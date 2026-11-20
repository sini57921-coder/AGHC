import gc,json,os,sys,time,weakref,traceback
from pathlib import Path
import torch

_started=time.perf_counter()
_log=Path(os.environ['AGHC_STAGE_MEMORY_LOG'])
def memory_mark(stage,**extra):
 torch.cuda.synchronize()
 free,total=torch.cuda.mem_get_info()
 row={'stage':stage,'epoch':time.time(),'elapsed_s':time.perf_counter()-_started,'pid':os.getpid(),'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved(),'free_bytes':free,'total_bytes':total,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),**extra}
 with _log.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print('AGHC_STAGE_MEMORY',json.dumps(row,ensure_ascii=False),flush=True)
 return row

def prepare_single(dataset):
 memory_mark('runtime_settings',cudnn_workspace_cap_mib=os.environ.get('CUDNN_CONV_WSCAP_DBG'),cudnn_version=torch.backends.cudnn.version(),workspace_limit_verification='environment observed; no per-operator workspace measurement')
 smpl_id,render_id=id(dataset.smpl_model),id(dataset.render)
 hps=dataset.hps;original=hps.forward;ref=weakref.ref(hps)
 def measured(*args,**kwargs):
  tensor=args[0]
  memory_mark('pixie_before',input_shape=list(tensor.shape),input_dtype=str(tensor.dtype),input_device=str(tensor.device))
  start=time.perf_counter();output=original(*args,**kwargs)
  memory_mark('pixie_after',forward_s=time.perf_counter()-start)
  return output
 hps.forward=measured
 try:data=dataset[0]
 finally:del hps.forward
 memory_mark('dataset_item_ready',tensor_shapes={k:list(v.shape) for k,v in data.items() if torch.is_tensor(v)})
 del dataset.hps
 del original,measured,hps
 gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache();torch.cuda.synchronize()
 released=ref() is None
 memory_mark('pixie_released',hps_collected=released,retained_smpl_model=id(dataset.smpl_model)==smpl_id,retained_renderer=id(dataset.render)==render_id)
 if not released:raise RuntimeError('PIXIE object still referenced after release')
 return data

def install_normal_probe(netF):
 seen={'before':False,'after':False}
 def before(module,args):
  if seen['before']:return
  seen['before']=True;x=args[0];torch.cuda.reset_peak_memory_stats()
  memory_mark('normal_first_before',input_shape=list(x.shape),input_dtype=str(x.dtype),input_device=str(x.device))
  seen['start']=time.perf_counter()
 def after(module,args,output):
  if seen['after']:return
  seen['after']=True
  memory_mark('normal_first_after',forward_s=time.perf_counter()-seen['start'],output_shape=list(output.shape),output_dtype=str(output.dtype))
 netF.register_forward_pre_hook(before);netF.register_forward_hook(after)

def install_error_hook():
 original_hook=sys.excepthook
 def report(kind,error,tb):
  try:memory_mark('failure',error_type=kind.__name__,error=str(error),traceback=''.join(traceback.format_exception(kind,error,tb)))
  except Exception as logging_error:
   with _log.open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':'failure','error_type':kind.__name__,'error':str(error),'memory_record_error':repr(logging_error)},ensure_ascii=False)+'\n')
  original_hook(kind,error,tb)
 sys.excepthook=report
