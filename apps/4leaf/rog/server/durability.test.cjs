'use strict';
// End-to-end durability checks against the REAL Node chat authority while
// replacing only the encrypted Supabase REST transport with an in-memory
// conditional-write PostgREST fixture. No paid database or production traffic.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createSupabasePersistence}=require('./persistence-supabase.cjs');
const {makeServer}=require('./central.cjs');
const KEY='ab'.repeat(32),SECRET='fake-backend-only-key',PROJECT_URL='https://fourleaf-qa.supabase.co';
function database(){
 const rows=new Map();
 let failWrites=false,delayMs=0,dropAfterCommit=false;
 const respond=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json'}});
 const fetch=async (url,opt)=>{
  try{
  const u=new URL(url),method=opt.method,slot=(u.searchParams.get('slot')||'').replace(/^eq\./,'')||'production';
  assert.equal(u.hostname,'fourleaf-qa.supabase.co');
  assert.equal(opt.headers.apikey,SECRET,'backend-only key is used, never leaked in a browser URL');
  if(method==='GET'){
   const row=rows.get(slot);
   return respond(row?[{...row}]:[]);
  }
  if(failWrites)return respond({error:'mock transient database failure'},503);
  if(delayMs)await new Promise(done=>setTimeout(done,delayMs));
  const body=JSON.parse(opt.body);
  if(method==='POST'){
   if(rows.has(body.slot))return respond([]);
   rows.set(body.slot,{...body});
   if(dropAfterCommit)throw Error('Simulated transport lost ACK after database POST committed');
   return respond([{...body}],201);
  }
  if(method==='PATCH'){
   const row=rows.get(slot);
   if(!row||u.searchParams.get('revision')!=='eq.'+row.revision)return respond([]);
   rows.set(slot,{...row,...body});
   if(dropAfterCommit)throw Error('Simulated transport lost ACK after database PATCH committed');
   return respond([{...row,...body}]);
  }
  throw Error('Unknown mock REST call '+method);
  }catch(error){console.error('Mock storage transport failure:',error.stack);throw error}
 };
 return {fetch,rows,setFailed:b=>{failWrites=b},setDelay:n=>{delayMs=n},
  setDropAfterCommit:b=>{dropAfterCommit=b}};
}
async function appFor(db,archiveKey=KEY){
 const persistence=createSupabasePersistence({url:PROJECT_URL,secret:SECRET,archiveKey,fetch:db.fetch});
 const app=makeServer({persistence});
 await new Promise(ok=>app.server.listen(0,'127.0.0.1',ok));
 const base='http://127.0.0.1:'+app.server.address().port;
 const call=async(method,route,token,data)=>{
  const response=await globalThis.fetch(base+route,{method,
   headers:{...(token?{authorization:'Bearer '+token}:{}),
    ...(data?{'content-type':'application/json'}:{})},
   body:data?JSON.stringify(data):undefined});
  return {status:response.status,data:await response.json()};
 };
 const session=async nick=>{
  const result=await call('POST','/api/session',null,{nick});
  assert.equal(result.status,201);return result.data;
 };
 return {app,call,session,persistence,close:()=>app.close()};
}
const info={region:'north',district:'샤이닝 브리즈',name:'지속적으로 저장할 방',background:3,capacity:4,password:'private-archive'};
test('encrypted real room/message snapshot survives full Node service restart with room ownership',async t=>{
 const db=database();let first=await appFor(db);
 t.after(async()=>{await first?.close()});
 const owner=await first.session('원본방장');
 const room=await first.call('POST','/api/rooms',owner.token,info);
 assert.equal(room.status,201);const id=room.data.room.id;
 assert.equal((await first.call('POST','/api/rooms/'+id+'/join',owner.token,{password:info.password})).status,200);
 assert.equal((await first.call('POST','/api/chat',owner.token,{text:'재시작에도 지킬 한국어 채팅'})).status,201);
 const dbRow=db.rows.get('production');
 assert.equal(dbRow.revision,2);
 assert.match(dbRow.sha256,/^[a-f0-9]{64}$/);
 assert.ok(!JSON.stringify(dbRow).includes('지킬 한국어'));
 assert.ok(!JSON.stringify(dbRow).includes(info.password));
 assert.ok(!JSON.stringify(dbRow).includes(owner.token));
 await first.close();first=null;
 const second=await appFor(db);t.after(()=>second.close());
 assert.equal((await second.call('GET','/api/health')).data.archive,'remote-encrypted');
 const restored=await second.call('POST','/api/session',null,{nick:'원본방장',resume:owner.token});
 assert.equal(restored.data.id,owner.id);
 const listing=await second.call('GET','/api/rooms?region=north&district='+encodeURIComponent(info.district),owner.token);
 assert.equal(listing.data.rooms.find(x=>x.id===id)?.isOwner,true,'room ownership survives cold restart');
 assert.equal((await second.call('POST','/api/rooms/'+id+'/join',owner.token,{password:info.password})).status,200);
 const history=await second.call('GET','/api/snapshot?after=0',owner.token);
 assert.deepEqual(history.data.entries.map(x=>x.text),['재시작에도 지킬 한국어 채팅']);
 const next=await second.call('POST','/api/chat',owner.token,{text:'복구 후 두 번째 메시지'});
 assert.equal(next.status,201);
 assert.ok(next.data.entry.seq>history.data.entries[0].seq);
 assert.equal(db.rows.get('production').revision,3);
});
test('failed remote write is quarantined until a verified cold restore, without phantom messages',async t=>{
 const db=database(),f=await appFor(db);t.after(()=>f.close());
 const a=await f.session('A'),id='leaf-public-north-3-0';
 assert.equal((await f.call('POST','/api/rooms/'+id+'/join',a.token,{})).status,200);
 db.setFailed(true);
 const denied=await f.call('POST','/api/chat',a.token,{text:'절대로 저장되지 않아야 할 기록'});
 assert.equal(denied.status,503);
 assert.equal(db.rows.size,0,'the simulated failure happened before any remote commit');
 // A 503 response from a remote proxy is NOT a transaction rollback proof:
 // keep all local reads and writes closed until reloading the real archive.
 assert.equal((await f.call('GET','/api/health')).status,503);
 assert.equal((await f.call('GET','/api/snapshot?after=0',a.token)).status,503);
 db.setFailed(false);
 assert.equal((await f.call('POST','/api/chat',a.token,{text:'unsafe reuse'})).status,503);
 const second=await appFor(db);t.after(()=>second.close());
 const recovered=await second.session('A again');
 assert.equal((await second.call('POST','/api/rooms/'+id+'/join',recovered.token,{})).status,200);
 assert.deepEqual((await second.call('GET','/api/snapshot?after=0',recovered.token)).data.entries,[]);
 const accepted=await second.call('POST','/api/chat',recovered.token,{text:'복구 후 진짜 채팅'});
 assert.equal(accepted.status,201);
 assert.deepEqual((await second.call('GET','/api/snapshot?after=0',recovered.token)).data.entries.map(x=>x.text),
  ['복구 후 진짜 채팅']);
});
test('corrupt archive or wrong encryption key cannot boot empty and overwrite existing state',async t=>{
 const db=database(),first=await appFor(db);t.after(()=>first.close());
 const a=await first.session('A');
 assert.equal((await first.call('POST','/api/rooms',a.token,info)).status,201);
 const original={...db.rows.get('production')};
 const bad=await appFor(db,'cd'.repeat(32));t.after(()=>bad.close());
 assert.equal((await bad.call('GET','/api/health')).status,503);
 assert.equal((await bad.call('POST','/api/session',null,{nick:'A'})).status,503);
 assert.deepEqual(db.rows.get('production'),original);
 await bad.close();
 db.rows.set('production',{...original,sha256:'0'.repeat(64)});
 const corrupt=await appFor(db);t.after(()=>corrupt.close());
 assert.equal((await corrupt.call('GET','/api/rooms')).status,503);
 assert.deepEqual(db.rows.get('production'),{...original,sha256:'0'.repeat(64)});
});
test('concurrent HTTP posts are serialized into distinct persisted CAS revisions',async t=>{
 const db=database();db.setDelay(8);
 const f=await appFor(db);t.after(()=>f.close());
 const a=await f.session('A'),id='leaf-public-north-3-0';
 await f.call('POST','/api/rooms/'+id+'/join',a.token,{});
 const responses=await Promise.all(Array.from({length:7},(_,i)=>
  f.call('POST','/api/chat',a.token,{text:'병렬메시지'+i})));
 assert.equal(responses.filter(x=>x.status===201).length,7);
 assert.equal(db.rows.get('production').revision,7);
 assert.equal(new Set(responses.map(x=>x.data.entry.seq)).size,7);
});
test('optimistic revision conflict never overwrites newer remote data',async t=>{
 const db=database(),f=await appFor(db);t.after(()=>f.close());
 const a=await f.session('A');await f.call('POST','/api/rooms/leaf-public-north-3-0/join',a.token,{});
 const accepted=await f.call('POST','/api/chat',a.token,{text:'원본 1'});
 assert.equal(accepted.status,201);
 const remote=db.rows.get('production');
 db.rows.set('production',{...remote,revision:remote.revision+1});
 const denied=await f.call('POST','/api/chat',a.token,{text:'충돌은 폐기'});
 assert.equal(denied.status,503);
 assert.equal(db.rows.get('production').revision,2);
 // With an unknown newer authoritative revision, returning the old local
 // copy would falsely claim no other writer changed that room.
 assert.equal((await f.call('GET','/api/health',null)).status,503);
 assert.equal((await f.call('GET','/api/snapshot?after=0',a.token)).status,503);
 assert.equal((await f.call('GET','/api/rooms?region=north&district='+encodeURIComponent(info.district),a.token)).status,503);
 assert.equal((await f.call('POST','/api/presence',a.token,{nick:'stale'})).status,503);
 assert.equal((await f.call('POST','/api/session',null,{nick:'new user'})).status,503);
 assert.equal((await f.call('POST','/api/chat',a.token,{text:'재시작 전 추가 쓰기 금지'})).status,503);
 assert.equal(db.rows.get('production').revision,2,'stale process never overwrites remote winner');
 // A new authority can fully reload the winning revision and resume traffic.
 const recovered=await appFor(db);t.after(()=>recovered.close());
 const newcomer=await recovered.session('RecoveredUser');
 assert.equal((await recovered.call('POST','/api/rooms/leaf-public-north-3-0/join',newcomer.token,{})).status,200);
 const afterRestart=await recovered.call('GET','/api/snapshot?after=0',newcomer.token);
 assert.deepEqual(afterRestart.data.entries.map(e=>e.text),['원본 1']);
 assert.equal((await recovered.call('POST','/api/chat',newcomer.token,{text:'새 권한자 복구 후 저장'})).status,201);
 assert.equal(db.rows.get('production').revision,3);
});


