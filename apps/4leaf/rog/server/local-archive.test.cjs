'use strict';
// Real HTTP server + real local filesystem: cold restart must not erase one
// damaged room or chat record. No production DB or user-owned files touched.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {mkdtempSync,readFileSync,writeFileSync,rmSync,existsSync}=require('node:fs');
const path=require('node:path');
const {tmpdir}=require('node:os');
const {makeServer}=require('./central.cjs');
const REGION='north',DISTRICT='샤이닝 브리즈';
function setup(t){
 const dir=mkdtempSync(path.join(tmpdir(),'4leaf-local-archive-'));
 t.after(()=>rmSync(dir,{recursive:true,force:true}));
 return path.join(dir,'state.json');
}
async function boot(file){
 const app=makeServer({storageFile:file});
 await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+app.server.address().port;
 const call=async(method,route,token,body)=>{
  const res=await fetch(base+route,{method,headers:{
   ...(token?{authorization:'Bearer '+token}:{}),
   ...(body?{'content-type':'application/json'}:{})},
   ...(body?{body:JSON.stringify(body)}:{})});
  return {status:res.status,data:await res.json()};
 };
 return {app,call,close:()=>app.close()};
}
const makeFixture=()=>({
 rooms:[{id:'room-archive-01',region:REGION,district:DISTRICT,name:'영구 채팅',
  capacity:4,background:3,preset:false,ownerId:'owner-01',
  ownerTokenHash:'a'.repeat(64),passwordSalt:'',passwordHash:'',created:1}],
 history:[['room-archive-01',[{id:'msg-01',seq:1,roomId:'room-archive-01',
  sender:'owner-01',user:'원더',text:'보존해야 할 대화',time:2}]]],
 sequence:1
});
test('actual local room, ownership and messages survive a complete Node authority restart',async t=>{
 const file=setup(t);
 let first=await boot(file);
 const owner=(await first.call('POST','/api/session',null,{nick:'원더'})).data;
 const created=await first.call('POST','/api/rooms',owner.token,{
  region:REGION,district:DISTRICT,name:'재시작해도 남는 원작방',
  capacity:4,background:2,password:'password123'
 });
 assert.equal(created.status,201);
 const id=created.data.room.id;
 assert.equal((await first.call('POST','/api/rooms/'+id+'/join',owner.token,
  {password:'password123'})).status,200);
 assert.equal((await first.call('POST','/api/chat',owner.token,{text:'삭제하면 안 되는 한글 기록'})).status,201);
 assert.ok(existsSync(file));
 const raw=readFileSync(file,'utf8');
 assert.ok(!raw.includes(owner.token)&&!raw.includes('password123'),
  'local snapshots may include hash verifiers but not plaintext secrets');
 await first.close();first=null;
 const recovered=await boot(file);t.after(()=>recovered.close());
 const restored=await recovered.call('POST','/api/session',null,{nick:'원더',resume:owner.token});
 assert.equal(restored.status,201);
 assert.equal(restored.data.id,owner.id);
 const listing=await recovered.call('GET','/api/rooms?region=north&district='+encodeURIComponent(DISTRICT),
  owner.token);
 assert.equal(listing.data.rooms.find(x=>x.id===id)?.isOwner,true);
 assert.equal((await recovered.call('POST','/api/rooms/'+id+'/join',owner.token,
  {password:'password123'})).status,200);
 const history=await recovered.call('GET','/api/snapshot?after=0',owner.token);
 assert.deepEqual(history.data.entries.map(x=>x.text),['삭제하면 안 되는 한글 기록']);
 assert.equal((await recovered.call('POST','/api/chat',owner.token,
  {text:'복원 완료 후 후속 대화'})).status,201);
 assert.deepEqual(JSON.parse(readFileSync(file,'utf8')).history.find(x=>x[0]===id)[1]
  .map(x=>x.text),['삭제하면 안 되는 한글 기록','복원 완료 후 후속 대화']);
});
test('damaged local JSON cannot boot as blank and cannot overwrite the original bytes',t=>{
 const file=setup(t),raw='{"rooms":[{"id":"incomplete"';
 writeFileSync(file,raw);
 assert.throws(()=>makeServer({storageFile:file}),SyntaxError);
 assert.equal(readFileSync(file,'utf8'),raw,'failure keeps the original bytes');
});
test('every structurally invalid local archive refuses startup rather than dropping records',t=>{
 const file=setup(t);
 const changes=[
  x=>{x.rooms[0].district='not a ChatTown district'},
  x=>{x.rooms[0].capacity=99},
  x=>{x.history[0][0]='orphaned-room'},
  x=>{x.history[0][1][0].roomId='wrong room'},
  x=>{x.history[0][1][0].seq=3},
  x=>{x.history[0][1][0].sender=null},
  x=>{x.rooms.push(structuredClone(x.rooms[0]))},
  x=>{x.history.push(structuredClone(x.history[0]))},
  x=>{x.history[0][1]=Array.from({length:201},(_,i)=>({
   id:'message-'+i,seq:i+1,roomId:'room-archive-01',
   sender:'owner-01',user:'원더',text:'대화 '+i,time:2+i}));x.sequence=201},
  x=>{x.sequence=-1}
 ];
 for(const alter of changes){
  const state=makeFixture();alter(state);
  const raw=JSON.stringify(state);writeFileSync(file,raw);
  assert.throws(()=>makeServer({storageFile:file}),/Invalid persisted ChatTown state/);
  assert.equal(readFileSync(file,'utf8'),raw,'no damage may be silently rewritten');
 }
});
test('interrupted temporary file cannot replace the last committed valid archive',async t=>{
 const file=setup(t),valid=makeFixture(),raw=JSON.stringify(valid);
 writeFileSync(file,raw);
 writeFileSync(file+'.99999.tmp','{broken incomplete transaction');
 const live=await boot(file);t.after(()=>live.close());
 const session=(await live.call('POST','/api/session',null,{nick:'다른 사람'})).data;
 assert.equal((await live.call('POST','/api/rooms/room-archive-01/join',
  session.token,{})).status,200);
 const result=await live.call('GET','/api/snapshot?after=0',session.token);
 assert.deepEqual(result.data.entries.map(e=>e.text),['보존해야 할 대화']);
 assert.equal(readFileSync(file,'utf8'),raw,'boot does not read or overwrite orphan tmp');
});
