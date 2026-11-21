const viewerStates={};
const viewerLoadKeys={clothing:null,body:null};
let activeViewerTaskKey=null;

function makeViewer(kind){
  const stage=$(kind+'Stage');
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x292c31);
  const camera=new THREE.PerspectiveCamera(38,1,.001,1000);camera.position.set(0,0,4);
  const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));stage.prepend(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xffffff,0x42454a,.85));const light=new THREE.DirectionalLight(0xffffff,.65);light.position.set(3,5,5);scene.add(light);
  const state={scene,camera,renderer,model:null,initial:null,requestId:0,target:new THREE.Vector3(),theta:0,phi:Math.PI/2,distance:4};viewerStates[kind]=state;
  const resize=()=>{const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);if(state.model)fitViewer(kind,false)};
  new ResizeObserver(resize).observe(stage);resize();
  const canvas=renderer.domElement,pointers=new Map();let lastX=0,lastY=0,pinch=null;
  canvas.addEventListener('pointerdown',e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);pinch=null});
  const end=e=>{pointers.delete(e.pointerId);pinch=null;if(pointers.size===1){const p=[...pointers.values()][0];lastX=p.x;lastY=p.y}};
  canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
  canvas.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId)||!state.model)return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(pointers.size===2){const [a,b]=[...pointers.values()],d=Math.hypot(a.x-b.x,a.y-b.y);if(pinch&&d>0){state.distance*=pinch/d;state.distance=Math.max(state.radius*.2,Math.min(state.radius*20,state.distance));updateCamera(state)}pinch=d;return}
    const dx=e.clientX-lastX,dy=e.clientY-lastY;markViewPreset(kind,null);
    if(e.buttons===2){const factor=state.distance*.0015;const right=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,0),up=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,1);state.target.addScaledVector(right,-dx*factor).addScaledVector(up,dy*factor)}
    else{state.theta-=dx*.008;state.phi=Math.max(.12,Math.min(Math.PI-.12,state.phi-dy*.006))}lastX=e.clientX;lastY=e.clientY;updateCamera(state);
  });
  canvas.addEventListener('wheel',e=>{e.preventDefault();if(!state.model)return;state.distance*=e.deltaY>0?1.08:1/1.08;state.distance=Math.max(state.radius*.2,Math.min(state.radius*20,state.distance));updateCamera(state)},{passive:false});canvas.addEventListener('contextmenu',e=>e.preventDefault());
  setViewerTools(kind,false);
  const cap=kind==='body'?'Body':'Clothing';$('reset'+cap).onclick=()=>fitViewer(kind,true);$('front'+cap).onclick=()=>setView(kind,0);$('side'+cap).onclick=()=>setView(kind,Math.PI/2);
}
function updateCamera(state){const r=state.distance,s=Math.sin(state.phi);state.camera.position.set(state.target.x+r*s*Math.sin(state.theta),state.target.y+r*Math.cos(state.phi),state.target.z+r*s*Math.cos(state.theta));state.camera.lookAt(state.target);state.camera.updateMatrixWorld(true)}
function fitViewer(kind,resetOrientation=true){const state=viewerStates[kind];if(!state.model)return;if(resetOrientation){state.theta=0;state.phi=Math.PI/2;markViewPreset(kind,'front')}
  const box=new THREE.Box3().setFromObject(state.model),size=box.getSize(new THREE.Vector3());state.target.copy(box.getCenter(new THREE.Vector3()));state.radius=Math.max(size.length()/2,.001);
  const direction=new THREE.Vector3(Math.sin(state.phi)*Math.sin(state.theta),Math.cos(state.phi),Math.sin(state.phi)*Math.cos(state.theta));
  const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),direction).normalize(),up=new THREE.Vector3().crossVectors(direction,right).normalize();
  const tanV=Math.tan(THREE.MathUtils.degToRad(state.camera.fov/2)),tanH=tanV*state.camera.aspect;let required=0;
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){const v=new THREE.Vector3(x,y,z).sub(state.target);required=Math.max(required,v.dot(direction)+Math.max(Math.abs(v.dot(up))/tanV,Math.abs(v.dot(right))/tanH))}
  state.distance=Math.max(required*1.12,state.radius*.3);state.camera.near=Math.max(state.radius*.001,.0001);state.camera.far=state.radius*100;state.camera.updateProjectionMatrix();updateCamera(state);
  state.initial={position:state.model.position.clone(),rotation:state.model.rotation.clone(),scale:state.model.scale.clone(),camera:state.camera.position.clone()};
}
function setView(kind,theta){const state=viewerStates[kind];if(!state.model)return;state.theta=theta;state.phi=Math.PI/2;fitViewer(kind,false);markViewPreset(kind,theta===0?'front':'side')}
function markViewPreset(kind,mode){const cap=kind==='body'?'Body':'Clothing';for(const preset of ['front','side'])$(preset+cap).setAttribute('aria-pressed',String(mode===preset))}
function setViewerTools(kind,ready){const cap=kind==='body'?'Body':'Clothing';for(const tool of ['front','side','reset','save'])$(tool+cap).disabled=!ready;if(!ready)markViewPreset(kind,null)}

