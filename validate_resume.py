"""Isolated resume-state checks using actual functions and model substitutes, no GPU."""
import ast
import copy
import json
import queue
import tempfile
import threading
import time
from pathlib import Path
from fastapi import HTTPException
from task_resume import prepare_resume, resume_allowed

ROOT=Path(__file__).resolve().parent

def main():
    with tempfile.TemporaryDirectory() as temp:
        snapshots=[];records={};pending=queue.Queue();calls=[]
        def save(task):snapshots.append(copy.deepcopy(task))
        def height(*args,**kwargs):calls.append("height");return {"status":"ok","height_cm":170,"failure_reason":None,"inference_time":1}
        def clothing(task):calls.append("clothing");return {"clothing_status":"ok","obj_url":"synthetic_clothing.obj","obj_role":"same_image_clothed_original_pose","clothing_failure_reason":None}
        def body(task,source):calls.append("body");return {"body_status":"ok","body_canonical_url":"synthetic_body.obj","body_failure_reason":None}
        ns={"guard":threading.Lock(),"time":time,"records":records,"pending":pending,"HTTPException":HTTPException,
            "run_ai":height,"build_clothed":clothing,"build_body":body,"save":save,"BASE":Path(temp),
            "candidates_for":lambda *a:[],"prepare_resume":prepare_resume,"resume_allowed":resume_allowed}
        tree=ast.parse((ROOT/"task_api.py").read_text(encoding="utf-8"))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("close_task","process_task","resume_task")]
        for f in functions:f.decorator_list=[]
        exec(compile(ast.Module(body=functions,type_ignores=[]),"isolated_task_functions","exec"),ns)
        seed={"task_id":"synthetic","status":"failed","height_status":"failed","clothing_status":"skipped","body_status":"skipped","image_path":"synthetic_input.png","run_key":"selected_target_key","target_selection":{"index":1},"force_fresh":False,"submitted_at":time.time(),"failure_reason":"MemoryError"}
        records["synthetic"]=copy.deepcopy(seed);ns["resume_task"]("synthetic")
        assert pending.qsize()==1
        try:ns["resume_task"]("synthetic")
        except HTTPException as error:assert error.status_code==409
        else:raise AssertionError("duplicate resume accepted")
        assert pending.qsize()==1
        task=records["synthetic"];assert task["target_selection"]==seed["target_selection"] and task["run_key"]==seed["run_key"]
        ns["process_task"](task);assert calls==["height","clothing","body"] and task["status"]=="completed"
        assert task["attempt_history"][0]["failure_reason"]=="MemoryError"
        calls.clear();partial={**seed,"status":"completed","height_status":"ok","height_cm":170,"body_status":"ok","body_canonical_url":"keep_body.obj","clothing_status":"failed"}
        records["synthetic"]=copy.deepcopy(partial);ns["resume_task"]("synthetic");task=records["synthetic"]
        assert task["height_cm"]==170 and task["body_canonical_url"]=="keep_body.obj"
        ns["process_task"](task);assert calls==["clothing"] and task["body_canonical_url"]=="keep_body.obj"
        assert task["timing_scope"]=="resumed_stages"
        calls.clear();partial={**seed,"status":"completed","height_status":"ok","height_cm":170,"clothing_status":"ok","obj_url":"keep_clothes.obj","body_status":"failed"}
        records["synthetic"]=copy.deepcopy(partial);ns["resume_task"]("synthetic");ns["process_task"](records["synthetic"])
        assert calls==["body"] and records["synthetic"]["obj_url"]=="keep_clothes.obj"
        assert not resume_allowed({**seed,"force_fresh":True})
        assert not resume_allowed({**seed,"status":"running"})
        assert not resume_allowed({**seed,"failure_reason":"person_binding_ambiguous"})
        print(json.dumps({"failed_resume":True,"preserved_target":True,"partial_successes_not_recomputed":True,"duplicate_queue_blocked":True,"fresh_run_restriction":True,"resume_timing_scope":True,"gpu_runs":0}))

if __name__=="__main__":main()
