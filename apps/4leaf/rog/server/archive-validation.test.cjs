'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {validateArchive}=require('./archive-validation.cjs');
const {makeServer,REGIONS}=require('./central.cjs');
const valid=(region,district)=>Object.hasOwn(REGIONS,region)&&REGIONS[region].includes(district);
const ROOM='f1a3a9f4-c14f-4c89-a504-3a3f8514b3a9';
function fixture(){
 return {sequence:9,rooms:[{
  id:ROOM,name:'지켜야 할 한국어 방',region:'north',district:'샤이닝 브리즈',
  background:3,capacity:4,preset:false,created:1700000000000,ownerId:'owner',
  ownerTokenHash:'a'.repeat(64),passwordSalt:'b'.repeat(32),
  passwordHash:'c'.repeat(64)}],
  history:[[ROOM,[{id:'m1',seq:9,roomId:ROOM,sender:'owner',user:'사용자',
   text:'반드시 유지할 대화',time:1700000000001}]]]};
}
const clone=x=>structuredClone(x);
test('valid restored private room and Korean history are accepted without normalization or data loss',()=>{
 const snap=fixture(),copy=clone(snap);
 assert.equal(validateArchive(snap,valid),snap);
 assert.deepEqual(snap,copy,'validation must never edit authenticated data');
});
test('a single malformed room cannot be silently omitted from an encrypted snapshot',()=>{
 const base=fixture();
 const invalid=[
  s=>{s.rooms[0].region='invalid'},
  s=>{s.rooms[0].district='invalid'},
  s=>{s.rooms[0].id='leaf-public-north-3-0'},
  s=>{s.rooms[0].capacity=99},
  s=>{s.rooms[0].background=99},
  s=>{s.rooms[0].ownerTokenHash='bad'},
  s=>{s.rooms[0].passwordHash='bad'},
  s=>{s.rooms.push(clone(s.rooms[0]))},
 ];
 for(const change of invalid){const s=clone(base);change(s);
  assert.throws(()=>validateArchive(s,valid),/Invalid persisted ChatTown state/,
   'one damaged private room must fail the entire restore');
 }
});
test('a broken or mixed-up history cannot be silently truncated, reordered or rewritten',()=>{
 const invalid=[
  s=>{s.history[0][0]='unrelated-room'},
  s=>{s.history[0][1][0].roomId='leaf-public-north-3-0'},
  s=>{s.history[0][1][0].seq=10},
  s=>{s.history[0][1][0].seq=0},
  s=>{s.history[0][1][0].sender=null},
  s=>{s.history[0][1].push(clone(s.history[0][1][0]))},
  s=>{s.history.push(clone(s.history[0]))},
  s=>{s.history[0][1]=Array.from({length:201},(_,i)=>
    ({id:'m'+i,seq:i+1,roomId:ROOM,sender:'owner',user:'사용자',text:'대화',time:i}));
      s.sequence=201},
  s=>{s.history[0][1][0].clientMessageId='unsafe-key'},
  s=>{s.sequence=-1},
 ];
 for(const change of invalid){const s=fixture();change(s);
  assert.throws(()=>validateArchive(s,valid),/Invalid persisted ChatTown state/,
   'one damaged history must reject the entire archive without erasing it');
 }
});
test('public-room messages are valid even though canonical preset rooms are never archived as custom rooms',()=>{
 const s={sequence:1,rooms:[],history:[['leaf-public-north-3-0',[
  {id:'msg',seq:1,roomId:'leaf-public-north-3-0',sender:'person',user:'사용자',
   text:'원작 상설방',time:1700000000000}]]]};
 assert.equal(validateArchive(s,valid),s);
});
test('encrypted sender fingerprints are valid only with consistent identity; old archives stay loadable',()=>{
 const s=fixture();
 // Old archive versions did not persist a token fingerprint.
 assert.equal(validateArchive(s,valid),s);
 const authHash='e'.repeat(64);
 s.history[0][1][0].senderTokenHash=authHash;
 assert.equal(validateArchive(s,valid),s);
 const malformed=clone(s);malformed.history[0][1][0].senderTokenHash='not-a-token-fingerprint';
 assert.throws(()=>validateArchive(malformed,valid),/Invalid persisted ChatTown state/);
 const mismatch=clone(s);mismatch.sequence=10;
 mismatch.history[0][1].push({...mismatch.history[0][1][0],id:'m2',seq:10,
  sender:'different-person'});
 assert.throws(()=>validateArchive(mismatch,valid),/Invalid persisted ChatTown state/,
  'one bearer-token fingerprint cannot claim two original sender identities');
});
test('legacy mixed-case duplicate replay IDs cannot silently survive validation',()=>{
 const s=fixture(),id='abcd0123abcd0123abcd0123abcd0123';
 s.history[0][1][0].clientMessageId=id;
 s.sequence=10;
 s.history[0][1].push({...s.history[0][1][0],id:'m2',seq:10,
  clientMessageId:id.toUpperCase()});
 assert.throws(()=>validateArchive(s,valid),/Invalid persisted ChatTown state/,
  'same semantic replay ID under a different hex letter case is a collision');
});
test('global chat cursors and message identities cannot collide across rooms',()=>{
 const s=fixture(),publicId='leaf-public-north-3-0';
 s.sequence=10;
 s.history.push([publicId,[{id:'m2',seq:10,roomId:publicId,
  sender:'guest',user:'게스트',text:'다른 방의 대화',time:1700000000002}]]);
 assert.equal(validateArchive(s,valid),s,'distinct global cursors remain valid');
 const sameCursor=clone(s);sameCursor.history[1][1][0].seq=9;
 assert.throws(()=>validateArchive(sameCursor,valid),/duplicate global message sequence/,
  'cross-room cursor collision must fail the whole archive');
 const sameId=clone(s);sameId.history[1][1][0].id='m1';
 assert.throws(()=>validateArchive(sameId,valid),/duplicate message id across rooms/,
  'cross-room ID collision must fail the whole archive');
});
test('server serves 503 rather than accepting partial encrypted restore and never commits blank state',async t=>{
 const archive=fixture();archive.rooms[0].district='malformed';
 let saves=0;
 const app=makeServer({persistence:{
  kind:'qa-failclosed-archive',broken:false,
  load:async()=>clone(archive),save:async()=>{saves++}
 }});
 t.after(()=>app.close());
 await new Promise(ok=>app.server.listen(0,'127.0.0.1',ok));
 const base='http://127.0.0.1:'+app.server.address().port;
 for(const [method,endpoint,body] of [
  ['GET','/api/health'],['POST','/api/session',{nick:'restore-denied'}],
  ['GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈')]
 ]){
  const res=await fetch(base+endpoint,{method,headers:body?{'content-type':'application/json'}:{},
   body:body?JSON.stringify(body):undefined});
  assert.equal(res.status,503,method+' '+endpoint+' must fail closed');
 }
 assert.equal(saves,0,'rejected archive never generates a new authoritative write');
 assert.equal(app.inspect().rooms,0,'in-memory state never accepts partial rooms');
});
test('remote revision conflict reports unhealthy instead of an incorrect HTTP 200',async t=>{
 const app=makeServer({persistence:{
  kind:'mock-cas',broken:true,load:async()=>({sequence:0,rooms:[],history:[]}),
  save:async()=>{throw Error('cannot save')}
 }});
 t.after(()=>app.close());
 await new Promise(ok=>app.server.listen(0,'127.0.0.1',ok));
 const base='http://127.0.0.1:'+app.server.address().port;
 const r=await fetch(base+'/api/health'),j=await r.json();
 assert.equal(r.status,503);assert.equal(j.ok,false);
 assert.equal(j.archive,'remote-encrypted');
});