function setViewerMessage(kind,message,error=false){
  const element=$(kind+'Message');
  element.textContent=message;
  element.style.display='block';
  element.style.color=error?'#ffc0c0':'#e3e5e9';
  $(kind+'State').textContent=error?'加载失败':'处理中';
}

function clearViewerModel(state){
  if(state.model){
    state.scene.remove(state.model);
    state.model.traverse(o=>{if(o.geometry)o.geometry.dispose()});
  }
  state.model=null;
  state.initial=null;
  for(const [kind,entry] of Object.entries(viewerStates))if(entry===state)setViewerTools(kind,false);
}

function clearViewer(kind,message){
  const state=viewerStates[kind];
  state.requestId++;
  clearViewerModel(state);
  setViewerMessage(kind,message);
}

function clearAllModels(message){
  viewerLoadKeys.clothing=null;viewerLoadKeys.body=null;activeViewerTaskKey=null;
  clearViewer('clothing',message);
  clearViewer('body',message);
}

function normalizeViewer(kind,group){group.updateMatrixWorld(true);fitViewer(kind,true)}

function colorViewer(group,kind){
  group.traverse(o=>{
    if(!o.isMesh)return;
    o.material=new THREE.MeshStandardMaterial({
      color:kind==='clothing'?0xffffff:0xc9ced5,
      vertexColors:kind==='clothing'&&!!o.geometry.getAttribute('color'),
      roughness:.72,metalness:.02,side:THREE.DoubleSide
    });
  });
}

function loadViewer(kind,url){
  const state=viewerStates[kind];
  const requestId=++state.requestId;
  clearViewerModel(state);
  setViewerMessage(kind,'正在加载本任务3D模型…');
  new THREE.OBJLoader().load(url,group=>{
    if(requestId!==state.requestId){
      group.traverse(o=>{if(o.geometry)o.geometry.dispose()});
      return;
    }
    state.model=group;
    normalizeViewer(kind,group);
    colorViewer(group,kind);
    state.scene.add(group);
    $(kind+'Message').style.display='none';$(kind+'State').textContent='已加载';setViewerTools(kind,true);
    log((kind==='clothing'?'原姿态着装':'标准A姿态人体')+'网格加载完成。','ok');
  },undefined,error=>{
    if(requestId!==state.requestId)return;
    setViewerMessage(kind,'模型加载失败：'+(error?.message||'文件不可读取'),true);
    log((kind==='clothing'?'着装':'人体')+'网格加载失败：'+(error?.message||'未知错误'),'err');
  });
}

function resetViewer(kind){fitViewer(kind,true)}

