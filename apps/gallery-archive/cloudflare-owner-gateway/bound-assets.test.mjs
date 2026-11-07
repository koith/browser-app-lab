import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash,webcrypto} from 'node:crypto';
import worker,{resetCatalogCacheForTests} from './worker.mjs';
import {boundAssetBucket} from './bound-assets.mjs';
globalThis.crypto??=webcrypto;
const raw=readFileSync(new URL('../../yui-gallery/stored-albums/v04/001_bd8318cfe6e0.jpg',import.meta.url));
const sha=createHash('sha256').update(raw).digest('hex');
const base='https://gallery.example',origin='https://koith.github.io';
function settings(){
 const calls=[];const catalogs={};
 for(const model of ['mimmi','yui'])catalogs[model]=JSON.stringify({schema_version:1,model,albums:[{id:'existing-album',images:[{number:1,key:'originals/existing-album/1_'+sha+'.jpg',sha256:sha,bytes:raw.length}]}]});
 return {calls,env:{PAGE_ORIGIN:origin,PAGES_READ_POLICY:'existing-sha-pinned-gallery',SIGNING_KEY:'worker-only-secret-01234567890123456789',ARCHIVE_CATALOGS:catalogs,
  ARCHIVE_ASSETS:{async fetch(request){
   calls.push(request.url);return new Response(raw,{headers:{'content-length':String(raw.length)}});
  }}
 }};
}
test('internal bound files: both model signatures read the unchanged actual JPEG',async()=>{
 resetCatalogCacheForTests();const {env,calls}=settings();
 for(const model of ['mimmi','yui']){
  const sign=await worker.fetch(new Request(base+'/api/v1/sign',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({model,album:'existing-album',number:1,variant:'original',sha256:sha})}),env);
  assert.equal(sign.status,200);const url=(await sign.json()).url;
  const photo=await worker.fetch(new Request(url),env);assert.equal(photo.status,200);
  assert.deepEqual(Buffer.from(await photo.arrayBuffer()),raw);
 }
 assert.equal(calls.length,2,'Private catalogs must not fetch exposed asset paths');
});
test('raw photo/catalog paths and foreign-origin signing never expose bound files',async()=>{
 const {env,calls}=settings();
 for(const path of ['/mimmi/metadata/catalog.json','/yui/originals/existing-album/1_'+sha+'.jpg']){
  const r=await worker.fetch(new Request(base+path),env);assert.equal(r.status,404);
 }
 const r=await worker.fetch(new Request(base+'/api/v1/sign',{method:'POST',headers:{Origin:'https://foreign.example'},body:'{}'}),env);
 assert.equal(r.status,403);assert.equal(calls.length,0);
});
test('bound asset integrity failure remains a failed image, never a new original',async()=>{
 resetCatalogCacheForTests();const {env}=settings();
 env.ARCHIVE_ASSETS.fetch=async()=>new Response(raw.map(x=>x^1));
 const signed=await worker.fetch(new Request(base+'/api/v1/sign',{method:'POST',headers:{Origin:origin},body:JSON.stringify({model:'yui',album:'existing-album',number:1,variant:'original',sha256:sha})}),env);
 const r=await worker.fetch(new Request((await signed.json()).url),env);assert.equal(r.status,502);
});
test('bound asset namespace, declared and streamed sizes are bounded',async()=>{
 const {env,calls}=settings();const bucket=boundAssetBucket(env);
 for(const key of ['../file','yui/originals/../file.jpg','yui/%2e%2e/file','yui/metadata/foreign.json'])await assert.rejects(bucket.get(key));
 assert.equal(calls.length,0);
 env.ARCHIVE_ASSETS.fetch=async()=>new Response('small',{headers:{'content-length':'9000000'}});
 await assert.rejects(bucket.get('yui/originals/existing-album/1.jpg'),/SIZE/);
 env.ARCHIVE_ASSETS.fetch=async()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(8_000_001));c.close()}}));
 await assert.rejects(bucket.get('yui/originals/existing-album/1.jpg'),/SIZE/);
});
