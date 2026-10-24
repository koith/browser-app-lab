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
 assert.deepEqual(alice.position,{x:19,y:83},
  '2002 ChatRoom original background 3 source-aligned slots must be the server-authoritative snapped position');
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

test('unresponsive devices release seats at the server TTL without fictional occupants',async t=>{
 let instant=1700000000000;
 const {app,call,auth}=await open({now:()=>instant});
 t.after(()=>app.close());
 const old=await auth('Disconnected');
 const room='leaf-public-north-3-2';
 assert.equal((await call('POST','/api/rooms/'+room+'/join',old.token,{})).code,200);
 instant+=46000;
 const newcomer=await auth('NewUser');
 const result=await call('GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),newcomer.token);
 assert.equal(result.data.rooms.find(r=>r.id===room)?.occupants,0,'expired browser sessions never count as real participants');
 assert.equal((await call('POST','/api/rooms/'+room+'/join',old.token,{})).code,401,'expired credentials cannot silently occupy a room');
 assert.equal((await call('POST','/api/rooms/'+room+'/join',newcomer.token,{})).code,200);
});

test('two distinct authenticated browsers atomically reserve non-overlapping real ChatRoom seat coordinates',async t=>{
 const {app,call,auth}=await open();t.after(()=>app.close());
 const [a,b]=await Promise.all([auth('OwnerOne'),auth('GuestTwo')]);
 const room='leaf-public-north-3-0';
 // An actual concurrent join must reserve different positions on the
 // central authority, not merely move overlapping CSS figures apart.
 const results=await Promise.all([a,b].map(user=>
  call('POST','/api/rooms/'+room+'/join',user.token,{})));
 assert.deepEqual(results.map(x=>x.code),[200,200]);
 const first=results.map(x=>x.data.position);
 assert.equal(new Set(first.map(pos=>pos.x+','+pos.y)).size,2);
 const wanted={x:20,y:63}; // original source public room0 uses background #2 slot 0
 const simultaneous=await Promise.all([a,b].map(user=>
  call('POST','/api/presence',user.token,{position:wanted})));
 assert.deepEqual(simultaneous.map(x=>x.code),[200,200]);
 assert.ok(simultaneous.every(x=>x.data.seat!==null));
 const snapshot=await call('GET','/api/snapshot?after=0',a.token);
 assert.equal(snapshot.data.peers.length,2);
 const seats=snapshot.data.peers.map(x=>x.position.x+','+x.position.y);
 assert.equal(new Set(seats).size,2,
  'simultaneous genuine clicks on the same native floor slot must yield separate authoritative seats');
 assert.ok(seats.includes('20,63'),'one actual participant receives original requested slot');
 assert.ok(snapshot.data.peers.every(p=>p.position.x>=0&&p.position.y<=100));
 await call('POST','/api/leave',a.token,{});
 const nowFree=await call('POST','/api/presence',b.token,{position:wanted});
 assert.deepEqual(nowFree.data.position,wanted,
  'the emptied real original room seat becomes available without synthetic avatars');
 const restored=await call('POST','/api/rooms/'+room+'/join',a.token,{});
 assert.equal(restored.code,200);
 assert.notDeepEqual(restored.data.position,nowFree.data.position,
  'the returning authenticated client may not retake another live occupant source slot');
});

test('owner transfers private ChatRoom to actual joined peer; kicked former owner cannot rejoin immediately',async t=>{
 let instant=1700000000000;
 const {app,call,auth}=await open({now:()=>instant});t.after(()=>app.close());
 const [owner,guest,outsider]=await Promise.all([auth('Owner'),auth('Guest'),auth('Outsider')]);
 const created=await call('POST','/api/rooms',owner.token,{
  region:'north',district:'샤이닝 브리즈',name:'방장 위임 검증',capacity:4,background:3,
  password:'secret123'
 });
 assert.equal(created.code,201);const id=created.data.room.id;
 for(const u of [owner,guest]){
  assert.equal((await call('POST','/api/rooms/'+id+'/join',u.token,{password:'secret123'})).code,200);
 }
 // Unauthorized outsiders and even joined guests cannot claim moderation.
 assert.equal((await call('POST','/api/rooms/'+id+'/transfer',outsider.token,{targetId:guest.id})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/kick',guest.token,{targetId:owner.id})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/transfer',owner.token,{targetId:outsider.id})).code,404);
 assert.equal((await call('POST','/api/rooms/'+id+'/transfer',owner.token,{targetId:owner.id})).code,400);
 const change=await call('POST','/api/rooms/'+id+'/transfer',owner.token,{targetId:guest.id});
 assert.equal(change.code,200);assert.equal(change.data.room.isOwner,false);
 assert.equal((await call('GET','/api/snapshot',guest.token)).data.room.isOwner,true);
 assert.equal((await call('GET','/api/snapshot',owner.token)).data.room.isOwner,false);
 assert.equal((await call('POST','/api/rooms/'+id+'/close',owner.token,{})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/kick',owner.token,{targetId:guest.id})).code,403);
 const reload=await call('POST','/api/session',null,{resume:guest.token,nick:'Guest'});
 assert.equal(reload.data.room.isOwner,true);
 const kick=await call('POST','/api/rooms/'+id+'/kick',guest.token,{targetId:owner.id});
 assert.equal(kick.code,200);assert.equal(kick.data.targetId,owner.id);
 const kicked=await call('GET','/api/snapshot',owner.token);
 assert.equal(kicked.data.roomId,null,'server must immediately revoke kicked membership');
 assert.equal(kicked.data.peers.length,0,'kicked user cannot see private room occupants');
 assert.equal((await call('POST','/api/chat',owner.token,{text:'not in room'})).code,403);
 assert.equal((await call('POST','/api/rooms/'+id+'/join',owner.token,{password:'secret123'})).code,403,
  'an immediate retry must not silently undo an authenticated kick');
 instant+=121000;
 assert.equal((await call('POST','/api/rooms/'+id+'/join',owner.token,{password:'secret123'})).code,200,
  'after explicit temporary exclusion expiry joining is allowed again');
 const snapshot=await call('GET','/api/snapshot',guest.token);
 assert.equal(snapshot.data.peers.length,2);
 assert.equal(new Set(snapshot.data.peers.map(p=>p.position.x+','+p.position.y)).size,2,
  'authoritative native seats remain distinct after owner transfer/kick/rejoin');
 assert.equal((await call('POST','/api/rooms/'+id+'/close',guest.token,{})).code,200);
});