test('durable chat retries the same client message ID after full authority restart without a second write',async t=>{
 const db=database();let first=await appFor(db);
 t.after(async()=>{if(first)await first.close()});
 const owner=await first.session('ReplayOwner');
 const created=await first.call('POST','/api/rooms',owner.token,info);
 assert.equal(created.status,201);
 const id=created.data.room.id;
 await first.call('POST','/api/rooms/'+id+'/join',owner.token,{password:info.password});
 const clientMessageId='44f53b9a-51f1-4001-9abd-16560a3e582f';
 const before=await first.call('POST','/api/chat',owner.token,
  {text:'네트워크가 끊긴 직후 기록',clientMessageId});
 assert.equal(before.status,201);
 const revision=db.rows.get('production').revision;
 await first.close();first=null;
 const second=await appFor(db);t.after(()=>second.close());
 const recovered=await second.call('POST','/api/session',null,
  {nick:'ReplayOwner',resume:owner.token});
 assert.equal(recovered.status,201);
 await second.call('POST','/api/rooms/'+id+'/join',owner.token,{password:info.password});
 const replay=await second.call('POST','/api/chat',owner.token,
  {text:'네트워크가 끊긴 직후 기록',clientMessageId});
 assert.equal(replay.status,200);
 assert.equal(replay.data.entry.id,before.data.entry.id);
 assert.equal(db.rows.get('production').revision,revision,
  'replaying after a restart must not create another archive revision');
 assert.equal((await second.call('GET','/api/snapshot?after=0',owner.token)).data.entries.length,1);
});

