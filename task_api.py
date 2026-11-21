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
from task_resume import resume_allowed, prepare_resume
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
    if task.get("status") == "cancelled": return "cancelled"
    if task.get("status") == "awaiting_target": return "awaiting_target"
    if task.get("status") == "queued": return "waiting"
    if task.get("status") == "running": return "partial" if hs == "ok" else "running"
    if hs == "failed": return "failed"
    if hs == "ok" and (cs == "failed" or bs == "failed"): return "partial"
    if hs == "ok" and cs == "ok" and bs == "ok": return "completed"
    return "partial" if task.get("status") in ("completed", "failed") else "running"


def stage(task):
    if task.get("status") == "cancelled": return "已取消排队，未执行本次推理"
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
        if task.get("preserved_stages"):
            task["timing_scope"] = "resumed_stages"
            task["display_time_note"] = "本次接续耗时，不含先前已完成阶段；历史分段不可相加为首次完整耗时"
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


def process_task(task):
    with guard:
        if task.get("status") != "queued": return
        task.update(status="running", started_at=time.time())
        task["queue_time"] = round(task["started_at"] - task["submitted_at"], 3) if task.get("submitted_at") else None
        save(task)
    if task.get("height_status") != "ok":
        with guard:
            task.update(height_status="running", height_started_at=time.time()); save(task)
        try:
            result = run_ai(task["image_path"], run_key=task.get("run_key"), force_fresh=task.get("force_fresh", False))
        except Exception as error:
            result = {"status":"failed", "height_cm":None, "failure_reason":f"{type(error).__name__}: {error}", "inference_time":round(time.time()-task["height_started_at"],3)}
        if result.get("status") == "failed" and "person_binding_ambiguous" in (result.get("failure_reason") or ""):
            choices = candidates_for(task, BASE)
            if choices:
                with guard:
                    task.update(status="awaiting_target", height_status="awaiting_target", target_candidates=choices, failure_reason=None); save(task)
                return
        with guard:
            task.update({k:v for k,v in result.items() if k != "status"})
            task.update(height_status=result["status"], height_finished_at=time.time(), height_duration=result.get("inference_time"))
            if result["status"] != "ok":
                for stage_name in ("clothing", "body"):
                    if task.get(stage_name+"_status") != "ok":
                        task[stage_name+"_status"]="skipped"
                        task[stage_name+"_failure_reason"]="未运行："+(result.get("failure_reason") or "身高阶段失败")
                close_task(task)
                return
            save(task)
    if task.get("clothing_status") != "ok":
        with guard:
            task.update(clothing_status="running", clothing_started_at=time.time()); save(task)
        try: clothing=build_clothed(task)
        except Exception as error: clothing={"clothing_status":"failed", "clothing_failure_reason":f"{type(error).__name__}: {error}", "obj_url":None,"obj_role":None}
        with guard:
            task.update(clothing); task.update(clothing_finished_at=time.time(), clothing_duration=round(time.time()-task["clothing_started_at"],3)); save(task)
    if task.get("body_status") != "ok":
        with guard:
            task.update(body_status="running", body_started_at=time.time()); save(task)
        try: body=build_body(task, task)
        except Exception as error: body={"body_status":"failed", "body_failure_reason":f"{type(error).__name__}: {error}", "body_canonical_url":None,"body_original_url":None}
        with guard:
            task.update(body); task.update(body_finished_at=time.time(), body_duration=round(time.time()-task["body_started_at"],3)); save(task)
    with guard: close_task(task)


def worker():
    while True:
        task_id=pending.get()
        try: process_task(records[task_id])
        finally: pending.task_done()


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
        return {**task,"resume_allowed":resume_allowed(task),"cancel_allowed":task.get("status")=="queued","target_candidates":choices,"result_state":result_state(task),"stage":stage(task)}

@app.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    with guard:
        task=records.get(task_id)
        if task is None: raise HTTPException(404,"任务不存在")
        if not resume_allowed(task):
            raise HTTPException(409,"当前任务不允许接续；运行中请查询状态，从头运行验收任务请按原规则提交")
        prepare_resume(task, time.time())
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

@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    with guard:
        task=records.get(task_id)
        if task is None: raise HTTPException(404,"任务不存在")
        if task.get("status")=="cancelled":
            return {"task_id":task_id,"status":"cancelled","message":"任务已取消"}
        if task.get("status")!="queued":
            message="任务已开始，未取消" if task.get("status")=="running" else "任务不在排队中，未取消"
            raise HTTPException(409,{"message":message,"status":task.get("status")})
        task.update(status="cancelled",cancelled_at=time.time(),failure_reason=None,
                    timing_scope="cancelled_before_execution",end_to_end_time=None,
                    display_time_note="任务在开始前取消，未产生本次推理耗时")
        task["finished_at"]=task["cancelled_at"]
        task["queue_time"]=round(task["cancelled_at"]-task["submitted_at"],3) if task.get("submitted_at") else None
        for stage_name in ("height","clothing","body"):
            if task.get(stage_name+"_status")=="queued":task[stage_name+"_status"]="cancelled"
        save(task)
        return {"task_id":task_id,"status":"cancelled","message":"已取消排队"}