function loadTaskViewer(kind,task){
  const body=kind==='body',status=task[body?'body_status':'clothing_status'];
  const valid=body?status==='ok':status==='ok'&&task.obj_role==='same_image_clothed_original_pose';
  const raw=body?task.body_canonical_url:task.obj_url;
  const url=valid&&raw?(raw.startsWith('http')?raw:API+raw):'';
  const reason=task[body?'body_failure_reason':'clothing_failure_reason'];
  const key=[task.task_id,task.attempt||1,url,status,reason||''].join('|');
  if(viewerLoadKeys[kind]===key)return;
  viewerLoadKeys[kind]=key;
  if(url){loadViewer(kind,url);return}
  const name=body?'标准A姿态人体':'原姿态着装';
  const message=status==='running'?name+'处理中':status==='queued'?'等待'+name:status==='ok'?'该侧已完成，但模型路径未提供':name+(reason?'：'+reason:'：'+statusText(status));
  clearViewer(kind,message);
  $(kind+'State').textContent=statusText(status);
}
function setTaskDot(mode){const element=$('serviceDot');element.classList.remove('offline','error','pending','warning');if(mode&&mode!=='ok')element.classList.add(mode)}
function statusText(status){return {ok:'成功',failed:'失败',skipped:'未运行',queued:'等待',running:'运行中'}[status]||'未记录'}
function taskState(task){
  if(task.status==='queued')return 'waiting';
  if(task.height_status==='failed')return 'failed';
  if(task.status==='running')return task.height_status==='ok'?'partial':'running';
  if(task.height_status==='ok'&&task.clothing_status==='ok'&&task.body_status==='ok')return 'completed';
  if(task.height_status==='ok')return 'partial';
  return task.status==='failed'?'failed':task.result_state||'waiting';
}
function featureSourceText(task){const source=task.feature_source??task.source;return source==='same_image_cache'?'同图已有特征缓存复用':source==='fresh_same_image'?'同图特征链路（可能复用阶段缓存）':'未记录'}
function finiteSeconds(value){return value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value))?Number(value):null}
function secondsText(value){const n=finiteSeconds(value);return n===null?'未记录':n.toFixed(3)+' 秒'}
function formatTaskDurations(task){
  const parts=['排队：'+secondsText(task.queue_time),'估高：'+secondsText(task.height_duration??task.inference_time)];
  if(task.clothing_duration!==undefined)parts.push('着装：'+secondsText(task.clothing_duration));
  if(task.body_duration!==undefined)parts.push('人体：'+secondsText(task.body_duration));
  if(task.display_time_note||task.timing_scope==='interrupted'){
    const note=(task.display_time_note||'任务运行中断；完整连续耗时不可得').replace(/(\d+(?:\.\d+)?)\s*ms\b/gi,(_,n)=>(Number(n)/1000).toFixed(3)+' 秒').replace(/(\d+(?:\.\d+)?)\s*s\b/gi,'$1 秒');
    parts.push('完整连续任务：未提供；分段不相加。'+note);
  }else if(task.timing_scope==='continuous')parts.push('完整任务（不含排队）：'+secondsText(task.end_to_end_time));
  else parts.push('任务原记录：'+secondsText(task.end_to_end_time)+'（历史连续口径未核实）');
  return parts.join('；');
}
function renderTask(task){
  const identity=task.task_id==='historical_case_not_distributed'?'历史示例 · 原图':task.task_id==='historical_case_not_distributed'?'历史示例 · 人工遮挡':'当前任务';if($('taskIdentity'))$('taskIdentity').textContent=identity;
  currentTask=task;
  renderTargetSelection(task);
  const terminal=task.status==='completed'||task.status==='failed',state=taskState(task);
  document.body.classList.toggle('is-complete',terminal);
  if(terminal)document.body.classList.remove('editing-input');
  $('taskId').textContent=task.task_id||'—';$('stageText').textContent=task.stage||({waiting:'等待执行',running:'处理中',partial:'部分完成',completed:'已完成',failed:'失败'}[state]);$('exportSummary').disabled=false;
  if(task.image_url){setPreview('original',API+task.image_url);$('original').dataset.taskImage=task.image_url;if(!selectedFile)$('fileName').textContent='已载入本任务照片'}
  const height=task.height_cm==null?NaN:Number(task.height_cm),heightOK=Number.isFinite(height)&&task.height_status==='ok';
  setResult(heightOK?height:null,state,formatTaskDurations(task));
  updateCaseContext(task);
  $('backendStatus').textContent={waiting:'等待',running:'运行中',partial:terminal?'部分完成 · 含失败':'部分完成 · 继续处理中',completed:'完成',failed:'失败'}[state];
  $('resultHint').textContent=terminal?(state==='completed'?'身高、人体与着装均已完成':state==='partial'?'可用结果已保留，请查看各侧原因':'没有有效身高，请查看失败原因'):(state==='partial'?'身高已完成，模型阶段继续运行':'请查看当前阶段，页面可刷新恢复');
  setTaskDot(state==='failed'?'error':state==='partial'?'warning':state==='completed'?'ok':'pending');
  const lines=['身高：'+statusText(task.height_status),'着装：'+statusText(task.clothing_status),'人体：'+statusText(task.body_status),'特征来源：'+featureSourceText(task)];
  for(const [label,key] of [['着装','clothing'],['人体','body']])if(task[key+'_failure_reason'])lines.push(label+'原因：'+task[key+'_failure_reason']);
  if(task.mesh_scale_status==='unscaled')lines.push('未公制标定：'+(task.mesh_scale_reason||'未记录'));
  $('modelStatus').textContent=lines.join('；');
  $('modelExplanation').textContent='特征来源不表示独立验证资格；同图链路也可能使用已完成的阶段缓存。人体和着装状态分别报告，模型尺度展示不构成新的厘米精度验证。';
  $('failureReason').hidden=state!=='failed';$('failureReason').style.display=state==='failed'?'block':'none';$('failureReason').textContent=state==='failed'?(task.failure_reason||'失败原因未记录'):'';
  if(terminal){$('waitTime').textContent='';if(location.hash==='#methods'){linkedSectionOpened=false;openLinkedSection()}}
  for(const kind of ['clothing','body'])loadTaskViewer(kind,task);
}
function renderProgress(task){renderTask(task)}
function renderData(task){renderTask(task)}

