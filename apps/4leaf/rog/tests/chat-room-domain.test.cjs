'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {makeCreationSession}=require('../chat-room-domain.js');
const input={name:'원작 방',region:'north',district:'샤이닝 브리즈',password:'secretpass'};
function harness(override={}){
 const calls=[];let fail=0,ready=true;
 const opts={
  create:async d=>{calls.push('CREATE');return {room:{id:'server-431',...d}}},
  join:async id=>{calls.push('JOIN');if(fail-->0)throw Error('503 temporary')},
  enter:async()=>{calls.push('ENTER');return true},
  leave:async()=>{calls.push('LEAVE')},
  connect:async()=>{calls.push('CONNECT')},
  isReady:()=>ready,
  isActive:()=>true,
  onCreated:()=>calls.push('ACK'),...override
 };
 return {session:makeCreationSession(opts),calls,fail(n){fail=n},offline(){ready=false}};
}
test('CREATE, JOIN and scene entry commit exactly once',async()=>{
 const h=harness();const out=await h.session.submit(input);
 assert.equal(out.room.id,'server-431');
 assert.deepEqual(h.calls,['CREATE','ACK','JOIN','ENTER']);
 await h.session.submit(input);assert.equal(h.calls.filter(x=>x==='CREATE').length,1);
});
test('JOIN 503 retries original ACK without a second CREATE',async()=>{
 const h=harness();h.fail(1);
 await assert.rejects(h.session.submit(input),/503 temporary/);
 assert.equal(h.session.state.phase,'retryable');assert.equal(h.session.room.id,'server-431');
 await h.session.submit({...input,name:'changed'});
 assert.equal(h.calls.filter(x=>x==='CREATE').length,1);
 assert.equal(h.calls.filter(x=>x==='JOIN').length,2);
 assert.equal(h.session.draft.name,input.name);
});
test('double submit coalesces in flight CREATE',async()=>{
 let unblock;const gate=new Promise(done=>unblock=done);
 const h=harness({create:async d=>{h.calls.push('CREATE');await gate;return {room:{id:'server-431',...d}}}});
 const one=h.session.submit(input),two=h.session.submit(input);
 unblock();await Promise.all([one,two]);
 assert.equal(h.calls.filter(x=>x==='CREATE').length,1);
 assert.equal(h.calls.filter(x=>x==='JOIN').length,1);
});
test('server session reconnected before JOIN',async()=>{
 const h=harness({isReady:()=>false,connect:async()=>h.calls.push('CONNECT')});
 await h.session.submit(input);assert.ok(h.calls.indexOf('CONNECT')<h.calls.indexOf('JOIN'));
});
test('screen entry rejection leaves server before retry',async()=>{
 let fail=true;
 const h=harness({enter:async()=>{h.calls.push('ENTER');if(fail){fail=false;return false}return true}});
 await assert.rejects(h.session.submit(input),/scene entry failed/);
 assert.ok(h.calls.includes('LEAVE'));await h.session.submit(input);
 assert.equal(h.calls.filter(x=>x==='CREATE').length,1);
});
test('closed form cannot JOIN after delayed CREATE ACK',async()=>{
 let unblock;const gate=new Promise(done=>unblock=done);
 const h=harness({create:async d=>{h.calls.push('CREATE');await gate;return {room:{id:'server-431',...d}}}});
 const running=h.session.submit(input);h.session.dispose();unblock();
 await assert.rejects(running,/dialog closed/);
 assert.equal(h.calls.filter(x=>x==='JOIN').length,0);
 assert.equal(h.session.room.id,'server-431');
});
test('lost CREATE acknowledgement reuses one logical request, never duplicates a room',async()=>{
 const requests=[],ack={room:{id:'created-once',name:'Original Room'}};
 let n=0;
 const h=harness({
  newRequestId:()=> 'b23a9ad3-51aa-48e3-a70f-9d2ca08db813',
  create:async payload=>{
   requests.push({...payload});
   if(n++===0)throw Error('Lost HTTP 201 after server commit');
   return ack;
  }
 });
 await assert.rejects(h.session.submit(input),/Lost HTTP 201/);
 assert.equal(h.session.state.phase,'retryable-create');
 assert.equal(h.session.room,null);
 const previousDraft=h.session.draft;
 await h.session.submit({...input,name:'changed after timeout'});
 assert.equal(requests.length,2);
 assert.deepEqual(requests[0],requests[1],
  'same room request must be replayed after an ambiguous lost acknowledgement');
 assert.equal(requests[0].createRequestId,'b23a9ad3-51aa-48e3-a70f-9d2ca08db813');
 assert.strictEqual(h.session.draft,previousDraft);
 assert.equal(h.session.room.id,'created-once');
});
test('definitive invalid CREATE permits a corrected new request',async()=>{
 let n=0;
 const ids=['a23a9ad3-51aa-48e3-a70f-9d2ca08db813',
  'a23a9ad3-51aa-48e3-a70f-9d2ca08db814'];
 const sent=[];
 const h=harness({
  newRequestId:()=>ids[n++],
  create:async data=>{
   sent.push({...data});
   if(sent.length===1){const err=Error('Bad name');err.status=400;throw err}
   return {room:{id:'corrected-room'}};
  }
 });
 await assert.rejects(h.session.submit(input),/Bad name/);
 assert.equal(h.session.draft,null);
 await h.session.submit({...input,name:'Corrected name'});
 assert.equal(sent[1].name,'Corrected name');
 assert.notEqual(sent[0].createRequestId,sent[1].createRequestId);
});
