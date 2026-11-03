'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {makeServer}=require('./central.cjs');
const {createAbuseGuard}=require('./abuse-guard.cjs');
async function serverFor(now){
 const app=makeServer({now});await new Promise(ok=>app.server.listen(0,'127.0.0.1',ok));
 const url='http://127.0.0.1:'+app.server.address().port;
 const call=async(route,body,token,headers={})=>{
  const response=await fetch(url+route,{method:'POST',
   headers:{'content-type':'application/json',
    ...(token?{authorization:'Bearer '+token}:{}),...headers},
   body:JSON.stringify(body)});
  return {code:response.status,data:await response.json()};
 };
 return {app,call,close:()=>app.close()};
}
const roomInfo={region:'north',district:'샤이닝 브리즈',name:'실제 게스트 테스트방',
 capacity:2,background:3,password:'correct-horse'};
test('network peer cannot evade 60/minute anonymous session bound with forged forwarded IPs',async t=>{
 let time=1700000000000;const f=await serverFor(()=>time);t.after(f.close);
 for(let i=0;i<60;i++){
  const x=await f.call('/api/session',{nick:'Visitor'+i},null,
   {'x-forwarded-for':'203.0.113.'+(i%200)});
  assert.equal(x.code,201);
 }
 const blocked=await f.call('/api/session',{nick:'Visitor61'},null,
  {'x-forwarded-for':'192.0.2.240'});
 assert.equal(blocked.code,429,'no spoofed proxy header bypasses the actual transport peer');
 time+=61000;
 const recovered=await f.call('/api/session',{nick:'VisitorRestart'},null);
 assert.equal(recovered.code,201,'quota automatically refills without user or server intervention');
});
test('room owner receives five creations per minute; the sixth is rejected without a ghost room',async t=>{
 const f=await serverFor(Date.now);t.after(f.close);
 const auth=await f.call('/api/session',{nick:'Owner'}),token=auth.data.token;
 for(let i=0;i<5;i++){
  const created=await f.call('/api/rooms',{...roomInfo,name:'방 '+i},token);
  assert.equal(created.code,201);
 }
 const denied=await f.call('/api/rooms',{...roomInfo,name:'과도한 추가 방'},token);
 assert.equal(denied.code,429);
 assert.equal(f.app.inspect().rooms,5);
});
test('repeated private-room password guesses throttle before expensive scrypt and preserve access rules',async t=>{
 const f=await serverFor(Date.now);t.after(f.close);
 const owner=(await f.call('/api/session',{nick:'Owner'})).data;
 const guest=(await f.call('/api/session',{nick:'Guest'})).data;
 const room=await f.call('/api/rooms',roomInfo,owner.token);
 assert.equal(room.code,201);const id=room.data.room.id;
 for(let i=0;i<6;i++){
  const wrong=await f.call('/api/rooms/'+id+'/join',{password:'incorrect'+i},guest.token);
  assert.equal(wrong.code,403);
 }
 assert.equal((await f.call('/api/rooms/'+id+'/join',{password:roomInfo.password},guest.token)).code,429);
 const ownerJoin=await f.call('/api/rooms/'+id+'/join',{password:roomInfo.password},owner.token);
 assert.equal(ownerJoin.code,200,'owner has independent quota and retains server-issued ownership');
});
test('bounded guard memory and aggregate chat budget across rotated guest sessions',()=>{
 let now=100000;
 const guard=createAbuseGuard({now:()=>now,maxEntries:12});
 for(let i=0;i<25;i++)guard.session('192.0.2.'+i);
 assert.ok(guard.inspect().trackedKeys<=12,'forged peer identities cannot grow unlimited guard state');
 for(let i=0;i<350;i++)guard.chat();
 assert.throws(()=>guard.chat(),e=>e.status===429);
 now+=6000;
 assert.doesNotThrow(()=>guard.chat(),'global chat budget resets at a short bounded window');
});
