import test from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import {readFileSync} from 'node:fs';
import {pagesGateway} from './pages-client.mjs';
import worker, { resetCatalogCacheForTests } from './worker.mjs';
globalThis.crypto ??= webcrypto;
const token = 'abcdefghijklmnopqrstuvwxyz_123456789012345';
const digest = value => createHash('sha256').update(value).digest('hex');
// A real already-published original, not an image-magic placeholder.
const bytes = new Uint8Array(readFileSync(new URL('../../yui-gallery/stored-albums/v04/001_bd8318cfe6e0.jpg',import.meta.url)));
assert.equal(digest(bytes),'bd8318cfe6e08824b26e1d3206a33400502cec23dc4d82f2c8a039520e6ec90d');
const makeEnv = (bad = false) => {
  const store = new Map();
  const photos = ['mimmi', 'yui'].map(model => ({
    schema_version: 1, model,
    albums: [{ id: 'example-photo-album', images: [{
      number: 1, key: 'originals/example-photo-album/one photo.jpg',
      sha256: digest(bytes), bytes: bytes.length
    }] }]
  }));
  for (const p of photos) {
    store.set(p.model + '/metadata/catalog.json', new TextEncoder().encode(JSON.stringify(p)));
    store.set(p.model + '/originals/example-photo-album/one photo.jpg', bad && p.model === 'mimmi' ? bytes.map(x => x ^ 1) : bytes);
  }
  const reads = [];
  return {
    env: {
      PAGE_ORIGIN: 'https://koith.github.io',
      SIGNING_KEY: 'signing-secret-not-shared-with-pages-0123456789',
      VIEWER_TOKEN_SHA256: digest(token),
      ARCHIVE_BUCKET: { async get(key) {
        reads.push(key);
        const b = store.get(key);
        return b ? { size: b.length, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset+b.byteLength),
          text: async () => new TextDecoder().decode(b) } : null;
      } }
    }, store, reads
  };
};
const request = (url, method='GET', body=null, authorization=null, origin='https://koith.github.io') =>
  new Request(url, { method, headers: {
    ...(origin ? { Origin: origin } : {}),
    ...(authorization ? { Authorization: 'Bearer '+authorization } : {}),
    ...(body ? { 'Content-Type': 'application/json' } : {})
  }, ...(body ? { body: JSON.stringify(body) } : {}) });
const endpoint = 'https://private-gallery.example';
async function signed(env, model) {
  const r = await worker.fetch(request(endpoint+'/api/v1/sign', 'POST',
    { model, album:'example-photo-album', number:1, variant:'original' }, token), env);
  assert.equal(r.status, 200);
  return (await r.json()).url;
}
test('no configured R2: safe fail closed, no billed read', async () => {
  const { env, reads } = makeEnv(); delete env.ARCHIVE_BUCKET;
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign'),env)).status,503);
  assert.equal(reads.length,0);
});
test('wrong origin or bearer cannot sign or read private photo', async () => {
  resetCatalogCacheForTests();
  const { env, reads } = makeEnv();
  const photo = { model:'mimmi',album:'example-photo-album',number:1,variant:'original' };
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','POST',photo,token,'https://evil.example'),env)).status,403);
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','POST',photo,'wrong-token-abcdefghijklmnopqrstuvwxyz'),env)).status,401);
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/media/mimmi/example-photo-album/1/original'),env)).status,403);
  assert.equal(reads.length,0);
});
test('both models: sign, R2 exact SHA readback, image type and CORS', async () => {
  resetCatalogCacheForTests();
  const { env } = makeEnv();
  for (const model of ['mimmi','yui']) {
    const url = await signed(env,model);
    const r = await worker.fetch(request(url),env);
    assert.equal(r.status,200); assert.equal(r.headers.get('content-type'),'image/jpeg');
    assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://koith.github.io');
    assert.deepEqual(new Uint8Array(await r.arrayBuffer()),bytes);
  }
});
test('tampered signature never reads private originals', async () => {
  resetCatalogCacheForTests();
  const { env,reads } = makeEnv();
  const u = new URL(await signed(env,'yui'));
  const before = reads.length;
  u.searchParams.set('h', '0'.repeat(64));
  assert.equal((await worker.fetch(request(u.href),env)).status,403);
  assert.equal(reads.length,before);
});
test('existing R2 same-length different SHA is rejected fail-closed', async () => {
  resetCatalogCacheForTests();
  const { env } = makeEnv(true);
  const url = await signed(env,'mimmi');
  const r = await worker.fetch(request(url),env);
  assert.equal(r.status,502); assert.equal((await r.json()).error,'STORAGE_MISMATCH');
});
test('CORS preflight never exposes secret headers to foreign origin', async () => {
  const {env}=makeEnv();
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','OPTIONS',null,null,'https://evil.example'),env)).status,403);
  const good = await worker.fetch(request(endpoint+'/api/v1/sign','OPTIONS'),env);
  assert.equal(good.status,204);
  assert.equal(good.headers.get('Access-Control-Allow-Origin'),'https://koith.github.io');
});

