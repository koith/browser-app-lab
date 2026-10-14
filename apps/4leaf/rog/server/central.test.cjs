'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {mkdtempSync,readFileSync,existsSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const path=require('node:path');
const {makeServer,REGIONS}=require('./central.cjs');
async function open(options={}){
 const app=makeServer(options);
 await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+app.server.address().port;
 async function call(method,route,token,data,headers={}){
  const res=await fetch(base+route,{method,headers:{
   ...(token?{authorization:'Bearer '+token}:{}),
   ...(data?{'content-type':'application/json'}:{}),...headers
  },body:data?JSON.stringify(data):undefined});
  return {code:res.status,data:await res.json()};
 }
 async function auth(nick){
  const res=await call('POST','/api/session',null,{nick});
  assert.equal(res.code,201);return res.data;
 }
 return {app,call,auth};
}
test('16 original ChatTown districts expose 8 persistent, unoccupied rooms each',async t=>{
 const {app,call,auth}=await open();t.after(()=>app.close());
 const user=await auth('Tester');
 for(const [region,districts] of Object.entries(REGIONS)){
  for(const [index,district] of districts.entries()){
   const res=await call('GET','/api/rooms?region='+region+'&district='+encodeURIComponent(district),user.token);
   assert.equal(res.code,200);
   assert.equal(res.data.rooms.length,8);
   assert.ok(res.data.rooms.every(r=>r.id.startsWith('leaf-public-'+region+'-'+index+'-')&&r.occupants===0));
  }
 }
});
test('authoritative capacity blocks 13th simultaneous device and admits it after vacancy',async t=>{
 const {app,call,auth}=await open();t.after(()=>app.close());
 const users=await Promise.all(Array.from({length:13},(_,i)=>auth('p'+i)));
 const id='leaf-public-north-3-0';
 const joins=await Promise.all(users.map(u=>call('POST','/api/rooms/'+id+'/join',u.token,{})));
 assert.equal(joins.filter(x=>x.code===200).length,12);
 assert.equal(joins.filter(x=>x.code===409).length,1);
 let room=await call('GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),users[0].token);
 assert.equal(room.data.rooms[0].occupants,12);
 await call('POST','/api/leave',users[0].token,{});
 const excluded=users[joins.findIndex(x=>x.code===409)];
 assert.equal((await call('POST','/api/rooms/'+id+'/join',excluded.token,{})).code,200);
});
test('isolated messages and real peers, with remote character direction and snap position',async t=>{
 const {app,call,auth}=await open();t.after(()=>app.close());
 const a=await auth('Alice'),b=await auth('Bob'),spy=await auth('Spy');
 const room='leaf-public-south-0-1';
 assert.equal((await call('POST','/api/chat',spy.token,{text:'spoof'})).code,403);
 for(const u of [a,b])assert.equal((await call('POST','/api/rooms/'+room+'/join',u.token,{})).code,200);
 await call('POST','/api/presence',a.token,{nick:'Alice',avatar:4,facing:-1,position:{x:15,y:86}});
 assert.equal((await call('POST','/api/chat',a.token,{text:'실제 채팅 테스트'})).code,201);
 const see=await call('GET','/api/snapshot?after=0',b.token);
 assert.equal(see.data.entries.length,1);
 assert.equal(see.data.entries[0].text,'실제 채팅 테스트');
 assert.equal(see.data.peers.length,2);
 const alice=see.data.peers.find(x=>x.id===a.id);
 assert.equal(alice.facing,-1);assert.equal(alice.avatar,4);
 assert.deepEqual(alice.position,{x:15,y:86});
 const outside=await call('GET','/api/snapshot?after=0',spy.token);
 assert.deepEqual(outside.data.entries,[]);assert.deepEqual(outside.data.peers,[]);
});
test('room owner permissions, passwords, data durability, no leaked credentials, CORS',async t=>{
 const dir=mkdtempSync(path.join(tmpdir(),'4leaf-server-test-'));
 t.after(()=>rmSync(dir,{recursive:true,force:true}));
 const file=path.join(dir,'rooms.json');
 const {app,call,auth}=await open({storageFile:file,origins:'https://koith.github.io'});
 t.after(()=>app.close());
 const a=await auth('Owner'),b=await auth('Visitor');
 const r=await call('POST','/api/rooms',a.token,{
  region:'north',district:'샤이닝 브리즈',name:'비밀방',capacity:2,background:3,password:'123456abc'
 });
 assert.equal(r.code,201);assert.equal(r.data.room.locked,true);
 const id=r.data.room.id;
 assert.equal((await call('POST','/api/rooms/'+id+'/join',b.token,{password:'wrong'})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/join',b.token,{password:'123456abc'})).code,200);
 assert.equal((await call('POST','/api/rooms/'+id+'/close',b.token,{})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/join',a.token,{password:'123456abc'})).code,200);
 await call('POST','/api/chat',a.token,{text:'방 기록 저장'});
 assert.equal(existsSync(file),true);
 const stored=readFileSync(file,'utf8');
 assert.ok(!stored.includes('123456abc')&&!stored.includes(a.token));
 assert.equal((await call('GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),b.token,null,
  {origin:'https://evil.example'})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/close',a.token,{})).code,200);
 assert.equal((await call('GET','/api/snapshot',b.token)).data.roomId,null);
});

test('reload resumes live room and server-confirmed ownership without fabricating capacity',async t=>{
 const {app,call,auth}=await open();t.after(()=>app.close());
 const host=await auth('OriginalOwner');
 const built=await call('POST','/api/rooms',host.token,{
  name:'복구 가능한 채팅방',region:'north',district:'샤이닝 브리즈',
  capacity:2,background:3,password:'resumption-password'
 });
 assert.equal(built.code,201);
 assert.equal(built.data.room.isOwner,true,'only the authenticated owner gets owner flag');
 const id=built.data.room.id;
 assert.equal((await call('POST','/api/rooms/'+id+'/join',host.token,{password:'resumption-password'})).code,200);
 const guest=await auth('AnotherDevice');
 assert.equal((await call('POST','/api/rooms/'+id+'/join',guest.token,{password:'resumption-password'})).code,200);
 const reloaded=await call('POST','/api/session',null,{nick:'OriginalOwner',resume:host.token});
 assert.equal(reloaded.code,201);
 assert.equal(reloaded.data.id,host.id,'a browser refresh preserves the server-issued person ID');
 assert.equal(reloaded.data.token,host.token,'a browser refresh retains its credential');
 assert.equal(reloaded.data.room?.id,id,'the server confirms the previously joined room');
 assert.equal(reloaded.data.room?.isOwner,true,'owner controls persist after page reload');
 const listing=await call('GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),host.token);
 assert.equal(listing.data.rooms.find(r=>r.id===id)?.occupants,2,'reload did not increment the authoritative room count');
 const visitorListing=await call('GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),guest.token);
 assert.equal(visitorListing.data.rooms.find(r=>r.id===id)?.isOwner,false,'remote visitor is not represented as owner');
 const stranger=await call('POST','/api/session',null,{nick:'FakeOwner',resume:'a'.repeat(64)});
 assert.notEqual(stranger.data.id,host.id,'made-up resume tokens cannot claim ownership');
 assert.equal((await call('POST','/api/rooms/'+id+'/close',host.token,{})).code,200);
});
