const API='';
const forceFreshRun=new URLSearchParams(location.search).get('fresh')==='1';
const $=id=>document.getElementById(id==='highlight'?'original':id);
let currentTask=null,selectedFile=null,followGeneration=0,startedAt=null,previewURL=null;
function log(msg,type=''){const row=document.createElement('div');row.className=type;row.textContent=new Date().toLocaleTimeString('zh-CN')+' '+msg;$('console').appendChild(row)}
function modal(msg){if($('examplePicker'))$('examplePicker').hidden=true;$('modalText').textContent=msg;$('modal').classList.add('show')}
$('close').onclick=()=>$('modal').classList.remove('show');
function setPreview(id,url){const target=$(id);if(target.dataset.url===url)return;target.dataset.url=url;target.replaceChildren();const img=document.createElement('img');img.alt='当前任务RGB输入';img.src=url;img.onerror=()=>{target.textContent='输入图像无法加载'};target.appendChild(img);document.body.classList.add('has-photo');const heading=document.querySelector('.panel-heading h1');if(heading)heading.textContent='当前照片';const label=document.querySelector('#drop strong');if(label)label.textContent='更换照片'}
function setResult(h,status,lat){
  $('height').innerHTML=h==null?'—<span>cm</span>':Number(h).toFixed(1)+'<span>cm</span>';
  $('preciseHeight').textContent='精确输出：'+(h==null?'—':Number(h).toFixed(4)+' cm')+'；小数位不代表测量精度';
  $('resultStatus').textContent={waiting:'等待',running:'运行中',partial:'部分完成',completed:'完成',failed:'失败',ok:'完成'}[status]||'尚未分析';
  $('latency').textContent=lat==null?'耗时：未记录':lat;
}
function setBusy(b,text){$('uploadBtn').disabled=b||!selectedFile;$('demoBtn').disabled=b;$('file').disabled=b;$('uploadBtn').textContent=b?(text||'处理中'):'开始分析'}
function prepareFile(file){if($('taskIdentity'))$('taskIdentity').textContent='待分析照片';document.body.classList.remove('occlusion-example');$('exampleContext').hidden=true;if($('file').disabled)return;if(!file||!file.type.startsWith('image/')){modal('请选择有效RGB图片');return}document.body.classList.remove('is-complete');document.body.classList.add('editing-input');followGeneration++;currentTask=null;startedAt=null;clearAllModels('待提交图像，尚未分析');setResult(null,'waiting',null);$('exportSummary').disabled=true;$('modelStatus').textContent='新图尚未提交';$('taskId').textContent='待提交';$('stageText').textContent='等待提交';selectedFile=file;$('uploadBtn').disabled=false;if(previewURL)URL.revokeObjectURL(previewURL);previewURL=URL.createObjectURL(file);setPreview('original',previewURL);$('fileName').textContent=file.name;log('已选图；提交后才开始推理')}
$('file').onchange=e=>prepareFile(e.target.files[0]);$('drop').ondragover=e=>{e.preventDefault();$('drop').classList.add('drag')};$('drop').ondragleave=()=>$('drop').classList.remove('drag');$('drop').ondrop=e=>{e.preventDefault();$('drop').classList.remove('drag');prepareFile(e.dataTransfer.files[0])};
$('uploadBtn').onclick=async()=>{
  if(!selectedFile){modal('请先选择一张图像');return}
  setBusy(true,'提交中');followGeneration++;currentTask=null;
  clearAllModels('等待新任务模型');setResult(null,'running',null);
  try{
    const fd=new FormData();fd.append('file',selectedFile);
    const response=await fetch('/api/tasks'+(forceFreshRun?'?force_fresh=true':''),{method:'POST',body:fd});
    const result=await response.json();
    if(!response.ok){const e=new Error(result.detail?.reason||result.detail||('提交失败 '+response.status));e.inputRejected=response.status>=400&&response.status<500;throw e}
    startedAt=Date.now();await followTask(result.task_id);
  }catch(e){
    if(e.inputRejected){setResult(null,'failed',null);$('stageText').textContent='输入未接收：'+e.message;$('failureReason').hidden=false;$('failureReason').textContent=e.message;log(e.message,'error');modal(e.message)}
    else connectionError(e);
  }finally{setBusy(false)}
};
function connectionError(e){$('backendStatus').textContent='连接中断';$('stageText').textContent='无法读取任务状态：'+e.message;$('reconnect').hidden=false;setTaskDot('offline');log(e.message,'error')}
$('demoBtn').onclick=()=>{modal('选择已有任务。仅供内部展示，不会重新推理。');$('examplePicker').hidden=false};
function loadExample(taskId){selectedFile=null;$('file').value='';$('modal').classList.remove('show');setBusy(true,'读取示例');followTask(taskId).catch(connectionError).finally(()=>setBusy(false))}
$('exampleClear').disabled=true;
$('exampleOccluded').disabled=true;
function updateCaseContext(task){const occluded=task?.task_id==='historical_case_not_distributed';document.body.classList.toggle('occlusion-example',occluded);$('exampleContext').hidden=!occluded;if(occluded){$('resultHint').textContent='人工遮挡案例 · 当前系统历史任务';$('exampleContext').textContent='BARACCA 001 局部躯干人工遮挡：输入、人体和着装均来自本任务。此为当前冻结生产链路演示，不能与历史五折预测直接比较，不代表精度改善。';$('caseNotice').textContent='人工遮挡历史任务 · 仅内部使用，未重新推理。'}else if(task?.task_id==='historical_case_not_distributed')$('caseNotice').textContent='原图历史任务 · 仅内部使用，未重新推理。'}
$('reconnect').onclick=()=>{const id=new URLSearchParams(location.search).get('task');if(id)followTask(id).catch(connectionError)};
function downloadBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportTimingScope(task){if(task.timing_scope==='resumed_stages')return {timing_scope:'resumed_stages',resume_processing_seconds:task.end_to_end_time??null,continuous_full_task_seconds:null,end_to_end_time:null,timing_explanation:task.display_time_note};const segmented=!!task.display_time_note||task.timing_scope==='interrupted';if(segmented)return {timing_scope:'historical_segmented',end_to_end_time:null,recorded_legacy_elapsed_s:task.end_to_end_time??null,recorded_legacy_elapsed_scope:'历史初次任务记录，非完整双模型端到端耗时',continuous_full_task_seconds:null,timing_explanation:task.display_time_note||'分次或中断记录，不能相加为连续端到端时间'};return {timing_scope:task.timing_scope||'historical_unverified',continuous_full_task_seconds:task.timing_scope==='continuous'?task.end_to_end_time??null:null,timing_explanation:task.timing_scope==='continuous'?'完整连续任务，不含排队':'连续计时范围未经核实，不作为完整端到端耗时'};}
$('exportSummary').onclick=()=>{if(!currentTask)return;const keys=['task_id','attempt','status','result_state','height_cm','height_status','failure_reason','method_version','feature_source','source','inference_time','queue_time','end_to_end_time','height_duration','clothing_duration','body_duration','timing_scope','display_time_note','stage','body_status','body_failure_reason','clothing_status','clothing_failure_reason','mesh_scale_status','mesh_scale_reason','body_parameter_matches_clothing'];const data={export_scope:'当前任务摘要；不包含本机绝对路径、其他任务或人物数据',display_note:'显示小数不代表测量精度'};for(const key of keys)if(currentTask[key]!==undefined)data[key]=currentTask[key];Object.assign(data,exportTimingScope(currentTask));downloadBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'AGHC_'+currentTask.task_id+'_summary.json')};
for(const [kind,cap] of [['clothing','Clothing'],['body','Body']])$('save'+cap).onclick=()=>{const state=viewerStates[kind];if(!state?.model){modal('该侧尚无可导出的模型视图');return}state.renderer.render(state.scene,state.camera);state.renderer.domElement.toBlob(blob=>{if(blob)downloadBlob(blob,'AGHC_'+currentTask.task_id+'_'+kind+'.png')},'image/png')};
setInterval(()=>{if(startedAt&&currentTask&&['queued','running'].includes(currentTask.status))$('waitTime').textContent='已等待 '+Math.max(0,Math.floor((Date.now()-startedAt)/1000))+' 秒（含排队）'},1000);

