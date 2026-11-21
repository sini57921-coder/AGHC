import hashlib
import json
import queue
import threading
import time
import uuid
from pathlib import Path
from fastapi import Body
from target_selection import candidates_for, prepare_target
from econ_paths import current_econ
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from ai_adapter import run_ai
from clothed_task import build as build_clothed
from body_mesh_task import build as build_body
from input_image import normalize_image, InputImageError

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
TASKS = BASE / "runs" / "web_tasks"
UPLOADS = BASE / "runs" / "uploads"
TASKS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="单张RGB身高估计", version="frozen35-tasks")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
pending = queue.Queue()
records = {}
guard = threading.Lock()


def result_state(task):
    hs, cs, bs = (task.get(k) for k in ("height_status", "clothing_status", "body_status"))
    if task.get("status") == "awaiting_target": return "awaiting_target"
    if task.get("status") == "queued": return "waiting"
    if task.get("status") == "running": return "partial" if hs == "ok" else "running"
    if hs == "failed": return "failed"
    if hs == "ok" and (cs == "failed" or bs == "failed"): return "partial"
    if hs == "ok" and cs == "ok" and bs == "ok": return "completed"
    return "partial" if task.get("status") in ("completed", "failed") else "running"


def stage(task):
    if task.get("status") == "awaiting_target": return "请点击编号框确认目标人物"
    rs = result_state(task)
    if rs == "waiting": return "等待任务执行"
    if task.get("height_status") in ("queued", "running"):
        digest = task.get("run_key") or task.get("image_sha256", "")[:16]
        sample = "upload_" + digest
        root = BASE / "runs"
        stages = [("人物检测", root / f"{sample}_detector/results.json"), ("相机视场", root / f"{sample}_fov/completion.json"), ("人体模型", root / f"{sample}_body/completion.json"), ("反射体形特征", root / f"{sample}_reflection/features.json"), ("人脸特征", root / digest / "face/features.json"), ("ECON体形恢复", current_econ(root / digest) / sample / "canonical/canonical_apose.json")]
        for name, path in stages:
            if not path.exists(): return name + "处理中"
        return "前端特征完成，正在执行35维预测"
    if task.get("height_status") == "failed": return "身高预测失败"
    for target in ("running", "queued"):
        for key, label in (("clothing_status", "着装重建"), ("body_status", "人体网格")):
            if task.get(key) == target: return (("着装重建中" if key.startswith("clothing") else "人体网格生成中") if target == "running" else label + "等待中")
    for key, label in (("clothing_status", "着装重建"), ("body_status", "人体网格")):
        if task.get(key) == "failed": return label + "失败"
    return {"completed": "全部阶段完成", "partial": "身高完成，模型阶段部分失败", "failed": "任务失败"}.get(rs, "处理中")


def write_unified(task):
    result_path = STATIC / "generated" / task["task_id"] / "unified_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(task, ensure_ascii=False, indent=2)
    result_path.write_text(payload, encoding="utf-8")
    (TASKS / f'{task["task_id"]}.json').write_text(payload, encoding="utf-8")


def save(task):
    task["result_state"] = result_state(task)
    task["stage"] = stage(task)
    write_unified(task)

def close_task(task, interrupted=False):
    task["status"] = "failed" if task.get("height_status") == "failed" else "completed"
    task["finished_at"] = time.time()
    if interrupted:
        task["timing_scope"] = "interrupted"
        task["display_time_note"] = "服务重启前的阶段耗时分别记录；停机间隔未计入"
    else:
        task["end_to_end_time"] = round(task["finished_at"] - task["started_at"], 3)
        task["timing_scope"] = "continuous"
    save(task)

for task_file in TASKS.glob("*.json"):
    task = json.loads(task_file.read_text(encoding="utf-8"))
    if task.get("status") in ("queued", "running"):
        if task.get("status") == "queued":
            task.update(height_status="failed", failure_reason="排队任务尚未开始，服务重启后未自动续跑", clothing_status="skipped", body_status="skipped", clothing_failure_reason="未运行：排队任务在服务重启前尚未开始", body_failure_reason="未运行：排队任务在服务重启前尚未开始", inference_time=None, height_duration=None, end_to_end_time=None, queue_time=None, started_at=None)
            task["display_time_note"] = "排队任务尚未开始，未产生推理耗时"
        elif task.get("height_status") in ("queued", "running"):
            task.update(height_status="failed", failure_reason=task.get("failure_reason") or "服务重启时身高阶段中断；未自动续跑", clothing_status="skipped", body_status="skipped", clothing_failure_reason="未运行：身高阶段中断", body_failure_reason="未运行：身高阶段中断")
        else:
            for key, label in (("clothing_status", "着装"), ("body_status", "人体网格")):
                if task.get(key) == "running":
                    task[key] = "failed"
                    task[key.replace("status", "failure_reason")] = f"服务重启时{label}阶段中断；未自动续跑"
                elif task.get(key) == "queued":
                    task[key] = "skipped"
                    task[key.replace("status", "failure_reason")] = f"未运行：服务重启时{label}阶段仍在等待"
        close_task(task, interrupted=True)
    records[task.get("task_id", task_file.stem)] = task


