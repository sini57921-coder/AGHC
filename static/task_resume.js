let resumeSubmitting=false;
function renderResume(task){
 const button=document.getElementById('resumeTask'),note=document.getElementById('resumeNote');
 if(!button)return;
 const allowed=task?.resume_allowed===true;
 button.hidden=!allowed;button.disabled=resumeSubmitting;
 note.hidden=!allowed&&!resumeSubmitting;
 if(resumeSubmitting)return;
 const cause=[task?.failure_reason,task?.clothing_failure_reason,task?.body_failure_reason].filter(Boolean).join(' ');
 note.textContent=/memory|allocat|显存|内存|cuda|环境|FileNotFound|FileExists|compiler/i.test(cause)?'请先处理内存、路径或运行环境问题，再继续。点击不会自动消除故障。':'接续会保留输入、已选目标及成功结果，只处理未完成阶段。不会自动重试。';
 button.textContent='继续处理';
}
async function continueTask(){
 if(resumeSubmitting||!currentTask?.resume_allowed)return;
 resumeSubmitting=true;
 const id=currentTask.task_id,button=document.getElementById('resumeTask'),note=document.getElementById('resumeNote');
 button.disabled=true;button.textContent='正在提交接续';note.hidden=false;note.textContent='正在提交一次接续请求，请勿重复点击。';
 try{
  const response=await fetch('/api/tasks/'+encodeURIComponent(id)+'/resume',{method:'POST'});
  const result=await response.json();
  if(!response.ok)throw new Error(result.detail||'接续未被接收');
  await followTask(result.task_id);
 }catch(error){
  // A lost POST response is ambiguous: query once, never POST automatically again.
  note.textContent='接续反馈中断，将查询原任务状态；不会自动重复提交。';
  try{await followTask(id);}catch(queryError){currentTask={...currentTask,resume_allowed:false};connectionError(queryError);note.textContent='连接中断，请用“重新连接”查询是否已入队，勿重复提交接续。';}
 }finally{
  resumeSubmitting=false;renderResume(currentTask);
 }
}
document.getElementById('resumeTask').onclick=continueTask;
