import hashlib
import json
import time
import uuid
from pathlib import Path
from PIL import Image


def candidates_for(task, base):
    if task.get("target_selection"): return []
    key = task.get("run_key") or task["image_sha256"][:16]
    path = base / "runs" / ("upload_" + key + "_detector") / "results.json"
    if not path.exists(): return []
    row = json.loads(path.read_text(encoding="utf-8"))[0]
    if row.get("source_sha256") != task["image_sha256"]: return []
    if row.get("person_candidates", 0) < 2: return []
    return [{"box":box,"score":score} for box,score in zip(row["boxes"],row["scores"])]


def prepare_target(source, choice, index, base):
    tid = uuid.uuid4().hex
    original = Path(source["image_path"])
    image = Image.open(original).convert("RGB")
    # Pixel crop bounds are recorded explicitly; no resize or aspect change.
    import math
    box=choice["box"]
    bounds=(max(0,math.floor(box[0])), max(0,math.floor(box[1])),
            min(image.width,math.ceil(box[2])), min(image.height,math.ceil(box[3])))
    if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]: raise ValueError("invalid target box")
    crop=image.crop(bounds)
    path=base/"static"/(tid+".png"); crop.save(path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    selection={"parent_task_id":source["task_id"],"parent_image_sha256":source["image_sha256"],
               "index":index,"box_original_pixels":box,"crop_bounds_original_pixels":bounds,
               "crop_to_original_translation":[bounds[0],bounds[1]],"scale":1,
               "confirmation":"user_click", "all_stages_input":"same target crop", "crop_sha256":digest}
    identity=hashlib.sha256(json.dumps(selection,sort_keys=True).encode()).hexdigest()[:16]
    key=digest[:16]+"_target_"+identity
    detector=base/"runs"/("upload_"+key+"_detector");detector.mkdir(parents=True)
    row={"sample_id":"upload_"+key,"subject_id":"upload_"+key,"source_sha256":digest,
         "person_candidates":1,"boxes":[[0,0,crop.width,crop.height]],"scores":[choice["score"]],
         "selected_box":[0,0,crop.width,crop.height],"selected_score":choice["score"],
         "original_wh":[crop.width,crop.height],"target_selection":selection}
    (detector/"results.json").write_text(json.dumps([row],indent=2),encoding="utf-8")
    work=base/"runs"/key;work.mkdir()
    (work/"target_selection.json").write_text(json.dumps(selection,indent=2),encoding="utf-8")
    return {"task_id":tid,"attempt":1,"status":"queued","height_status":"queued",
            "clothing_status":"queued","body_status":"queued","height_cm":None,
            "failure_reason":None,"image_path":str(path),"image_url":"/static/"+path.name,
            "image_sha256":digest,"run_key":key,"force_fresh":False,"submitted_at":time.time(),
            "method_version":source["method_version"],"target_selection":selection,
            "evaluation_scope":"用户指定目标后完成；非全自动首次成功"}