def worker():
    while True:
        task_id = pending.get()
        with guard:
            task = records[task_id]
            task.update(status="running", height_status="running", started_at=time.time(), height_started_at=time.time())
            task["queue_time"] = round(task["started_at"] - task["submitted_at"], 3) if task.get("submitted_at") else None
            save(task)
        try:
            result = run_ai(task["image_path"], run_key=task.get("run_key"), force_fresh=task.get("force_fresh", False))
        except Exception as error:
            result = {"status": "failed", "height_cm": None, "failure_reason": f"{type(error).__name__}: {error}", "inference_time": round(time.time() - task["started_at"], 3)}
        if result.get("status") == "failed" and "person_binding_ambiguous" in (result.get("failure_reason") or ""):
            choices = candidates_for(task, BASE)
            if choices:
                with guard:
                    task.update(status="awaiting_target", height_status="awaiting_target", target_candidates=choices,
                                clothing_status="queued", body_status="queued", failure_reason=None)
                    save(task)
                pending.task_done()
                continue
        with guard:
            task.update({k:v for k,v in result.items() if k != "status"})
            task["height_status"] = result["status"]
            task["height_finished_at"] = time.time()
            task["height_duration"] = result.get("inference_time")
            task["clothing_status"] = "running" if result["status"] == "ok" else "skipped"
            task["body_status"] = "queued" if result["status"] == "ok" else "skipped"
            if result["status"] != "ok":
                cause = result.get("failure_reason") or "身高阶段未返回有效结果"
                task["clothing_failure_reason"] = task["body_failure_reason"] = f"未运行：{cause}"
                close_task(task)
            else: save(task)
        if result["status"] == "ok":
            task["clothing_started_at"] = time.time()
            with guard: save(task)
            try: clothing = build_clothed(task)
            except Exception as error: clothing = {"clothing_status":"failed", "clothing_failure_reason":f"{type(error).__name__}: {error}", "obj_url":None, "obj_role":None}
            with guard:
                task.update(clothing); task["clothing_finished_at"] = time.time(); task["clothing_duration"] = round(task["clothing_finished_at"]-task["clothing_started_at"],3); save(task)
                task["body_status"] = "running"; task["body_started_at"] = time.time(); save(task)
            try: body = build_body(task, clothing)
            except Exception as error: body = {"body_status":"failed", "body_failure_reason":f"{type(error).__name__}: {error}", "body_canonical_url":None, "body_original_url":None}
            with guard:
                task.update(body); task["body_finished_at"] = time.time(); task["body_duration"] = round(task["body_finished_at"]-task["body_started_at"],3); close_task(task)
        pending.task_done()


threading.Thread(target=worker, daemon=True).start()

@app.post("/api/tasks")
async def submit(file: UploadFile = File(...), force_fresh: bool = False):
    task_id = uuid.uuid4().hex
    original_dir = UPLOADS / task_id
    original_dir.mkdir(parents=True)
    original_path = original_dir / "original.bin"
    original = await file.read()
    original_path.write_bytes(original)
    record_path = original_dir / "input_processing.json"
    processing = {"task_id": task_id, "original_filename": file.filename,
                  "declared_content_type": file.content_type,
                  "original_path": str(original_path),
                  "original_sha256": hashlib.sha256(original).hexdigest()}
    try:
        data, conversion = normalize_image(original)
    except InputImageError as error:
        processing.update(status="rejected", failure_reason=str(error), failure_code=error.code)
        record_path.write_text(json.dumps(processing, ensure_ascii=False, indent=2), encoding="utf-8")
        raise HTTPException(error.status_code, {"code": error.code, "reason": str(error), "input_record_id": task_id})
    path = STATIC / (task_id + ".png")
    path.write_bytes(data)
    processing.update(conversion, status="accepted", processed_path=str(path))
    record_path.write_text(json.dumps(processing, ensure_ascii=False, indent=2), encoding="utf-8")
    task = {"task_id":task_id,"attempt":1,"status":"queued","result_state":"waiting","height_cm":None,"height_status":"queued","clothing_status":"queued","clothing_failure_reason":None,"body_status":"queued","body_failure_reason":None,"failure_reason":None,"method_version":"frozen35_full112_clear_only_20261101_v1","inference_time":None,"image_path":str(path),"image_url":"/static/"+path.name,"image_sha256":hashlib.sha256(data).hexdigest(),"obj_url":None,"obj_role":None,"submitted_at":time.time()}
    task["force_fresh"] = force_fresh
    task.update(original_image_path=str(original_path), original_filename=file.filename,
                original_sha256=processing["original_sha256"],
                input_record_path=str(record_path), input_processing=processing)
    task["run_key"] = task["image_sha256"][:16] + ("_" + task_id[:8] if force_fresh else "")
    with guard: records[task_id]=task; save(task)
    pending.put(task_id); return {"task_id":task_id,"status":"queued","result_state":"waiting"}