test('canonical catalog refuses cross-album or preview namespace substitutions', async () => {
  resetCatalogCacheForTests();
  const { env,store } = makeEnv();
  for (const model of ['mimmi','yui']) {
    const key=model+'/metadata/catalog.json';
    const original=JSON.parse(new TextDecoder().decode(store.get(key)));
    original.albums[0].images[0].key='originals/another-album/photo.jpg';
    store.set(key,new TextEncoder().encode(JSON.stringify(original)));
  }
  const req=request(endpoint+'/api/v1/sign','POST',
    {model:'mimmi',album:'example-photo-album',number:1,variant:'original'},token);
  assert.equal((await worker.fetch(req,env)).status,404);
});

test('Pages mode is explicit; known photo SHA grants the existing keyless read without bucket secrets',async()=>{
  resetCatalogCacheForTests();const {env,reads}=makeEnv();
  const p={model:'yui',album:'example-photo-album',number:1,variant:'original',sha256:digest(bytes)};
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','POST',p),env)).status,401);
  env.PAGES_READ_POLICY='existing-sha-pinned-gallery';delete env.VIEWER_TOKEN_SHA256;
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','POST',{...p,sha256:'0'.repeat(64)}),env)).status,403);
  const before=reads.length;
  assert.equal((await worker.fetch(request(endpoint+'/api/v1/sign','POST',p,null,'https://evil.example'),env)).status,403);
  assert.equal(reads.length,before);
  const signed=await worker.fetch(request(endpoint+'/api/v1/sign','POST',p),env);
  assert.equal(signed.status,200);
  const url=(await signed.json()).url;
  const raw=await worker.fetch(request(url,'GET',null,null,null),env);
  assert.equal(raw.status,200);assert.equal(digest(new Uint8Array(await raw.arrayBuffer())),digest(bytes));
});

test('Pages client: both models use signed actual originals, deduplicate calls and never send a bearer',async()=>{
  resetCatalogCacheForTests();const {env}=makeEnv();env.PAGES_READ_POLICY='existing-sha-pinned-gallery';
  delete env.VIEWER_TOKEN_SHA256;
  for(const model of ['mimmi','yui']){
    let calls=0;
    const client=pagesGateway({endpoint,model,fetcher:async(url,init)=>{
      calls++;assert.equal(init.credentials,'omit');assert.equal(init.headers.Authorization,undefined);
      return worker.fetch(new Request(url,{...init,headers:{...init.headers,Origin:'https://koith.github.io'}}),env);
    }});
    const photo={ownerAlbum:'example-photo-album',storageNumber:1,number:50,sha256:digest(bytes),bytes:bytes.length};
    const [a,b]=await Promise.all([client.asset(photo),client.asset(photo,'cover')]);
    assert.equal(a,b);assert.equal(calls,1);assert.ok(!a.includes('originals/'));
    const response=await worker.fetch(request(a),env);
    assert.equal(response.status,200);assert.deepEqual(new Uint8Array(await response.arrayBuffer()),bytes);
  }
});

