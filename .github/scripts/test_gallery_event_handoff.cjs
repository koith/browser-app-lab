'use strict';
const assert=require('node:assert/strict');
const run=require('./gallery_event_handoff.cjs');

const SHA='a'.repeat(40), OLD='b'.repeat(40);
const ledger=()=>Array.from({length:11},(_,i)=>
  '- ['+([1,2,4].includes(i+1)?'x':' ')+'] **G-'+String(i+1).padStart(2,'0')+'** work').join('\n');
const collector={
  name:'Gallery Direct Individual Photo Collection and Verified Storage',
  event:'workflow_dispatch',head_branch:'main',
  head_repository:{full_name:'koith/browser-app-lab'}
};
function row(sha=SHA,status='completed',conclusion='success',date='2026-11-04T01:00:00Z') {
  return {head_sha:sha,head_branch:'main',status,conclusion,event:'workflow_dispatch',
    created_at:date,updated_at:date,id:17};
}
async function simulate({event='push',history={},body=ledger(),payload=null,changed=false,jobs=[]}={}) {
  const dispatched=[],logs=[];
  const p=payload||(event==='push'
    ?{repository:{full_name:'koith/browser-app-lab'}}
    :event==='issues'?{action:'edited',issue:{number:605}}:
      {action:'completed',workflow_run:collector});
  const github={rest:{
    issues:{get:async()=>({data:{body}})},
    git:{getRef:async()=>({data:{object:{sha:SHA}}})},
    actions:{
      listWorkflowRuns:async({workflow_id})=>({data:{workflow_runs:history[workflow_id]||[]}}),
      createWorkflowDispatch:async({workflow_id})=>{dispatched.push(workflow_id);},
      listJobsForWorkflowRun:async()=>({data:{jobs}})
    },
    repos:{compareCommitsWithBasehead:async()=>({data:{files:changed?
      [{filename:'apps/mimmi-gallery/owner-index.json'}]:[]}})}
  }};
  await run({github,context:{
    repo:{owner:'koith',repo:'browser-app-lab'},eventName:event,
    payload:p,ref:'refs/heads/main'},core:{
      info:x=>logs.push(x),notice:x=>logs.push(x)}});
  return {dispatched,logs};
}
(async()=>{
  let r=await simulate();assert.deepEqual(r.dispatched,['gallery-direct-individual-archive.yml']);
  r=await simulate({event:'workflow_run',history:{'gallery-direct-individual-archive.yml':[row()]}});
  assert.deepEqual(r.dispatched,['gallery-reverse-full-corpus-ab.yml']);
  r=await simulate({history:{'gallery-direct-individual-archive.yml':[row(SHA,'in_progress',null)]}});
  assert.deepEqual(r.dispatched,[]);
  r=await simulate({event:'workflow_run',payload:{action:'completed',workflow_run:
    {...collector,head_repository:{full_name:'outsider/repo'}}}});
  assert.deepEqual(r.dispatched,[]);
  const nextBody=ledger().replace('- [ ] **G-03**','- [x] **G-03**');
  r=await simulate({event:'issues',body:nextBody,history:{
    'gallery-direct-individual-archive.yml':[row()]},payload:{action:'edited',
    issue:{number:605},changes:{body:{from:ledger()}}}});
  assert.deepEqual(r.dispatched,['gallery-direct-individual-archive.yml']);
  r=await simulate({event:'workflow_run',history:{
    'gallery-direct-individual-archive.yml':[row(OLD)],
    'static.yml':[row(SHA)]},changed:true});
  assert.deepEqual(r.dispatched,['gallery-newly-stored-photo-qa.yml']);
  r=await simulate({event:'workflow_run',history:{
    'gallery-direct-individual-archive.yml':[row(OLD)],
    'static.yml':[row(SHA)],
    'gallery-deployed-pages-photo-qa.yml':[row(SHA)],
    'gallery-newly-stored-photo-qa.yml':[row(SHA)]
  },changed:true,jobs:[{name:'actual-deployed-originals (chromium)',conclusion:'success'}]});
  assert.deepEqual(r.dispatched,['gallery-reverse-full-corpus-ab.yml']);
  console.log('PASS: 7 event-driven handoff safety and progression tests');
})().catch(e=>{console.error(e);process.exitCode=1;});
