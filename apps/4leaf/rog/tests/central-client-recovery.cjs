'use strict';
// Exercise the actual production browser client against the real Node authority
// without a mocked REST implementation or a 46-second wall-clock sleep.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {makeServer}=require('../server/central.cjs');

const clientSource=fs.readFileSync(path.join(__dirname,'../central-client.js'),'utf8');
async function fixture(){
 const clock={value:1700000000000};
 const app=makeServer({now:()=>clock.value});
 await new Promise(ok=>app.server.listen(0,'127.0.0.1',ok));
 const base='http://127.0.0.1:'+app.server.address().port;
 const timers=[];
 function browser(fetchOverride=fetch){
  const events=[],retryFns=[],handlers=new Map();
  const data=new Map(),window={
   LEAF_CENTRAL_API_URL:base,
   addEventListener:(kind,fn)=>handlers.set(kind,fn)
  };
  const storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,String(v))};
  vm.runInNewContext(clientSource,{
   window,document:{querySelector:()=>null},location:{protocol:'http:'},URL,
   sessionStorage:storage,fetch:fetchOverride,console,
   setInterval:fn=>{timers.push(fn);return timers.length},clearInterval:()=>{},
   setTimeout:fn=>{retryFns.push(fn);return retryFns.length},
   clearTimeout:()=>{}
  },{filename:'central-client.js'});
  const client=window.__LEAF_CENTRAL_CHAT__;
  client.subscribe(e=>events.push(e));
  return {client,events,token:()=>storage.getItem('leaf_central_session_v1'),
   retries:retryFns,online:()=>handlers.get('online')?.()};
 }
 const call=async(method,route,token,body)=>{
  const resp=await fetch(base+route,{method,headers:{
   ...(token?{authorization:'Bearer '+token}:{}),
   ...(body?{'content-type':'application/json'}:{})
  },body:body?JSON.stringify(body):undefined});
  return {code:resp.status,data:await resp.json()};
 };
 return {app,clock,browser,call,timers,close:()=>app.close()};
}
const ROOM_A='leaf-public-north-3-0',ROOM_B='leaf-public-north-3-1';

test('expired authority session reauthenticates and re-enters its real public room before sending',async t=>{
 const f=await fixture();t.after(f.close);
 const a=f.browser(),original=await a.client.connect('Alice');
 assert.equal(a.client.ready,true);
 await a.client.join(ROOM_A);
 assert.equal(a.client.joinedId,ROOM_A);
 await a.client.chat('before expiry');
 f.clock.value+=46001; // The server has now expired this browser's token.
 const posted=await a.client.chat('after expiry');
 assert.equal(posted.entry.text,'after expiry');
 assert.equal(a.client.ready,true);
 assert.equal(a.client.joinedId,ROOM_A,'no phantom room; admission is confirmed by the authority');
 assert.equal(a.client.id,original.id,
  'retained authenticated chat history restores the same original sender after TTL expiry');
 assert.ok(a.events.some(e=>e.type==='rejoined'&&e.room.id===ROOM_A));
 const state=await f.call('GET','/api/snapshot?after=0',a.token());
 assert.equal(state.code,200);
 assert.deepEqual(state.data.entries.map(e=>e.text),['before expiry','after expiry'],
  'authoritative message history is retained across the 45-second token reset');
 assert.equal(state.data.peers.length,1,'the expired peer has only one real replacement seat');
 // Verify through a fresh authenticated peer, not through browser-local history.
 const b=f.browser();await b.client.connect('Bob');await b.client.join(ROOM_A);
 const snapshot=await b.client.chat('bob confirmed');
 assert.equal(snapshot.entry.text,'bob confirmed');
 assert.equal(snapshot.entry.roomId,ROOM_A);
 assert.ok(a.events.filter(e=>e.type==='ready').length===2);
 assert.equal(a.token(),original.token,
  'sender bearer token is recovered only when an archived message fingerprint proves ownership');
});

test('a guest without retained messages receives a fresh identity after session expiry',async t=>{
 const f=await fixture();t.after(f.close);
 const a=f.browser(),original=await a.client.connect('QuietGuest');
 await a.client.join(ROOM_A);
 f.clock.value+=46001;
 const posted=await a.client.chat('first retained message after expiry');
 assert.equal(posted.entry.text,'first retained message after expiry');
 assert.notEqual(a.client.id,original.id,
  'a token without archived owner/message evidence cannot claim an old identity');
 assert.notEqual(a.token(),original.token,
  'unproven expired bearer tokens are rotated instead of blindly accepted');
 const state=await f.call('GET','/api/snapshot?after=0',a.token());
 assert.equal(state.code,200);
 assert.equal(state.data.entries.length,1);
 assert.equal(state.data.peers.length,1,'guest resumes only after real room re-admission');
});