test('public ChatRoom lost-ACK replay recovers the original sender after full encrypted server restart',async t=>{
 const db=database();let first=await appFor(db);
 t.after(async()=>{if(first)await first.close()});
 const author=await first.session('상설방 사용자');
 const room='leaf-public-north-3-1';
 assert.equal((await first.call('POST','/api/rooms/'+room+'/join',author.token,{})).status,200);
 const key='abdc883a-645f-4ad3-9f2c-415368d06217';
 const sent=await first.call('POST','/api/chat',author.token,
  {text:'상설방 재시작 전 실제 한 번 보낸 메시지',clientMessageId:key});
 assert.equal(sent.status,201);
 assert.equal(Object.hasOwn(sent.data.entry,'senderTokenHash'),false);
 assert.equal(Object.hasOwn(sent.data.entry,'clientMessageId'),false);
 const oldSnapshot=await first.call('GET','/api/snapshot?after=0',author.token);
 assert.equal(Object.hasOwn(oldSnapshot.data.entries[0],'senderTokenHash'),false);
 const savedRevision=db.rows.get('production').revision;
 assert.equal(savedRevision,1,'one real public chat mutation means one durable revision');
 assert.ok(!JSON.stringify(db.rows.get('production')).includes(author.token),
  'the bearer token is never written to remote storage in plaintext');
 await first.close();first=null;

 // Simulate a cold free-tier process restart that lost all in-memory sessions.
 const second=await appFor(db);t.after(()=>second.close());
 const recovered=await second.call('POST','/api/session',null,
  {nick:'상설방 사용자',resume:author.token});
 assert.equal(recovered.status,201);
 assert.equal(recovered.data.id,author.id,
  'encrypted message sender fingerprint proves previously issued guest identity');
 assert.equal(recovered.data.token,author.token,
  'a valid resumed public user keeps the same bearer token');
 assert.equal(recovered.data.room,null,
  'do not fabricate an occupied room after a cold restart');
 assert.equal((await second.call('POST','/api/rooms/'+room+'/join',author.token,{})).status,200);
 const replay=await second.call('POST','/api/chat',author.token,
  {text:'상설방 재시작 전 실제 한 번 보낸 메시지',clientMessageId:key});
 assert.equal(replay.status,200);
 assert.equal(replay.data.replayed,true);
 assert.equal(replay.data.entry.id,sent.data.entry.id);
 assert.equal(replay.data.entry.seq,sent.data.entry.seq);
 const replayUpper=await second.call('POST','/api/chat',author.token,
  {text:'상설방 재시작 전 실제 한 번 보낸 메시지',clientMessageId:key.toUpperCase()});
 assert.equal(replayUpper.status,200,'a case-variant retry after restart is the SAME message');
 assert.equal(replayUpper.data.entry.id,sent.data.entry.id);
 assert.equal(db.rows.get('production').revision,savedRevision,
  'lost-ACK retry cannot create a second room message or archive revision');

 // Guessing/choosing arbitrary 64-hex resume tokens must NOT claim a sender.
 const forged=await second.call('POST','/api/session',null,
  {nick:'타인',resume:'f'.repeat(64)});
 assert.equal(forged.status,201);
 assert.notEqual(forged.data.id,author.id);
 assert.notEqual(forged.data.token,'f'.repeat(64));
 assert.equal((await second.call('POST','/api/rooms/'+room+'/join',forged.data.token,{})).status,200);
 const stolenAck=await second.call('POST','/api/chat',forged.data.token,
  {text:'상설방 재시작 전 실제 한 번 보낸 메시지',clientMessageId:key});
 assert.equal(stolenAck.status,409,
  'a stolen/guessed ACK ID alone does not reveal another sender acknowledgement');
 assert.equal(db.rows.get('production').revision,savedRevision);
 const history=await second.call('GET','/api/snapshot?after=0',author.token);
 assert.deepEqual(history.data.entries.map(e=>e.text),
  ['상설방 재시작 전 실제 한 번 보낸 메시지']);
 assert.equal(Object.hasOwn(history.data.entries[0],'senderTokenHash'),false);
});


