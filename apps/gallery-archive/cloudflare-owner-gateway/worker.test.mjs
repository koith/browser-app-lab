import test from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import worker, { resetCatalogCacheForTests } from './worker.mjs';
globalThis.crypto ??= webcrypto;
const token = 'abcdefghijklmnopqrstuvwxyz_123456789012345';
const digest = value => createHash('sha256').update(value).digest('hex');
const bytes = Uint8Array.from([255, 216, 255, 224, 1, 2, 3, 4, 5]);
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
