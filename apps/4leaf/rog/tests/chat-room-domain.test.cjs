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