async function checkHealth(){
  try{
    const response=await fetch(API+'/health');
    if(!response.ok)throw new Error();
    if(!new URLSearchParams(location.search).get('task')){setTaskDot('ok');$('backendStatus').textContent='本机服务在线'}
  }catch{setTaskDot('offline');$('backendStatus').textContent='本机服务未连接'}
}

function animateViewers(){
  requestAnimationFrame(animateViewers);
  for(const state of Object.values(viewerStates))state.renderer.render(state.scene,state.camera);
}

makeViewer('clothing');
makeViewer('body');
animateViewers();
log('双模型查看器初始化完成。','ok');

async function followTask(taskId){
  const generation=++followGeneration;
  history.replaceState(null,'',location.pathname+'?task='+encodeURIComponent(taskId)+location.hash);
  localStorage.setItem('aghc_last_task',taskId);$('reconnect').hidden=true;

  let lastStage='';
  while(true){
    const response=await fetch(API+'/api/tasks/'+encodeURIComponent(taskId));
    if(!response.ok)throw new Error('状态查询失败：'+response.status);
    const task=await response.json();
    if(generation!==followGeneration)return;
    const taskKey=task.task_id+'|'+(task.attempt||1); if(activeViewerTaskKey!==taskKey){clearAllModels('正在读取本任务模型…');viewerLoadKeys.clothing=null;viewerLoadKeys.body=null;activeViewerTaskKey=taskKey;}
    currentTask=task;startedAt=task.submitted_at==null?startedAt:Number(task.submitted_at)*1000;

    if(task.stage!==lastStage){lastStage=task.stage;log(task.stage||'推理中')}
    if(task.status==='completed'||task.status==='failed'||task.status==='awaiting_target'){
      renderData(task);
      log(task.height_status==='ok'&&task.clothing_status==='failed'?'身高预测完成；着装重建失败：'+(task.clothing_failure_reason||'未提供原因'):task.status==='completed'?'任务完成。':'任务失败：'+(task.failure_reason||'未提供原因'),task.status==='failed'||task.clothing_status==='failed'?'err':'ok');
      return task;
    }
    renderProgress(task);
    await new Promise(resolve=>setTimeout(resolve,2000));
  }
}

const savedTask=new URLSearchParams(location.search).get('task')||localStorage.getItem('aghc_last_task');
checkHealth();
if(savedTask){
  if(savedTask==='historical_case_not_distributed')$('caseNotice').textContent='历史示例 · 仅供内部使用，未重新推理。';
  setBusy(true,'恢复任务…');
  followTask(savedTask).catch(error=>{
    log('恢复任务失败：'+error.message,'err');
    $('backendStatus').textContent='任务状态读取失败';$('stageText').textContent='连接中断：'+error.message;$('reconnect').hidden=false;
    setTaskDot('offline');
    // Keep any partial result already loaded before the connection failed.
  }).finally(()=>setBusy(false));
}




