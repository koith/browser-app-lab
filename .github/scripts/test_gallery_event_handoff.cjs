'use strict';
const assert=require('node:assert/strict');
const run=require('./gallery_event_handoff.cjs');
const SHA='a'.repeat(40);
const ledger=(done=[1,2,4])=>Array.from({length:11},(_,i)=>
  '- ['+(done.includes(i+1)?'x':' ')+'] **G-'+String(i+1).padStart(2,'0')+'** work').join('\n');
const item=(status='completed',conclusion='success',sha=SHA)=>({
  id:42,head_sha:sha,head_branch:'main',status,conclusion,event:'workflow_dispatch'
});
async function simulate({event='push',body=ledger(),history={},pages=[item()],
  payload,ref='refs/heads/main'}={}) {
  const dispatched=[],logs=[];
  const p=payload||(event==='push'
    ?{repository:{full_name:'koith/browser-app-lab'}}
    :event==='issues'?{action:'edited',issue:{number:605}}
    :{action:'completed',workflow_run:{
      name:'Deploy static content to Pages',head_branch:'main',
      head_repository:{full_name:'koith/browser-app-lab'},event:'push'}});
  const github={rest:{
    issues:{get:async()=>({data:{body}})},
    git:{getRef:async()=>({data:{object:{sha:SHA}}})},
    actions:{
      listWorkflowRuns:async({workflow_id})=>({data:{
        workflow_runs:workflow_id==='static.yml'?pages:(history[workflow_id]||[])
      }}),
      createWorkflowDispatch:async x=>{dispatched.push(x.workflow_id);}
    }
  }};
  await run({github,context:{repo:{owner:'koith',repo:'browser-app-lab'},
    eventName:event,ref,payload:p},
    core:{info:x=>logs.push(x),notice:x=>logs.push(x)}});
  return {dispatched,logs};
}
(async()=>{
  let r=await simulate();
  assert.deepEqual(r.dispatched,['gallery-first-image-metrics.yml']);
  r=await simulate({pages:[item('in_progress',null)]});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({pages:[item('completed','failure')]});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({history:{'gallery-first-image-metrics.yml':[item('in_progress',null)]}});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({history:{'gallery-first-image-metrics.yml':[item()]}});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({event:'issues',body:ledger([1,2,4,9])});
  assert.deepEqual(r.dispatched,['gallery-quality-branding-entry-qa.yml']);
  r=await simulate({event:'issues',body:ledger([1,2,4,9,10])});
  assert.deepEqual(r.dispatched,['gallery-deployed-pages-photo-qa.yml']);
  r=await simulate({event:'issues',body:ledger([1,2,4,9,10,11])});
  assert.deepEqual(r.dispatched,['gallery-visual-quality-audit.yml']);
  r=await simulate({body:ledger([1,2,4,8,9,10,11])});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({event:'workflow_run',payload:{action:'completed',workflow_run:{
    name:'Deploy static content to Pages',head_branch:'main',
    head_repository:{full_name:'evil/fork'},event:'push'}}});
  assert.deepEqual(r.dispatched,[]);
  for(const name of ['gallery-direct-individual-archive.yml',
    'gallery-targeted-public-photo-crawl.yml','mimmi-official-archive.yml'])
    assert.ok(!r.dispatched.includes(name));
  console.log('PASS: 10 feature-first, pause, trust and no-duplicate tests');
})().catch(e=>{console.error(e);process.exitCode=1;});
