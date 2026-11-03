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
 function browser(){
  const data=new Map(),window={LEAF_CENTRAL_API_URL:base},events=[];
  const storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,String(v))};
  vm.runInNewContext(clientSource,{
   window,document:{querySelector:()=>null},location:{protocol:'http:'},URL,
   sessionStorage:storage,fetch,console,setInterval:fn=>{timers.push(fn);return timers.length},
   clearInterval:()=>{}
  },{filename:'central-client.js'});
  const client=window.__LEAF_CENTRAL_CHAT__;
  client.subscribe(e=>events.push(e));
  return {client,events,token:()=>storage.getItem('leaf_central_session_v1')};
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
 assert.notEqual(a.client.id,original.id,'expired non-owner identity is re-issued by the authority');
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
 assert.notEqual(a.token(),original.token,'rotated credential must be stored for later reload');
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
