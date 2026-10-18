#!/usr/bin/env node
'use strict';
// Canonical 4LEAF restoration backlog. Deliberately dependency-free.
// Git history + immutable intake/event prefixes prevent conversation-loss and
// accidental task deletion from silently rewriting the user's requirements.
const fs=require('node:fs');
const path=require('node:path');
const cp=require('node:child_process');
const ROOT=path.resolve(__dirname,'../../../..');
const FILE=path.resolve(__dirname,'../docs/RESTORATION_LEDGER.json');
const GIT_PATH='apps/4leaf/rog/docs/RESTORATION_LEDGER.json';
const STATUSES=['todo','in_progress','blocked','done'];
const PRIORITIES=['P0','P1','P2'];
const REQUIRED=[
 ...Array.from({length:10},(_,i)=>'M'+String(i).padStart(2,'0')),
 'P0-BOARD','P0-ACTOR','P0-PODIUM','P0-DICE','P0-CHAT',
 'P0-RELEASE','GOV-LEDGER'
];
const today=()=>new Date().toISOString().slice(0,10);
const read=()=>JSON.parse(fs.readFileSync(FILE,'utf8'));
const save=ledger=>{
 ledger.updatedAt=today();
 const target=FILE+'.tmp-'+process.pid;
 try{fs.writeFileSync(target,JSON.stringify(ledger,null,2)+'\n','utf8');fs.renameSync(target,FILE)}
 finally{if(fs.existsSync(target))fs.unlinkSync(target)}
};
const requireValid=(cond,message)=>{if(!cond)throw new Error(message)};
const obj=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const nonempty=v=>typeof v==='string'&&v.trim().length>0;
const deepEqual=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function validate(data,previous){
 requireValid(data.schemaVersion===1,'unsupported schemaVersion');
 requireValid(Array.isArray(data.tasks)&&Array.isArray(data.intake)&&Array.isArray(data.events),
  'tasks/intake/events must be arrays');
 const ids=new Set();
 for(const task of data.tasks){
  requireValid(obj(task)&&/^[A-Z][A-Z0-9-]{2,40}$/.test(task.id),'invalid task id');
  requireValid(!ids.has(task.id),'duplicate task id: '+task.id);ids.add(task.id);
  requireValid(PRIORITIES.includes(task.priority),'invalid priority: '+task.id);
  requireValid(STATUSES.includes(task.status),'invalid status: '+task.id);
  requireValid(nonempty(task.title)&&nonempty(task.current),'missing title/current: '+task.id);
  requireValid(Array.isArray(task.acceptance)&&task.acceptance.some(nonempty),
   'missing original acceptance criteria: '+task.id);
  requireValid(Array.isArray(task.evidence)&&task.evidence.every(nonempty),
   'invalid evidence list: '+task.id);
  requireValid(nonempty(task.evidenceLevel)&&nonempty(task.lastReviewed),
   'missing evidence status/date: '+task.id);
  if(task.status==='done'){
   const proof=task.verifiedAcceptance;
   requireValid(obj(proof)&&
     ['sourceComparison','implementation','runtimeTest','deployment'].every(k=>nonempty(proof[k])),
    'DO NOT mark done without original comparison, implementation, browser QA and deployed SHA: '+task.id);
  }
  if(task.status==='blocked')
   requireValid(nonempty(task.blocker)&&Array.isArray(task.alternatives)&&
     task.alternatives.some(nonempty),'blocked requires blocker and investigated alternatives: '+task.id);
 }
 for(const id of REQUIRED)requireValid(ids.has(id),'protected restoration requirement removed: '+id);
 const intakeIds=new Set();
 for(const req of data.intake){
  requireValid(obj(req)&&nonempty(req.id)&&nonempty(req.text)&&
    Array.isArray(req.taskIds)&&req.taskIds.length>0,'bad user request record');
  requireValid(!intakeIds.has(req.id),'duplicate request: '+req.id);intakeIds.add(req.id);
  for(const id of req.taskIds)requireValid(ids.has(id),'request refers to missing task: '+id);
 }
 for(let i=0;i<data.events.length;i++){
  const e=data.events[i];
  requireValid(obj(e)&&e.seq===i+1&&nonempty(e.date)&&nonempty(e.type),
   'event sequence must be strictly append-only: '+(i+1));
  if(e.taskId)requireValid(ids.has(e.taskId),'event refers to missing task');
  if(e.requestId)requireValid(intakeIds.has(e.requestId),'event refers to missing request');
 }
 if(previous){
  const oldTaskIds=new Set(previous.tasks.map(t=>t.id));
  for(const id of oldTaskIds)requireValid(ids.has(id),'previously registered task was deleted: '+id);
  requireValid(data.intake.length>=previous.intake.length,'user request history truncated');
  requireValid(data.events.length>=previous.events.length,'work history truncated');
  previous.intake.forEach((x,i)=>requireValid(deepEqual(x,data.intake[i]),
    'immutable user request changed: '+x.id));
  previous.events.forEach((x,i)=>requireValid(deepEqual(x,data.events[i]),
    'append-only work history changed at #'+(i+1)));
  const fresh=data.events.slice(previous.events.length);
  for(const id of ids)if(!oldTaskIds.has(id))
   requireValid(fresh.some(e=>e.type==='TASK_ADDED'&&e.taskId===id),
    'new task lacks registration event: '+id);
  for(let i=previous.intake.length;i<data.intake.length;i++)
   requireValid(fresh.some(e=>e.type==='REQUEST_REGISTERED'&&e.requestId===data.intake[i].id),
    'new intake lacks event: '+data.intake[i].id);
  for(const old of previous.tasks){
   const current=data.tasks.find(t=>t.id===old.id);
   if(current.status!==old.status)requireValid(fresh.some(e=>
    e.type==='STATUS_CHANGED'&&e.taskId===old.id&&e.from===old.status&&e.to===current.status),
     'task status changed without audit event: '+old.id);
  }
 }
 return data;
}
function against(ref){
 const result=cp.spawnSync('git',['show',ref+':'+GIT_PATH],
  {cwd:ROOT,encoding:'utf8',maxBuffer:8*1024*1024});
 if(result.status!==0){
  // No old ledger (first introduction). Never suppress other read errors.
  const found=cp.spawnSync('git',['cat-file','-e',ref+'^{commit}'],{cwd:ROOT});
  requireValid(found.status===0,'Git reference not found: '+ref);
  return null;
 }
 return JSON.parse(result.stdout);
}
function append(data,event){
 data.events.push({seq:data.events.length+1,date:today(),...event});
}
function idForRequest(data){
 const prefix='REQ-'+today().replaceAll('-','')+'-';
 const seq=data.intake.filter(e=>e.id.startsWith(prefix)).length+1;
 return prefix+String(seq).padStart(3,'0');
}
function report(data,onlyOpen=false,asJson=false){
 const rows=data.tasks.filter(t=>!onlyOpen||t.status!=='done')
   .sort((a,b)=>PRIORITIES.indexOf(a.priority)-PRIORITIES.indexOf(b.priority)||a.id.localeCompare(b.id));
 const counts=Object.fromEntries(STATUSES.map(s=>[s,data.tasks.filter(t=>t.status===s).length]));
 if(asJson){process.stdout.write(JSON.stringify({counts,tasks:rows},null,2)+'\n');return}
 console.log('4LEAF 원작 개발원장 | '+data.updatedAt+
  ' | 전체 '+data.tasks.length+' · 진행 '+counts.in_progress+' · 대기 '+counts.todo+
  ' · 장애 '+counts.blocked+' · 완료 '+counts.done);
 for(const task of rows)console.log(
  '['+task.status+']['+task.priority+'] '+task.id+' '+task.title+
  ' | '+task.acceptance[0]);
}
function main(argv){
 const cmd=argv[0]||'report';
 if(cmd==='report'||cmd==='open'){
  const data=validate(read());
  report(data,cmd==='open',argv.includes('--json'));return;
 }
 if(cmd==='check'){
  const pos=argv.indexOf('--against');
  const prev=pos<0?null:against(argv[pos+1]);
  validate(read(),prev);console.log('RESTORATION LEDGER CHECK PASS');return;
 }
 const data=validate(read());
 if(cmd==='add'){
  const [id,priority,milestone,title,criteria,context]=argv.slice(1);
  requireValid(id&&priority&&title&&criteria&&context,
   'usage: add ID P0|P1|P2 M04|- "title" "acceptance" "current"');
  requireValid(!data.tasks.some(t=>t.id===id),'existing ID: '+id);
  data.tasks.push({id,priority,title,status:'todo',milestone:milestone==='-'?null:milestone,
   current:context,acceptance:[criteria],evidence:[],
   evidenceLevel:'UNVERIFIED-ORIGINAL-EQUIVALENCE',lastReviewed:today(),verifiedAcceptance:null});
  append(data,{type:'TASK_ADDED',taskId:id,details:'New backlog task; not falsely marked complete'});
 }else if(cmd==='intake'){
  const [requestText,...ids]=argv.slice(1);
  requireValid(nonempty(requestText)&&ids.length>0,
   'usage: intake "exact user request" TASK-ID [TASK-ID ...]');
  for(const id of ids)requireValid(data.tasks.some(t=>t.id===id),'unknown task: '+id);
  const id=idForRequest(data);
  data.intake.push({id,date:today(),origin:'user',text:requestText,taskIds:[...new Set(ids)]});
  append(data,{type:'REQUEST_REGISTERED',requestId:id,taskIds:[...new Set(ids)]});
 }else if(cmd==='set'){
  const [id,status,...reasonParts]=argv.slice(1);
  const reason=reasonParts.join(' ').trim();
  requireValid(STATUSES.includes(status)&&nonempty(reason),
   'usage: set ID todo|in_progress|blocked|done "reason"');
  const task=data.tasks.find(t=>t.id===id);
  requireValid(task,'unknown task: '+id);
  requireValid(task.status!==status,'already '+status);
  const previous=task.status;
  task.status=status;task.lastReviewed=today();
  append(data,{type:'STATUS_CHANGED',taskId:id,from:previous,to:status,details:reason});
 }else throw new Error('command must be report, open, check, add, intake or set');
 validate(data);save(data);
 report(data,true);
}
try{main(process.argv.slice(2))}
catch(error){console.error('RESTORATION LEDGER ERROR:',error.message);process.exitCode=1}
