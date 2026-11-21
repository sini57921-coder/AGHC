let targetPanel=null,targetPanelKey=null;
function renderTargetSelection(task){
 if(!targetPanel){targetPanel=document.createElement('section');targetPanel.style.cssText='background:#fff;padding:16px;border:2px solid #2365c9;margin:12px 0;';document.querySelector('.results').prepend(targetPanel);}
 const choices=task.target_candidates||[];
 targetPanel.hidden=!choices.length;
 if(!choices.length){targetPanelKey=null;return;}
 if(targetPanelKey===task.task_id)return;
 targetPanelKey=task.task_id;targetPanel.replaceChildren();
 const heading=document.createElement('h2');heading.textContent='请选择本次要分析的人物';targetPanel.append(heading);
 const note=document.createElement('p');note.textContent='检测到多个人物。点击编号框，再确认目标。不会默认选择最大框；确认后所有阶段使用该目标裁剪。';targetPanel.append(note);
 const wrap=document.createElement('div');wrap.style.cssText='position:relative;max-width:420px;';targetPanel.append(wrap);
 const img=document.createElement('img');img.src=task.image_url;img.style.cssText='width:100%;display:block';wrap.append(img);
 let selected=null;
 const confirm=document.createElement('button');confirm.textContent='请先选择编号';confirm.disabled=true;
 img.onload=()=>{choices.forEach((choice,i)=>{const a=choice.box;const button=document.createElement('button');button.type='button';button.textContent=String(i+1);button.title='选择人物 '+(i+1);button.style.cssText=`position:absolute;left:${100*a[0]/img.naturalWidth}%;top:${100*a[1]/img.naturalHeight}%;width:${100*(a[2]-a[0])/img.naturalWidth}%;height:${100*(a[3]-a[1])/img.naturalHeight}%;border:3px solid #ffae00;background:transparent;color:#111;font-weight:bold;text-align:left;vertical-align:top;min-width:20px;min-height:24px;padding:0;`;
 button.onclick=()=>{selected=i;for(const el of wrap.querySelectorAll('button'))el.style.borderColor='#ffae00';button.style.borderColor='#146cff';confirm.disabled=false;confirm.textContent='确认人物 '+(i+1)+' 并开始分析';};wrap.append(button);});};
 targetPanel.append(confirm);
 confirm.onclick=async()=>{if(selected===null)return;confirm.disabled=true;confirm.textContent='正在提交目标';try{const response=await fetch('/api/tasks/'+task.task_id+'/target',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:selected})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'提交失败');await followTask(data.task_id);}catch(error){confirm.disabled=false;confirm.textContent='提交失败：'+error.message;}};
}
