import json,os,time
from pathlib import Path
import onnxruntime as ort
_original=ort.InferenceSession
_log=os.environ.get("AGHC_REMBG_PROVIDER_LOG")
def emit(row):
 if _log:
  with Path(_log).open("a",encoding="utf-8") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
class TimedSession:
 def __init__(self,session):self.session=session
 def __getattr__(self,name):return getattr(self.session,name)
 def run(self,*args,**kwargs):
  start=time.perf_counter()
  try:
   result=self.session.run(*args,**kwargs)
  except Exception as error:
   emit({"event":"run_failed","actual_providers":self.session.get_providers(),"seconds":time.perf_counter()-start,"error":repr(error)});raise
  emit({"event":"run_completed","actual_providers":self.session.get_providers(),"seconds":time.perf_counter()-start});return result
def cpu_u2net(path_or_bytes,*args,**kwargs):
 name=Path(str(path_or_bytes)).name.lower() if isinstance(path_or_bytes,(str,os.PathLike)) else ""
 if name!="u2net.onnx":return _original(path_or_bytes,*args,**kwargs)
 args=list(args)
 if len(args)>=2:args[1]=["CPUExecutionProvider"];kwargs.pop("providers",None)
 else:kwargs["providers"]=["CPUExecutionProvider"]
 session=_original(path_or_bytes,*args,**kwargs)
 actual=session.get_providers();emit({"event":"session_created","model":str(path_or_bytes),"requested_providers":["CPUExecutionProvider"],"actual_providers":actual,"pid":os.getpid()})
 if actual!=["CPUExecutionProvider"]:raise RuntimeError("U2Net CPU provider not effective: "+str(actual))
 print("AGHC_U2NET_ACTUAL_PROVIDERS",actual,flush=True)
 return TimedSession(session)
ort.InferenceSession=cpu_u2net