test('missing preview may use only its own verified original; bad auth never falls through',async()=>{
  resetCatalogCacheForTests();const {env}=makeEnv();env.PAGES_READ_POLICY='existing-sha-pinned-gallery';
  let calls=0;
  const photo={ownerAlbum:'example-photo-album',number:1,sha256:digest(bytes),bytes:bytes.length,
    preview:'previews/example-photo-album/absent.webp',preview_sha256:'a'.repeat(64),preview_bytes:123};
  const client=pagesGateway({endpoint,model:'yui',fetcher:(url,init)=>{
    calls++;return worker.fetch(new Request(url,{...init,headers:{...init.headers,Origin:'https://koith.github.io'}}),env);
  }});
  const url=await client.asset(photo,'preview');assert.equal(calls,2);assert.ok(url.includes('/original?'));
  assert.equal(await client.asset(photo,'cover'),url);assert.equal(calls,2);
  const denied=pagesGateway({endpoint,model:'yui',fetcher:async()=>new Response('',{status:401})});
  await assert.rejects(denied.asset(photo,'preview'),/GALLERY_GATEWAY_HTTP_401/);
});

test('Pages sign: one transient TypeError retries exact SHA request and returns real stored JPEG',async()=>{
  resetCatalogCacheForTests();const {env}=makeEnv();
  env.PAGES_READ_POLICY='existing-sha-pinned-gallery';
  const photo={ownerAlbum:'example-photo-album',number:1,
    sha256:digest(bytes),bytes:bytes.length};
  for(const model of ['mimmi','yui']){
    let calls=0;
    const client=pagesGateway({endpoint,model,fetcher:async(url,init)=>{
      calls++;
      assert.equal(new URL(url).pathname,'/api/v1/sign');
      assert.equal(init.credentials,'omit');
      assert.equal(init.headers.Authorization,undefined);
      const body=JSON.parse(init.body);
      assert.equal(body.model,model);
      assert.equal(body.sha256,digest(bytes));
      if(calls===1)throw new TypeError('synthetic transient network interruption');
      return worker.fetch(new Request(url,{...init,headers:{
        ...init.headers,Origin:'https://koith.github.io'}}),env);
    }});
    const [a,b]=await Promise.all([client.asset(photo,'original'),client.asset(photo,'cover')]);
    assert.equal(a,b,'same SHA requests must deduplicate despite transient network');
    assert.equal(calls,2,'only one retry is permitted');
    assert.deepEqual(new Uint8Array(await (await worker.fetch(request(a),env)).arrayBuffer()),bytes);
    assert.equal((new URL(a)).searchParams.size,4,'never append retry query to signed media URL');
  }
});

test('Pages sign: repeated network loss stops after two bounded retries; 401 and bad signature are not retried',async()=>{
  const photo={ownerAlbum:'example-photo-album',number:1,
    sha256:digest(bytes),bytes:bytes.length};
  let calls=0;
  const offline=pagesGateway({endpoint,model:'yui',fetcher:async()=>{
    calls++;throw new TypeError('network unavailable');
  }});
  await assert.rejects(offline.asset(photo),TypeError);
  assert.equal(calls,3,'at most two bounded network retries');
  calls=0;
  const denied=pagesGateway({endpoint,model:'yui',fetcher:async()=>{
    calls++;return new Response('',{status:403});
  }});
  await assert.rejects(denied.asset(photo),/GALLERY_GATEWAY_HTTP_403/);
  assert.equal(calls,1,'access-denied must not retry');
  calls=0;
  const malformed=pagesGateway({endpoint,model:'yui',fetcher:async()=>{
    calls++;return Response.json({url:'https://untrusted.example/foo',sha256:digest(bytes),
      bytes:bytes.length,expires_at:Math.floor(Date.now()/1000)+300});
  }});
  await assert.rejects(malformed.asset(photo),/INVALID_SIGNED_PHOTO/);
  assert.equal(calls,1,'invalid signed response must not retry');
});



