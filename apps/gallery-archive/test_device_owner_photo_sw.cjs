'use strict';
// A realistic zero-network Service Worker regression, including HTTP 503 after
// one successful photo, SHA validation, owner separation, and quota eviction.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {createHash,webcrypto}=require('node:crypto');

const model=process.argv[2];
assert.ok(['mimmi','yui'].includes(model),'specify mimmi or yui');
const GATEWAY='https://mimmi-private-gallery-free.onrender.com';
const BASE=model==='mimmi' ? '/api/media/' : '/api/yui/media/';
const bytes=Buffer.from('owned-static-original-picture-exact-bytes-test-fixture');
const sha=createHash('sha256').update(bytes).digest('hex');
const url=(num=1,hash=sha,kind='original')=>GATEWAY+BASE+'known-album/'+num+'/'+kind+'?v='+hash;
const request=(value,more={})=>({
  url:value,method:'GET',destination:'image',credentials:'omit',...more
});
let providerStatus=200,content=bytes,ctype='image/jpeg';
const calls=[];
const stores=new Map();
const listeners={};
const getCache=(name)=>{
  if(!stores.has(name))stores.set(name,new Map());
  const data=stores.get(name);
  return {
    match:async req=>data.get(req.url)?.clone(),
    put:async (req,res)=>{data.set(req.url,res.clone())},
    keys:async ()=>[...data.keys()].map(url=>({url})),
    delete:async key=>data.delete(key.url),
  };
};
const scope={
  URL,Uint8Array,Response,
  caches:{
    open:async name=>getCache(name),
    keys:async()=>[...stores.keys()],
    delete:async name=>stores.delete(name)
  },
  self:{
    crypto:webcrypto,
    addEventListener:(type,cb)=>{listeners[type]=cb},
    skipWaiting:async()=>{},
    clients:{claim:async()=>{}}
  },
  fetch:async (value,options)=>{
    calls.push({url:typeof value==='string'?value:value.url,options});
    return new Response(providerStatus===200?content:Buffer.from('{"error_code":31326}'),{
      status:providerStatus,
      headers:{'content-type':providerStatus===200?ctype:'application/json',
        'content-length':String(content.length)}
    })
  }
};
vm.runInNewContext(
  fs.readFileSync(path.resolve(__dirname,'..',model+'-gallery','gallery-cover-sw.js'),'utf8'),
  scope,
  {filename:model+'-gallery/gallery-cover-sw.js'}
);
async function dispatch(req){
  let response=null;const pending=[];
  listeners.fetch({
    request:req,
    respondWith:p=>{response=p},
    waitUntil:p=>pending.push(p)
  });
  if(!response)return null;
  const result=await response;
  await Promise.all(pending);
  return result;
}
(async()=>{
  const first=await dispatch(request(url()));
  assert.equal(first.status,200,'first exact original should render');
  assert.deepEqual(Buffer.from(await first.arrayBuffer()),bytes);
  assert.equal(calls.length,1);
  let cached=stores.get(model+'-owner-verified-photos-v1');
  assert.equal(cached.size,1,'successfully verified photo must be saved locally');
  assert.equal(calls[0].options.credentials,'omit');
  assert.equal(calls[0].options.mode,'cors');

  providerStatus=503;
  const second=await dispatch(request(url()));
  assert.equal(second.status,200,'Render free sleeping must not break a saved photo');
  assert.deepEqual(Buffer.from(await second.arrayBuffer()),bytes);
  assert.equal(calls.length,1,'second photo must be served without contacting Render');

  const preview=await dispatch(request(url(2,sha,'preview')));
  assert.equal(preview.status,503,'uncached photo must report genuine upstream failure');
  assert.equal(cached.size,1,'provider error must not enter local cache');

  providerStatus=200;
  content=Buffer.from('different-image-corrupt-sha');
  const corrupt=await dispatch(request(url(3)));
  assert.equal(corrupt.status,502,'different SHA must not display as stored original');
  assert.equal(cached.size,1,'invalid bytes must not be cached');

  content=bytes;ctype='application/json';
  const disguised=await dispatch(request(url(4)));
  assert.equal(disguised.status,200,'gateway MIME response preserved without caching');
  assert.equal(cached.size,1,'nonimage responses never cached');
  ctype='image/jpeg';
  assert.equal(await dispatch(request(url(7,sha+'x'))),null,'invalid v not intercepted');
  assert.equal(await dispatch(request(url(8,sha)+'&token=leak')),null,'extra query rejected');
  assert.equal(await dispatch(request('https://evil.example'+BASE+'known-album/1/original?v='+sha)),null);
  const otherPrefix=model==='mimmi'?'/api/yui/media/':'/api/media/';
  assert.equal(await dispatch(request(GATEWAY+otherPrefix+'known-album/1/original?v='+sha)),null,'other owner never cached');
  assert.equal(await dispatch(request(url(9),{credentials:'include'})),null,'credentialed request never intercepted');
  assert.equal(await dispatch(request(url(9),{destination:'script'})),null,'nonphoto request never intercepted');

  // All URLs are SHA-versioned; count limit bounds device storage use.
  for(let n=10;n<120;n++)assert.equal((await dispatch(request(url(n)))).status,200);
  assert.equal(cached.size,96,'device-only photo count must be capped at 96');
  assert.equal(cached.has(url()),false,'least recently inserted photo evicted');
  const recent=await dispatch(request(url(119)));
  assert.equal(recent.status,200);
  assert.equal(calls.length,1+1+1+1+110,'cached latest photo avoids another network call');
  console.log(model.toUpperCase()+'_DEVICE_OWNER_PHOTO_SHA_CACHE_RESTART_503_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
