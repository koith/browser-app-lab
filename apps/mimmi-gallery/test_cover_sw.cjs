'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, 'gallery-cover-sw.js'), 'utf8');
const gateway = 'https://mimmi-private-gallery-free.onrender.com';
const cover = (v, n=1) => gateway + '/api/cover/mimmi/safe-album/' + n + '?v=' + v.repeat(24);
const request = (url, destination='image') => ({url,method:'GET',destination});
const response = (code=200, mime='image/webp') => ({
  ok: code>=200&&code<300,status:code,
  headers:{get:key=>key.toLowerCase()==='content-type'?mime:null},
  clone(){return response(code,mime)}
});

function makeHarness(gatewayReply=response()) {
  const listeners={}, entries=new Map(), observed=[];
  const cache={
    match:async req=>entries.get(req.url),
    put:async (req, res)=>{entries.set(req.url,res)},
    keys:async ()=>[...entries.keys()].map(url=>({url})),
    delete:async req=>entries.delete(req.url)
  };
  const env={
    URL, caches:{open:async ()=>cache, keys:async()=>['mimmi-owner-saved-covers-v1'],
      delete:async()=>true},
    self:{addEventListener:(name, callback)=>{listeners[name]=callback},
      skipWaiting:async()=>{},clients:{claim:async()=>{}}},
    fetch:async (url, opts)=>{observed.push({url:typeof url==='string'?url:url.url,opts});if(gatewayReply instanceof Error)throw gatewayReply;return gatewayReply}
  };
  vm.runInNewContext(source,env,{filename:'gallery-cover-sw.js'});
  async function dispatch(req) {
    let output, pending=[];
    listeners.fetch({request:req,respondWith:p=>{output=p},waitUntil:p=>pending.push(p)});
    if(!output)return null;
    const result=await output;
    await Promise.all(pending);
    return result;
  }
  return {dispatch,entries,observed,listeners};
}
(async()=>{
  const h=makeHarness();
  const a=request(cover('a'));
  assert.equal((await h.dispatch(a)).status,200);
  assert.equal(h.entries.size,1);
  assert.equal(h.observed.length,1);
  assert.equal(h.observed[0].opts.mode,'cors');
  assert.equal(h.observed[0].opts.credentials,'omit');
  assert.equal((await h.dispatch(a)).status,200);
  assert.equal(h.observed.length,1,'second request must be served from private browser cache');

  for(const bad of [
    gateway+'/api/media/safe-album/1/original?v='+('a'.repeat(64)),
    cover('a').replace('v='+('a'.repeat(24)),'v=wrong'),
    'https://other.example/api/cover/mimmi/safe-album/1?v='+('a'.repeat(24)),
    cover('a').replace('/mimmi/','/yui/'),
    cover('a')+'&access_token=secret'
  ])assert.equal(await h.dispatch(request(bad)),null,'out-of-scope media not intercepted');

  const failure=makeHarness(response(503,'application/json'));
  await failure.dispatch(a);await failure.dispatch(a);
  assert.equal(failure.entries.size,0,'provider errors never enter browser cache');
  assert.equal(failure.observed.length,2,'bad response must not be cached');

  const broken=makeHarness(new Error('CORS unavailable'));
  await assert.rejects(()=>broken.dispatch(a),/CORS unavailable/);
  assert.equal(broken.entries.size,0);

  for(let n=1;n<=120;n++)await h.dispatch(request(cover('b',n)));
  assert.equal(h.entries.size,96,'bounded local cover cache');
  assert.equal(h.entries.has(a.url),false,'oldest cached cover should be evicted');

  console.log('MIMMI_COVER_RELOAD_CACHE_SCOPE_AND_SHA_VERSION_TEST_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
