let cancelSubmitting=false,cancelNotice='',cancelNoticeTask=null;
function renderCancel(task){
 const button=document.getElementById('cancelTask'),note=document.getElementById('cancelNote');
 button.hidden=task?.cancel_allowed!==true;button.disabled=cancelSubmitting;
 if(cancelNoticeTask===task?.task_id&&cancelNotice){note.hidden=false;note.textContent=cancelNotice;}
 else{note.hidden=true;}
}
async function cancelQueuedTask(){
 if(cancelSubmitting||!currentTask?.cancel_allowed)return;
 const id=currentTask.task_id;cancelSubmitting=true;cancelNoticeTask=id;cancelNotice='正在取消排队';renderCancel(currentTask);
 try{
  const response=await fetch('/api/tasks/'+encodeURIComponent(id)+'/cancel',{method:'POST'});
  const result=await response.json();
  cancelNotice=response.ok?result.message:(result.detail?.message||result.detail||'未取消');
  if(!response.ok)log(cancelNotice,'error');
  await followTask(id);
 }catch(error){
  cancelNotice='取消结果尚未确认，请用“重新连接”查询；不会自动重复取消。';
  try{await followTask(id);}catch(queryError){currentTask={...currentTask,cancel_allowed:false};connectionError(queryError);}
 }finally{cancelSubmitting=false;renderCancel(currentTask);}
}
document.getElementById('cancelTask').onclick=cancelQueuedTask;
