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
 let failWrites=false,delayMs=0;
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
   rows.set(body.slot,{...body});return respond([{...body}],201);
  }
  if(method==='PATCH'){
   const row=rows.get(slot);
   if(!row||u.searchParams.get('revision')!=='eq.'+row.revision)return respond([]);
   rows.set(slot,{...row,...body});return respond([{...row,...body}]);
  }
  throw Error('Unknown mock REST call '+method);
  }catch(error){console.error('Mock storage transport failure:',error.stack);throw error}
 };
 return {fetch,rows,setFailed:b=>{failWrites=b},setDelay:n=>{delayMs=n}};
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
test('network commit failure sends 503 and cannot expose a phantom accepted message',async t=>{
 const db=database(),f=await appFor(db);t.after(()=>f.close());
 const a=await f.session('A'),id='leaf-public-north-3-0';
 assert.equal((await f.call('POST','/api/rooms/'+id+'/join',a.token,{})).status,200);
 db.setFailed(true);
 const denied=await f.call('POST','/api/chat',a.token,{text:'절대로 저장되지 않아야 할 기록'});
 assert.equal(denied.status,503);
 const unseen=await f.call('GET','/api/snapshot?after=0',a.token);
 assert.deepEqual(unseen.data.entries,[],'failed remote commit is rolled back before peer reads');
 db.setFailed(false);
 const accepted=await f.call('POST','/api/chat',a.token,{text:'복구 후 진짜 채팅'});
 assert.equal(accepted.status,201);
 assert.deepEqual((await f.call('GET','/api/snapshot?after=0',a.token)).data.entries.map(x=>x.text),
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
 assert.equal((await f.call('GET','/api/snapshot?after=0',a.token)).data.entries.length,1);
 assert.equal((await f.call('POST','/api/chat',a.token,{text:'재시작 전 추가 쓰기 금지'})).status,503);
});
