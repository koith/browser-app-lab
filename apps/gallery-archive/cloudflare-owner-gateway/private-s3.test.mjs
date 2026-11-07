import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash,webcrypto} from 'node:crypto';
import {createServer} from 'node:http';
import {once} from 'node:events';
import worker,{resetCatalogCacheForTests} from './worker.mjs';
import {privateS3Config,privateS3Bucket,signedS3Get} from './private-s3.mjs';
globalThis.crypto??=webcrypto;
const hash=b=>createHash('sha256').update(b).digest('hex');
const env={
 OWNER_S3_ENDPOINT:'https://s3.us-west-004.backblazeb2.com',OWNER_S3_BUCKET:'gallery-test',
 OWNER_S3_REGION:'us-west-004',OWNER_S3_ACCESS_KEY_ID:'exampleAccessKeyNotReal',
 OWNER_S3_SECRET_ACCESS_KEY:'exampleSecretNotARealAccount1234567890'
};
const bytes=readFileSync(new URL('../../yui-gallery/stored-albums/v04/001_bd8318cfe6e0.jpg',import.meta.url));
assert.equal(hash(bytes),'bd8318cfe6e08824b26e1d3206a33400502cec23dc4d82f2c8a039520e6ec90d');

test('only complete, HTTPS, provider-scoped private B2/R2 settings may make requests',()=>{
 assert.ok(privateS3Config(env));
 for(const change of [
  {OWNER_S3_ENDPOINT:'http://s3.us-west-004.backblazeb2.com'},
  {OWNER_S3_ENDPOINT:'https://private.example'},
  {OWNER_S3_ENDPOINT:'https://key:secret@s3.us-west-004.backblazeb2.com'},
  {OWNER_S3_ENDPOINT:env.OWNER_S3_ENDPOINT+'/other'},
  {OWNER_S3_ENDPOINT:env.OWNER_S3_ENDPOINT+'?token=anything'},
  {OWNER_S3_REGION:'different-region'},
  {OWNER_S3_BUCKET:'../foreign'},
  {OWNER_S3_SECRET_ACCESS_KEY:''}
 ])assert.equal(privateS3Bucket({...env,...change},()=>{throw Error('must not fetch')}),null);
});

test('SigV4 matches independent botocore S3 signer for spaces, B2 and R2 auto region',async()=>{
 const instant=new Date('2026-11-07T04:20:00.000Z');
 for(const target of [env,{...env,OWNER_S3_ENDPOINT:'https://'+'a'.repeat(32)+'.r2.cloudflarestorage.com',OWNER_S3_REGION:'auto'}]){
  const config=privateS3Config(target);
  const request=await signedS3Get(config,'yui/originals/example-album/one photo.jpg',instant);
  assert.ok(request.url.endsWith('/one%20photo.jpg'));
  const py=spawnSync(process.env.PYTHON_FOR_SIGV4||'python3',[new URL('./sigv4_reference.py',import.meta.url).pathname],{
   input:JSON.stringify({url:request.url,date:request.headers.get('x-amz-date'),key:config.key,secret:config.secret,region:config.region}),encoding:'utf8'
  });
  assert.equal(py.status,0,py.stderr);
  const reference=JSON.parse(py.stdout);
  assert.equal(request.headers.get('authorization'),reference.Authorization);
  assert.equal(request.headers.get('x-amz-content-sha256'),reference['X-Amz-Content-SHA256']);
 }
});

test('invalid object paths and ambiguous S3 failures never become an anonymous fallback',async()=>{
 for(const key of ['../photo.jpg','/photo.jpg','yui//photo.jpg','yui/../photo.jpg','yui/%2e%2e/photo.jpg','yui/\\photo.jpg'])
  await assert.rejects(signedS3Get(privateS3Config(env),key),/INVALID_PRIVATE_OBJECT_KEY/);
 for(const status of [401,403,451,500,503]){
  const store=privateS3Bucket(env,async()=>new Response('provider text must not escape',{status}));
  await assert.rejects(store.get('yui/metadata/catalog.json'),/PRIVATE_S3_READ_FAILED/);
 }
 assert.equal(await privateS3Bucket(env,async()=>new Response('',{status:404})).get('yui/metadata/catalog.json'),null);
});