test('Pages recovery re-signs same immutable owner original after a cached media 503',async()=>{
  resetCatalogCacheForTests();const {env}=makeEnv();
  env.PAGES_READ_POLICY='existing-sha-pinned-gallery';
  const photo={ownerAlbum:'example-photo-album',number:1,
    sha256:digest(bytes),bytes:bytes.length};
  for(const model of ['mimmi','yui']){
    let signs=0;
    const client=pagesGateway({endpoint,model,fetcher:(url,init)=>{
      signs++;
      assert.equal(init.credentials,'omit');
      assert.equal(JSON.parse(init.body).sha256,photo.sha256);
      return worker.fetch(new Request(url,{...init,headers:{
        ...init.headers,Origin:'https://koith.github.io'}}),env);
    }});
    const original=await client.asset(photo,'original');
    assert.equal(await client.asset(photo,'original'),original);
    assert.equal(signs,1,'regular reads should stay cached');
    const refreshed=await client.renew(photo,'original');
    assert.equal(signs,2,'recovery must contact Worker rather than reuse signed URL cache');
    const signed=new URL(refreshed);
    assert.deepEqual([...signed.searchParams.keys()].sort(),['b','e','h','s']);
    assert.equal(signed.searchParams.get('h'),photo.sha256);
    const response=await worker.fetch(request(refreshed),env);
    assert.equal(response.status,200);
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()),bytes);
  }
});

test('Pages recovery does not retry a denied or malicious signed response',async()=>{
  const photo={ownerAlbum:'example-photo-album',number:1,sha256:digest(bytes),bytes:bytes.length};
  let calls=0;
  const denied=pagesGateway({endpoint,model:'yui',fetcher:async()=>{
    calls++;return new Response('',{status:403});
  }});
  await assert.rejects(denied.renew(photo,'cover'),/GALLERY_GATEWAY_HTTP_403/);
  assert.equal(calls,1);
  await assert.rejects(denied.renew(photo,'not-variant'),/INVALID_PHOTO_VARIANT/);
  assert.equal(calls,1);
  let bad=0;
  const malformed=pagesGateway({endpoint,model:'mimmi',fetcher:async()=>{
    bad++;return Response.json({url:'https://different.example/forged',sha256:photo.sha256,
      bytes:photo.bytes,expires_at:Math.floor(Date.now()/1000)+300});
  }});
  await assert.rejects(malformed.renew(photo,'original'),/INVALID_SIGNED_PHOTO/);
  assert.equal(bad,1);
});

test('Pages client rejects an external, wrong-SHA or expired signed URL instead of exposing it',async()=>{
  const photo={ownerAlbum:'example-photo-album',number:1,sha256:digest(bytes),bytes:bytes.length};
  for(const mutation of ['host','sha','expiry']){
    resetCatalogCacheForTests();const {env}=makeEnv();env.PAGES_READ_POLICY='existing-sha-pinned-gallery';
    const client=pagesGateway({endpoint,model:'mimmi',fetcher:async(url,init)=>{
      const response=await worker.fetch(new Request(url,{...init,headers:{...init.headers,Origin:'https://koith.github.io'}}),env);
      const data=await response.json();
      if(mutation==='host')data.url=data.url.replace(endpoint,'https://unrelated.example');
      if(mutation==='sha')data.sha256='0'.repeat(64);
      if(mutation==='expiry')data.expires_at=1;
      return Response.json(data);
    }});
    await assert.rejects(client.asset(photo),/INVALID_SIGNED_PHOTO/);
  }
});
