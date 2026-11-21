const fs=require('fs'),vm=require('vm'),assert=require('assert');
async function scenario(disconnect=false){
 const elements={resumeTask:{},resumeNote:{},reconnect:{}};let posts=0,queries=0,offline=0,release;
 const context={document:{getElementById:id=>elements[id]},currentTask:{task_id:'synthetic',resume_allowed:true,failure_reason:'MemoryError'},fetch:async(url,opt)=>{assert.equal(opt.method,'POST');assert(url.endsWith('/resume'));posts++;if(disconnect)throw Error('lost response');return {ok:true,json:async()=>({task_id:'synthetic'})};},followTask:async id=>{queries++;if(disconnect)throw Error('offline');await new Promise(resolve=>release=resolve);},connectionError:()=>offline++};vm.createContext(context);vm.runInContext(fs.readFileSync('static/task_resume.js','utf8'),context);
 vm.runInContext('renderResume(currentTask)',context);assert.equal(elements.resumeTask.hidden,false);assert(elements.resumeNote.textContent.includes('先处理'));
 const first=vm.runInContext('continueTask()',context),second=vm.runInContext('continueTask()',context);await new Promise(resolve=>setImmediate(resolve));
 if(!disconnect){assert.equal(posts,1);context.currentTask={task_id:'synthetic',resume_allowed:false};release();}
 await Promise.all([first,second]);assert.equal(posts,1);assert.equal(queries,1);
 if(disconnect){assert.equal(offline,1);assert.equal(elements.resumeTask.hidden,true);}
 const ui=fs.readFileSync('static/research_ui.js','utf8');const reconnect=ui.match(/\$\('reconnect'\)\.onclick=\(\)=>\{[^\n]+/)[0];context.$=id=>elements[id];context.URLSearchParams=URLSearchParams;context.location={search:'?task=synthetic'};context.followTask=async()=>{queries++;};vm.runInContext(reconnect,context);elements.reconnect.onclick();await Promise.resolve();assert.equal(posts,1);assert.equal(queries,2);
}
(async()=>{await scenario();await scenario(true);console.log(JSON.stringify({single_post_on_double_click:true,disconnect_no_repost:true,reconnect_get_only:true,resource_hint:true,gpu_runs:0}));})().catch(e=>{console.error(e);process.exitCode=1;});