test('declared and streamed limits reject oversized or truncated objects',async()=>{
 const large=privateS3Bucket(env,async()=>new Response('small',{headers:{'content-length':'9000000'}}));
 await assert.rejects(large.get('yui/metadata/catalog.json'),/PRIVATE_S3_OBJECT_TOO_LARGE/);
 const truncated=privateS3Bucket(env,async()=>new Response('small',{headers:{'content-length':'99'}}));
 await assert.rejects(truncated.get('yui/originals/album/1.jpg'),/PRIVATE_S3_LENGTH_MISMATCH/);
 const chunked=privateS3Bucket(env,async()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(6_000_001));c.close()}})));
 await assert.rejects(chunked.get('yui/metadata/catalog.json'),/PRIVATE_S3_OBJECT_TOO_LARGE/);
});

test('real local HTTP staging: automatic S3 adapter reads both catalogs and exact JPEG via signed requests',async()=>{
 resetCatalogCacheForTests();
 const objects=new Map();
 for(const model of ['mimmi','yui']){
  objects.set('/gallery-test/'+model+'/metadata/catalog.json',Buffer.from(JSON.stringify({schema_version:1,model,albums:[{id:'existing-album',images:[{
   number:1,key:'originals/existing-album/one photo.jpg',sha256:hash(bytes),bytes:bytes.length
  }]}]})));
  objects.set('/gallery-test/'+model+'/originals/existing-album/one%20photo.jpg',bytes);
 }
 const observed=[];
 const server=createServer((request,response)=>{
  observed.push({path:request.url,authorization:request.headers.authorization,date:request.headers['x-amz-date']});
  const body=objects.get(request.url);
  if(!request.headers.authorization?.startsWith('AWS4-HMAC-SHA256 ')){response.writeHead(403);response.end();return}
  if(!body){response.writeHead(404);response.end();return}
  response.writeHead(200,{'content-length':String(body.length),'content-type':request.url.endsWith('.jpg')?'image/jpeg':'application/json'});response.end(body);
 });
 server.listen(0,'127.0.0.1');await once(server,'listening');
 const local='http://127.0.0.1:'+server.address().port,originalFetch=globalThis.fetch;
 globalThis.fetch=async request=>{
  assert.equal(new URL(request.url).origin,env.OWNER_S3_ENDPOINT);
  assert.equal(request.redirect,'error');
  return originalFetch(local+new URL(request.url).pathname,{headers:request.headers,redirect:'error'});
 };
 try{
  const settings={...env,PAGE_ORIGIN:'https://koith.github.io',PAGES_READ_POLICY:'existing-sha-pinned-gallery',SIGNING_KEY:'private-worker-signing-key-0123456789abcdef'};
  for(const model of ['mimmi','yui']){
   const signed=await worker.fetch(new Request('https://gallery.example/api/v1/sign',{method:'POST',headers:{Origin:settings.PAGE_ORIGIN,'Content-Type':'application/json'},body:JSON.stringify({model,album:'existing-album',number:1,variant:'original',sha256:hash(bytes)})}),settings);
   assert.equal(signed.status,200);const data=await signed.json();
   assert.ok(!data.url.includes('backblazeb2'));assert.ok(!data.url.includes(settings.OWNER_S3_ACCESS_KEY_ID));
   const response=await worker.fetch(new Request(data.url),settings);
   assert.equal(response.status,200);assert.equal(response.headers.get('content-type'),'image/jpeg');
   assert.equal(hash(Buffer.from(await response.arrayBuffer())),hash(bytes));
  }
  assert.equal(observed.length,4,'Catalog cache must survive S3 adapter recreation');
  assert.ok(observed.every(x=>x.authorization&&x.date));
 }finally{globalThis.fetch=originalFetch;await new Promise(resolve=>server.close(resolve))}
});
