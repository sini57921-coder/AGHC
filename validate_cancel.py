"""CPU-only cancellation checks using isolated records and stage substitutes."""
import ast,copy,json,queue,tempfile,threading,time
from pathlib import Path
from fastapi import HTTPException
from task_resume import resume_allowed

ROOT=Path(__file__).resolve().parent

def main():
 with tempfile.TemporaryDirectory() as directory:
  base=Path(directory);records={};calls=[];entered=threading.Event();release=threading.Event()
  def height(*a,**k):calls.append("height");entered.set();release.wait(3);return {"status":"ok","height_cm":170,"inference_time":1}
  def clothes(task):calls.append("clothes");return {"clothing_status":"ok"}
  def body(task,source):calls.append("body");return {"body_status":"ok"}
  ns={"guard":threading.Lock(),"time":time,"json":json,"records":records,"HTTPException":HTTPException,"BASE":base,"STATIC":base/"static","TASKS":base/"tasks","current_econ":lambda work:work/"econ","run_ai":height,"build_clothed":clothes,"build_body":body,"candidates_for":lambda *a:[]}
  ns["TASKS"].mkdir()
  names={"cancel_task","process_task","close_task","save","write_unified","result_state","stage"}
  funcs=[n for n in ast.parse((ROOT/"task_api.py").read_text(encoding="utf-8")).body if isinstance(n,ast.FunctionDef) and n.name in names]
  for f in funcs:f.decorator_list=[]
  exec(compile(ast.Module(body=funcs,type_ignores=[]),"isolated_cancel_functions","exec"),ns)
  task={"task_id":"synthetic","status":"queued","height_status":"queued","clothing_status":"queued","body_status":"queued","image_path":"synthetic.png","image_sha256":"synthetic","run_key":"synthetic","submitted_at":time.time()}
  records["synthetic"]=copy.deepcopy(task);ns["cancel_task"]("synthetic");snapshot=copy.deepcopy(records["synthetic"])
  ns["cancel_task"]("synthetic");assert snapshot==records["synthetic"]
  ns["process_task"](records["synthetic"]);assert not calls
  saved=json.loads((ns["TASKS"]/"synthetic.json").read_text(encoding="utf-8"));assert saved["status"]=="cancelled" and saved["result_state"]=="cancelled" and saved["failure_reason"] is None
  assert saved["image_path"]==task["image_path"] and not resume_allowed(saved)
  # Start wins the same lock: cancellation must not interrupt a running stage.
  records["synthetic"]=copy.deepcopy(task)
  thread=threading.Thread(target=ns["process_task"],args=(records["synthetic"],));thread.start();assert entered.wait(2)
  try:ns["cancel_task"]("synthetic")
  except HTTPException as error:assert error.status_code==409 and error.detail["message"]=="任务已开始，未取消"
  else:raise AssertionError("running task cancelled")
  release.set();thread.join(3);assert not thread.is_alive() and calls==["height","clothes","body"]
  assert records["synthetic"]["status"]=="completed"
  partial={**task,"height_status":"ok","height_cm":170,"body_status":"ok","body_canonical_url":"keep.obj"};records["synthetic"]=partial
  ns["cancel_task"]("synthetic");assert partial["height_cm"]==170 and partial["body_canonical_url"]=="keep.obj"
  print(json.dumps({"cancel_before_start_skips_models":True,"duplicate_cancel_no_changes":True,"start_wins_returns_409":True,"cancelled_persisted":True,"input_and_successes_preserved":True,"not_inference_failure":True,"gpu_runs":0}))

if __name__=="__main__":main()
