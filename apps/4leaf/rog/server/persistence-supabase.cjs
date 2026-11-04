'use strict';
// Server-only Supabase persistence. No secret may be embedded in browser code.
// Load must succeed before any chat requests, and failed writes fail closed.
const {gzipSync,gunzipSync}=require('node:zlib');
const {createHash,createCipheriv,createDecipheriv,randomBytes}=require('node:crypto');
const TABLE='fourleaf_chat_snapshots';
const digest=data=>createHash('sha256').update(data).digest('hex');
function storageError(message){const e=new Error(message);e.status=503;e.durable=true;return e;}
function createSupabasePersistence(options={}){
 const url=String(options.url||'').trim().replace(/\/+$/,'');
 const secret=String(options.secret||'').trim();
 const archiveKey=String(options.archiveKey||'').trim();
 const slot=String(options.slot||'production').trim();
 const fetcher=options.fetch||globalThis.fetch;
 if(!/^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(url))
  throw storageError('Durable store must be a Supabase HTTPS project');
 if(!secret||!/^[0-9a-f]{64}$/i.test(archiveKey))
  throw storageError('Durable store needs a server-only API key and 32-byte encryption key');
 if(!/^[a-z0-9_-]{1,48}$/.test(slot))throw storageError('Invalid archive slot');
 const key=Buffer.from(archiveKey,'hex'),rows=url+'/rest/v1/'+TABLE;
 let revision=0,loaded=false,broken=false;
 const headers=extra=>({
  apikey:secret,
  ...(/^[\w-]+\.[\w-]+\.[\w-]+$/.test(secret)?{authorization:'Bearer '+secret}:{}),
  accept:'application/json',...extra
 });
 async function request(method,query,body,extraHeaders={}){
  let response;
  try{
   response=await fetcher(rows+query,{
    method,headers:headers({...(body?{'content-type':'application/json'}:{}),...extraHeaders}),
    ...(body?{body:JSON.stringify(body)}:{}),
    signal:AbortSignal.timeout(15000),cache:'no-store'
   });
  }catch{throw storageError('Durable chat database is unreachable')}
  if(!response.ok)throw storageError('Durable chat database rejected '+method+' (HTTP '+response.status+')');
  try{
   const result=await response.json();
   if(!Array.isArray(result))throw Error('Non-array response');
   return result;
  }catch{throw storageError('Unexpected durable database response')}
 }
 function encode(snapshot){
  const plain=Buffer.from(JSON.stringify(snapshot));
  if(plain.length>24*1024*1024)
   throw storageError('Chat archive size limit reached; preserving current snapshot');
  const compressed=gzipSync(plain,{level:6});
  const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',key,iv);
  const sealed=Buffer.concat([iv,cipher.update(compressed),cipher.final(),cipher.getAuthTag()]);
  return {payload:sealed.toString('base64'),sha256:digest(sealed)};
 }
 function decode(record){
  if(!record||typeof record.payload!=='string'||!Number.isSafeInteger(Number(record.revision))||
   Number(record.revision)<1||!/^[a-f0-9]{64}$/.test(record.sha256||''))
   throw storageError('Invalid durable chat archive record');
  const bytes=Buffer.from(record.payload,'base64');
  if(bytes.length<29||digest(bytes)!==record.sha256)
   throw storageError('Durable chat archive checksum mismatch');
  try{
   const iv=bytes.subarray(0,12),tag=bytes.subarray(bytes.length-16);
   const decipher=createDecipheriv('aes-256-gcm',key,iv);
   decipher.setAuthTag(tag);
   const compressed=Buffer.concat([decipher.update(bytes.subarray(12,-16)),decipher.final()]);
   const snapshot=JSON.parse(gunzipSync(compressed,{maxOutputLength:24*1024*1024}).toString('utf8'));
   if(!snapshot||!Array.isArray(snapshot.rooms)||!Array.isArray(snapshot.history)||
    !Number.isSafeInteger(snapshot.sequence)||snapshot.sequence<0)
    throw Error('Unexpected snapshot');
   return snapshot;
  }catch{throw storageError('Archive decryption or structure failed; verify the encryption key')}
 }
 async function load(){
  const result=await request('GET','?slot=eq.'+encodeURIComponent(slot)+'&select=revision,payload,sha256');
  if(result.length>1)throw storageError('Duplicate archive rows');
  if(result.length===0){revision=0;loaded=true;return {rooms:[],history:[],sequence:0};}
  const snapshot=decode(result[0]);
  revision=Number(result[0].revision);loaded=true;return snapshot;
 }
 async function save(snapshot){
  if(!loaded||broken)throw storageError('Archive recovery required before write');
  const {payload,sha256}=encode(snapshot);
  let result;
  try{
   if(revision===0){
    result=await request('POST','?on_conflict=slot',
     {slot,revision:1,payload,sha256},
     {prefer:'resolution=ignore-duplicates,return=representation'});
   }else{
    result=await request('PATCH','?slot=eq.'+encodeURIComponent(slot)+'&revision=eq.'+revision,
     {revision:revision+1,payload,sha256},
     {prefer:'return=representation'});
   }
  }catch(error){
   // A write timeout, HTTP 5xx, or unreadable response does NOT prove
   // rollback: the remote revision may already have committed. Until the
   // authoritative row is reloaded after restart, both reads and writes
   // must fail closed instead of exposing the old in-memory snapshot.
   broken=true;
   throw error;
  }
  if(result.length!==1||Number(result[0].revision)!==revision+1){
   // A second writer may have won a CAS race. Never overwrite its revision.
   broken=true;
   throw storageError('Archive revision conflict; restart and recover remote state');
  }
  revision++;
  return revision;
 }
 return {load,save,get revision(){return revision},get broken(){return broken},kind:'supabase-aes256gcm'};
}
module.exports={createSupabasePersistence};
