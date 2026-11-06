/**
 * Render-independent, opt-in private R2 reader for the existing personal gallery.
 * No R2 objects or credentials are provisioned by this source file.
 * Pages receives only expiring, SHA-bound media URLs, never storage credentials.
 */
const ID = /^[a-z0-9][a-z0-9-]{1,99}$/;
const SHA = /^[a-f0-9]{64}$/;
const cache = new Map();
const enc = new TextEncoder();
const toHex = bytes => [...bytes].map(v => v.toString(16).padStart(2, '0')).join('');
const isHex = (v, n) => typeof v === 'string' && new RegExp('^[a-f0-9]{' + n + '}$').test(v);
const same = (a, b) => {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
};
const hash = async bytes => toHex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)));
const sign = async (secret, value) => {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return toHex(new Uint8Array(await crypto.subtle.sign('HMAC', key, enc.encode(value))));
};
function cors(req, env) {
  const allowed = env.PAGE_ORIGIN || 'https://koith.github.io';
  const origin = req.headers.get('Origin');
  return {
    'Vary': 'Origin',
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    ...(origin === allowed ? { 'Access-Control-Allow-Origin': allowed } : {}),
  };
}
function response(req, env, status, error) {
  return new Response(JSON.stringify({ error }), { status, headers: {
    ...cors(req, env), 'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  }});
}
function identifier(model, album, number, variant) {
  return (model === 'mimmi' || model === 'yui') && ID.test(album) &&
    Number.isSafeInteger(number) && number > 0 && number < 10000 &&
    (variant === 'original' || variant === 'preview');
}
function safeKey(key) {
  return typeof key === 'string' && key.length < 1024 &&
    /^[A-Za-z0-9._/-]+$/.test(key) && !key.startsWith('/') &&
    !key.split('/').some(seg => seg === '' || seg === '.' || seg === '..');
}
function imageType(bytes) {
  if (bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'image/jpeg';
  if (bytes.length >= 8 && [137,80,78,71,13,10,26,10].every((n,i) => bytes[i] === n)) return 'image/png';
  if (bytes.length >= 12 && String.fromCharCode(...bytes.slice(0,4)) === 'RIFF' &&
      String.fromCharCode(...bytes.slice(8,12)) === 'WEBP') return 'image/webp';
  return null;
}
async function catalog(env, model) {
  const now = Date.now(), hit = cache.get(model);
  if (hit && hit.expires > now && hit.bucket === env.ARCHIVE_BUCKET) return hit.value;
  const item = await env.ARCHIVE_BUCKET.get(model + '/metadata/catalog.json');
  if (!item || item.size < 20 || item.size > 6_000_000) return null;
  const raw = await item.text();
  let data;
  try { data = JSON.parse(raw); } catch { return null; }
  if (data?.schema_version !== 1 || data.model !== model || !Array.isArray(data.albums)) return null;
  const entries = new Map();
  for (const album of data.albums) {
    if (!ID.test(album?.id) || !Array.isArray(album.images)) return null;
    for (const photo of album.images) {
      const n = photo?.number;
      if (!Number.isSafeInteger(n) || n < 1 || n >= 10000 ||
          !isHex(photo.sha256, 64) || !Number.isSafeInteger(photo.bytes) ||
          photo.bytes < 1 || photo.bytes > 8_000_000 || !safeKey(photo.key)) return null;
      const id = album.id + ':' + n;
      if (entries.has(id)) return null;
      entries.set(id, {
        original: { key: photo.key, sha: photo.sha256, bytes: photo.bytes },
        preview: photo.preview && isHex(photo.preview_sha256, 64) &&
          Number.isSafeInteger(photo.preview_bytes) &&
          photo.preview_bytes > 0 && photo.preview_bytes <= 8_000_000 &&
          safeKey(photo.preview)
          ? { key: photo.preview, sha: photo.preview_sha256, bytes: photo.preview_bytes }
          : null
      });
    }
  }
  cache.set(model, { value: entries, bucket: env.ARCHIVE_BUCKET, expires: now + 30_000 });
  return entries;
}
async function entry(env, model, album, number, variant) {
  const map = await catalog(env, model);
  return map?.get(album + ':' + number)?.[variant] || null;
}
const payload = (model, album, number, variant, sha, bytes, expires) =>
  [model, album, number, variant, sha, bytes, expires].join('|');
async function authorize(req, env) {
  const auth = req.headers.get('Authorization') || '';
  const token = /^Bearer ([A-Za-z0-9_-]{32,256})$/.exec(auth)?.[1];
  if (!token || !isHex(env.VIEWER_TOKEN_SHA256, 64)) return false;
  return same(await hash(enc.encode(token)), env.VIEWER_TOKEN_SHA256);
}
async function handle(request, env) {
  const u = new URL(request.url), path = u.pathname, origin = request.headers.get('Origin');
  if (!env.ARCHIVE_BUCKET || typeof env.SIGNING_KEY !== 'string' ||
      env.SIGNING_KEY.length < 32 || !isHex(env.VIEWER_TOKEN_SHA256, 64)) {
    return response(request, env, 503, 'NOT_CONFIGURED');
  }
  if (request.method === 'OPTIONS') {
    if (origin !== (env.PAGE_ORIGIN || 'https://koith.github.io'))
      return response(request, env, 403, 'ORIGIN_DENIED');
    return new Response(null, { status: 204, headers: {
      ...cors(request, env), 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Authorization, Content-Type',
      'Access-Control-Max-Age': '3600'
    }});
  }
  if (path === '/api/v1/sign' && request.method === 'POST') {
    if (origin !== (env.PAGE_ORIGIN || 'https://koith.github.io'))
      return response(request, env, 403, 'ORIGIN_DENIED');
    if (!await authorize(request, env)) return response(request, env, 401, 'UNAUTHORIZED');
    let body;
    try {
      if (Number(request.headers.get('Content-Length') || '0') > 1024)
        return response(request, env, 413, 'BODY_TOO_LARGE');
      body = await request.json();
    } catch { return response(request, env, 400, 'INVALID_REQUEST'); }
    const { model, album, variant } = body || {};
    const number = body?.number;
    if (!identifier(model, album, number, variant))
      return response(request, env, 400, 'INVALID_PHOTO');
    const p = await entry(env, model, album, number, variant);
    if (!p) return response(request, env, 404, 'PHOTO_NOT_MIRRORED');
    const expires = Math.floor(Date.now() / 1000) + 300;
    const signature = await sign(env.SIGNING_KEY, payload(model, album, number, variant, p.sha, p.bytes, expires));
    const href = new URL('/api/v1/media/' + [model, album, number, variant].join('/'), u.origin);
    href.searchParams.set('h', p.sha);
    href.searchParams.set('b', String(p.bytes));
    href.searchParams.set('e', String(expires));
    href.searchParams.set('s', signature);
    return new Response(JSON.stringify({ url: href.href, expires_at: expires,
      sha256: p.sha, bytes: p.bytes }), { status: 200, headers: {
      ...cors(request, env), 'Content-Type': 'application/json',
      'Cache-Control': 'no-store'
    }});
  }
  const match = /^\/api\/v1\/media\/(mimmi|yui)\/([a-z0-9-]+)\/([0-9]{1,4})\/(original|preview)$/.exec(path);
  if (match && request.method === 'GET') {
    const [, model, album, rawNumber, variant] = match;
    const number = Number(rawNumber);
    const sha = u.searchParams.get('h'), size = u.searchParams.get('b');
    const expiresText = u.searchParams.get('e'), signature = u.searchParams.get('s');
    const expires = Number(expiresText), bytes = Number(size), now = Math.floor(Date.now() / 1000);
    if (!identifier(model, album, number, variant) || !isHex(sha, 64) ||
        !/^[1-9][0-9]{0,7}$/.test(size || '') || bytes > 8_000_000 ||
        !/^[1-9][0-9]{9,10}$/.test(expiresText || '') ||
        expires < now || expires > now + 300 || !isHex(signature, 64))
      return response(request, env, 403, 'SIGNATURE_INVALID');
    const calculated = await sign(env.SIGNING_KEY, payload(model, album, number, variant, sha, bytes, expires));
    if (!same(signature, calculated)) return response(request, env, 403, 'SIGNATURE_INVALID');
    const p = await entry(env, model, album, number, variant);
    if (!p || !same(p.sha, sha) || p.bytes !== bytes)
      return response(request, env, 404, 'PHOTO_NOT_MIRRORED');
    const object = await env.ARCHIVE_BUCKET.get(model + '/' + p.key);
    if (!object || object.size !== p.bytes) return response(request, env, 502, 'STORAGE_MISMATCH');
    const photo = new Uint8Array(await object.arrayBuffer());
    if (photo.byteLength !== p.bytes || !same(await hash(photo), p.sha))
      return response(request, env, 502, 'STORAGE_MISMATCH');
    const type = imageType(photo);
    if (!type) return response(request, env, 415, 'INVALID_IMAGE_TYPE');
    return new Response(photo, { status: 200, headers: {
      ...cors(request, env), 'Content-Type': type, 'Content-Length': String(p.bytes),
      'Cache-Control': 'private, max-age=60'
    }});
  }
  return response(request, env, 404, 'NOT_FOUND');
}
export function resetCatalogCacheForTests() { cache.clear(); }
export default { fetch: handle };