@app.get("/api/tasks/{task_id}")
def task_result(task_id: str):
    with guard:
        task=records.get(task_id)
        if task is None: raise HTTPException(404,"任务不存在")
        choices = candidates_for(task, BASE) if task.get("status") in ("failed", "awaiting_target") else []
        return {**task,"target_candidates":choices,"result_state":result_state(task),"stage":stage(task)}

@app.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    with guard:
        task=records.get(task_id)
        if task is None: raise HTTPException(404,"任务不存在")
        if task.get("force_fresh"):
            raise HTTPException(409,"从头运行任务请通过网页重新提交，不使用阶段接续")
        if task.get("status") not in ("failed","completed") or result_state(task) not in ("failed","partial"):
            raise HTTPException(409,"仅能接续终态失败或部分失败的任务")
        history=task.get("attempt_history",[]); old={k:v for k,v in task.items() if k not in ("attempt_history",)}; history.append(old)
        identity={k:task[k] for k in ("task_id","image_path","image_url","image_sha256","submitted_at","method_version","run_key","force_fresh","original_image_path","original_filename","original_sha256","input_record_path","input_processing","target_selection","evaluation_scope") if k in task}
        for key in list(task): task.pop(key)
        task.update(identity, attempt=old.get("attempt",1)+1, attempt_history=history, submitted_at=time.time(), status="queued",result_state="waiting",height_cm=None,height_status="queued",clothing_status="queued",body_status="queued",failure_reason=None,clothing_failure_reason=None,body_failure_reason=None,obj_url=None,obj_role=None,body_canonical_url=None,body_original_url=None,inference_time=None,end_to_end_time=None,queue_time=None,height_duration=None,clothing_duration=None,body_duration=None,height_started_at=None,height_finished_at=None,clothing_started_at=None,clothing_finished_at=None,body_started_at=None,body_finished_at=None,started_at=None,finished_at=None,feature_source=None,source=None,stage="等待任务执行")
        records[task_id]=task; save(task)
    pending.put(task_id); return {"task_id":task_id,"status":"queued","result_state":"waiting"}

@app.get("/health")
def health(): return {"status":"ok","model":"frozen35_full112_clear_only"}









@app.post("/api/tasks/{task_id}/target")
def select_target(task_id: str, payload: dict = Body(...)):
    with guard:
        source = records.get(task_id)
        if source is None: raise HTTPException(404, "任务不存在")
        selection_file = BASE / "runs" / "uploads" / task_id / "selected_target_task.json"
        if selection_file.exists():
            return json.loads(selection_file.read_text(encoding="utf-8"))
        if source.get("selected_target_task_id"):
            raise HTTPException(409, "本任务已确认目标，请打开对应的新任务")
        if source.get("status") not in ("awaiting_target", "failed"):
            raise HTTPException(409, "当前任务不等待目标选择")
        choices = candidates_for(source, BASE)
        index = payload.get("index")
        if type(index) is not int or index < 0 or index >= len(choices):
            raise HTTPException(400, "请选择有效编号")
        new = prepare_target(source, choices[index], index, BASE)
        records[new["task_id"]] = new
        save(new)
        selection_file.parent.mkdir(parents=True, exist_ok=True)
        selection_file.write_text(json.dumps({"task_id":new["task_id"],"status":"queued"}),encoding="utf-8")
        # Preserve original evaluation task files; selection lives in the child record.
    pending.put(new["task_id"])
    return {"task_id":new["task_id"], "status":"queued"}