test('changing real rooms resets the received-history cursor and never leaks prior-room history',async t=>{
 const f=await fixture();t.after(f.close);
 const a=f.browser(),b=f.browser();
 await a.client.connect('Alice');await b.client.connect('Bob');
 await b.client.join(ROOM_B);
 await b.client.chat('earlier message in B');
 await a.client.join(ROOM_A);
 await a.client.chat('later message in A');
 // A first poll advances the global cursor past B's earlier message.
 const observedA=new Promise(ok=>a.client.subscribe(e=>{
  if(e.type==='snapshot'&&e.roomId===ROOM_A)ok(e);
 }));
 f.timers[0]();await observedA;
 await a.client.join(ROOM_B); // must reset global "after" to zero
 const observedB=new Promise(ok=>a.client.subscribe(e=>{
  if(e.type==='snapshot'&&e.roomId===ROOM_B)ok(e);
 }));
 f.timers[0]();
 const state=await observedB;
 assert.ok(state.entries.some(e=>e.text==='earlier message in B'));
 assert.ok(state.entries.every(e=>e.roomId===ROOM_B));
 assert.equal(state.peers.length,2);
});

test('server refusal after expiry does not leave a fabricated joined room',async t=>{
 const f=await fixture();t.after(f.close);
 const a=f.browser(),b=f.browser(),c=f.browser();
 await a.client.connect('LostSeat');
 await b.client.connect('OtherSeat');
 await a.client.join(ROOM_A);
 f.clock.value+=46001; // a's seat is now expired
 await b.client.connect('OtherSeat');
 await b.client.join(ROOM_A);
 const activePeerId=b.client.id;
 await c.client.connect('ThirdSeat');
 await c.client.join(ROOM_A);
 // The standard room has 12 seats, so occupy all remaining slots using
 // independent authenticated clients (no synthetic/fabricated occupants).
 const newcomers=[];
 for(let n=0;n<10;n++){
  const user=f.browser();await user.client.connect('Peer'+n);
  await user.client.join(ROOM_A);newcomers.push(user);
 }
 await assert.rejects(a.client.chat('not delivered'),/Join a room first/);
 assert.equal(a.client.joinedId,null);
 assert.ok(a.events.some(e=>e.type==='membership-lost'&&e.roomId===ROOM_A));
 const bMessage=await b.client.chat('still live');
 assert.equal(bMessage.entry.text,'still live');
 assert.equal(activePeerId,b.client.id,'renewed active peer identity remains stable');
});


test('private room owner proves original token after TTL and reuses password only in live memory',async t=>{
 const f=await fixture();t.after(f.close);
 const a=f.browser();const auth=await a.client.connect('Owner');
 const created=await a.client.create({region:'north',district:'샤이닝 브리즈',
  name:'복구할 비밀방',capacity:2,background:3,password:'mySecret987'});
 const roomId=created.room.id;
 await a.client.join(roomId,'mySecret987');
 await a.client.chat('owner before');
 f.clock.value+=46001;
 const after=await a.client.chat('owner after');
 assert.equal(after.entry.roomId,roomId);
 assert.equal(a.client.joinedId,roomId);
 assert.equal(a.client.id,auth.id,
  'the password is not an owner credential; the archived SHA256 token fingerprint restores ownership');
 const check=await f.call('GET','/api/snapshot?after=0',a.token());
 assert.equal(check.code,200);
 assert.equal(check.data.room.isOwner,true);
 assert.deepEqual(check.data.entries.map(x=>x.text),['owner before','owner after']);
 const visitor=f.browser();await visitor.client.connect('Visitor');
 await assert.rejects(visitor.client.join(roomId,''),/Incorrect password/);
 assert.equal(visitor.client.joinedId,null);
});


test('cold free-tier authority 503 recovers without page reload or a duplicate polling timer',async t=>{
 const f=await fixture();t.after(f.close);
 let attempts=0;
 const a=f.browser(async(url,options)=>{
  if(String(url).endsWith('/api/session')&&attempts++===0)
   return new Response(JSON.stringify({error:'Authority is waking up'}),{status:503});
  return fetch(url,options);
 });
 await assert.rejects(a.client.connect('ColdStart'),/waking up/);
 assert.equal(a.client.ready,false,'an unconfirmed session is not reported connected');
 assert.equal(a.retries.length,1,'one bounded reconnect timer is scheduled');
 await a.retries.shift()();
 assert.equal(a.client.ready,true,'the same browser reconnects automatically');
 assert.equal(a.events.filter(e=>e.type==='ready').length,1);
 assert.equal(f.timers.length,1,'reconnection may install only one snapshot polling interval');
 await a.client.join(ROOM_A);
 const result=await a.client.chat('콜드스타트 복구 후 실제 채팅');
 assert.equal(result.entry.text,'콜드스타트 복구 후 실제 채팅');
});

test('manual disconnect cancels cold-start retries and does not create a ghost session',async t=>{
 const f=await fixture();t.after(f.close);
 let attempts=0;
 const a=f.browser(async(url,options)=>{
  if(String(url).endsWith('/api/session')&&attempts++===0)
   return new Response(JSON.stringify({error:'Service unavailable'}),{status:503});
  return fetch(url,options);
 });
 await assert.rejects(a.client.connect('Disconnected'),/unavailable/);
 assert.equal(a.retries.length,1);
 a.client.disconnect();
 await a.retries.shift()();
 assert.equal(a.client.ready,false);
 assert.equal(attempts,1,'manual disconnect does not silently authenticate again');
 assert.equal(f.timers.length,0,'no hidden polling after manual disconnect');
});