$('aboutBtn').onclick=()=>modal('上传照片后点击“开始分析”。请保留单人真实头顶和足部。\n\n通常需数分钟，以当前任务记录为准；身高和模型可能分别成功或失败。\n\n开发集误差约5—7 cm，尚未达到3 cm目标，未证明稳定的局部遮挡精度收益。显示小数不代表测量精度。\n\n可在“方法与局限”中查看来源及完整边界。');
$('changePhoto').onclick=()=>{document.body.classList.add('editing-input');$('inputPanel').scrollIntoView({behavior:'smooth',block:'start'})};



let linkedSectionOpened=false;
function openLinkedSection(){if(location.hash!=='#methods'||linkedSectionOpened)return;const section=$('methods');if(!section)return;section.open=true;linkedSectionOpened=true;requestAnimationFrame(()=>section.scrollIntoView({block:'start'}))}
window.addEventListener('hashchange',()=>{linkedSectionOpened=false;openLinkedSection()});
openLinkedSection();
const comparisonNav=document.querySelector('nav a[href="/static/occlusion.html"]');
if(comparisonNav)comparisonNav.addEventListener('click',()=>{const id=currentTask?.task_id||localStorage.getItem('aghc_last_task');if(id&&/^[a-f0-9]{32}$/.test(id))comparisonNav.href='/static/occlusion.html?return_task='+encodeURIComponent(id)});

$('demoBtn').disabled=true; $('caseNotice').textContent='发布候选不附带人物案例；请使用获准图片。';