test('lost ACK after actual DB COMMIT prevents stale reads; restart recovers one original message',async t=>{
 const db=database(),first=await appFor(db);t.after(()=>first.close());
 const sender=await first.session('원본 전송자'),room='leaf-public-north-3-1';
 assert.equal((await first.call('POST','/api/rooms/'+room+'/join',sender.token,{})).status,200);
 const key='26dc9264-ab37-43e3-a903-a4cfabff9b33';
 const message='원격 DB에 실제 저장되었지만 응답이 끊긴 채팅';
 db.setDropAfterCommit(true);
 const uncertain=await first.call('POST','/api/chat',sender.token,
  {text:message,clientMessageId:key});
 assert.equal(uncertain.status,503,'an unknown HTTP ACK must never pretend success');
 assert.equal(db.rows.get('production')?.revision,1,'the DB DID commit before its ACK was dropped');
 assert.ok(!JSON.stringify(db.rows.get('production')).includes(message),
  'the original message remains encrypted');
 assert.equal(first.persistence.broken,true,'an ambiguous write response quarantines this server');
 db.setDropAfterCommit(false);
 for(const [method,url,token,body] of [
  ['GET','/api/health',null,null],
  ['GET','/api/snapshot?after=0',sender.token,null],
  ['GET','/api/rooms?region=north&district='+encodeURIComponent('샤이닝 브리즈'),sender.token,null],
  ['POST','/api/session',null,{nick:'new peer'}],
  ['POST','/api/chat',sender.token,{text:'must not overwrite winning revision'}]
 ]){
  assert.equal((await first.call(method,url,token,body)).status,503,
   'ambiguous COMMIT must fail closed on '+method+' '+url);
 }
 assert.equal(db.rows.get('production').revision,1,'stale authority never advances remote revision');
 // A completely new Node process reloads the encrypted winning revision.
 const recovered=await appFor(db);t.after(()=>recovered.close());
 const auth=await recovered.call('POST','/api/session',null,
  {nick:'원본 전송자',resume:sender.token});
 assert.equal(auth.status,201);
 assert.equal(auth.data.id,sender.id,'archived sender token fingerprint proves original sender');
 assert.equal((await recovered.call('POST','/api/rooms/'+room+'/join',sender.token,{})).status,200);
 const snapshot=await recovered.call('GET','/api/snapshot?after=0',sender.token);
 assert.deepEqual(snapshot.data.entries.map(x=>x.text),[message]);
 const replay=await recovered.call('POST','/api/chat',sender.token,
  {text:message,clientMessageId:key});
 assert.equal(replay.status,200);
 assert.equal(replay.data.replayed,true);
 assert.equal(replay.data.entry.id,snapshot.data.entries[0].id);
 assert.equal(db.rows.get('production').revision,1,
  'after restart, an ACK retry does not create a duplicate durable message');
});
