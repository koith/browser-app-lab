/* Device-only cache for verified SHA-versioned owner media and covers.
 * A previously viewed photo survives Render Free sleep/restart. Never cache
 * credentials, catalogs, provider JSON/403/503, arbitrary images or other models.
 * Browser storage is best-effort and may be evicted by Safari. No public CDN.
 */
'use strict';

const COVER_CACHE = 'mimmi-owner-saved-covers-v1';
const MAX_COVERS = 96;
const PHOTO_CACHE = 'mimmi-owner-verified-photos-v1';
const MAX_PHOTOS = 96;
const MAX_PHOTO_BYTES = 120 * 1024 * 1024;
const MAX_SINGLE_PHOTO = 12 * 1024 * 1024;
const GATEWAY = 'https://mimmi-private-gallery-free.onrender.com';

function eligibleCover(request) {
  if (request.method !== 'GET' || request.destination !== 'image') return false;
  try {
    const url = new URL(request.url);
    if (url.origin !== GATEWAY ||
        !/^\/api\/cover\/mimmi\/[a-z0-9][a-z0-9-]{1,100}\/[0-9]{1,5}$/.test(url.pathname)) return false;
    const params = [...url.searchParams.keys()];
    return params.length === 1 && params[0] === 'v' &&
      /^[a-f0-9]{24}$/.test(url.searchParams.get('v') || '');
  } catch { return false; }
}


function eligiblePhoto(request) {
  if (request.method !== 'GET' ||
      (request.destination !== 'image' && request.destination !== '')) return false;
  if (request.credentials === 'include') return false;
  try {
    const url = new URL(request.url);
    if (url.origin !== GATEWAY ||
        !/^\/api\/media\/[a-z0-9][a-z0-9-]{1,99}\/[1-9][0-9]{0,4}\/(original|preview)$/.test(url.pathname)) return false;
    const keys = [...url.searchParams.keys()];
    return keys.length === 1 && keys[0] === 'v' &&
      /^[a-f0-9]{64}$/.test(url.searchParams.get('v') || '');
  } catch { return false; }
}

async function verifiedPhotoResponse(event) {
  const request = event.request;
  const version = new URL(request.url).searchParams.get('v');
  const cache = await caches.open(PHOTO_CACHE);
  const prior = await cache.match(request, {ignoreVary: true});
  if (prior) return prior;
  try {
    // Use only a readable first-party CORS response, never opaque provider
    // errors. Exact SHA verification excludes resized or swapped originals.
    const fetched = await fetch(request.url, {
      mode: 'cors', credentials: 'omit', redirect: 'error', cache: 'no-store'
    });
    const mime = (fetched.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
    if (!fetched.ok || !/^image\/(jpeg|png|webp|avif)$/.test(mime)) {
      return fetched;
    }
    const declaredLength = Number(fetched.headers.get('content-length') || 0);
    if (declaredLength > MAX_SINGLE_PHOTO) return fetched;
    if (!self.crypto || !self.crypto.subtle) return fetched;
    const bytes = await fetched.clone().arrayBuffer();
    if (!bytes.byteLength || bytes.byteLength > MAX_SINGLE_PHOTO) return fetched;
    const digest = await self.crypto.subtle.digest('SHA-256', bytes);
    const exact = Array.from(new Uint8Array(digest),
      x => x.toString(16).padStart(2, '0')).join('');
    if (exact !== version) return new Response('', {status: 502, statusText: 'Stored photo SHA mismatch'});
    const saved = new Response(bytes, {
      status: 200,
      headers: {'Content-Type': mime, 'Content-Length': String(bytes.byteLength),
        'Cache-Control': 'private, max-age=31536000, immutable'}
    });
    // Finish the disk write before the image load completes. Async
    // waitUntil writes can race with Safari document navigation/reload.
    try {
        await cache.put(request, saved.clone());
        const entries = await cache.keys();
        let size = 0, count = 0;
        const items = [];
        for (const key of entries) {
          const item = await cache.match(key);
          const length = Number(item?.headers?.get('content-length') || 0);
          items.push({key, length});
          size += length;
          count++;
        }
        for (const item of items) {
          if (count <= MAX_PHOTOS && size <= MAX_PHOTO_BYTES) break;
          if (await cache.delete(item.key)) {
            count--; size -= item.length;
          }
        }
    } catch {
      // Quota eviction or Safari private mode never breaks photo viewing.
    }
    return saved;
  } catch {
    // An uncached request must still behave like the existing gallery.
    return fetch(request);
  }
}

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const name of await caches.keys()) {
    if ((name.startsWith('mimmi-owner-saved-covers-') && name !== COVER_CACHE) ||
        (name.startsWith('mimmi-owner-verified-photos-') && name !== PHOTO_CACHE)) {
      await caches.delete(name);
    }
  }
  await self.clients.claim();
})()));

self.addEventListener('fetch', event => {
  const request = event.request;
  if (eligiblePhoto(request)) {
    event.respondWith(verifiedPhotoResponse(event));
    return;
  }
  if (!eligibleCover(request)) return;
  event.respondWith((async () => {
    const cache = await caches.open(COVER_CACHE);
    const saved = await cache.match(request, {ignoreVary: true});
    if (saved) return saved;
    try {
      // CORS is allowed by this same first-party gallery's existing gateway.
      // A CORS response lets us check 200 + image MIME; do not cache opaque
      // responses, provider JSON errors, rejected logins or broken thumbnails.
      const response = await fetch(request.url, {
        mode: 'cors', credentials: 'omit', redirect: 'error'
      });
      const mime = response.headers.get('content-type') || '';
      if (response.ok && /^image\/(webp|jpeg|png)$/i.test(mime.split(';')[0].trim())) {
        const verifiedImageResponse = response.clone();
        event.waitUntil((async () => {
          await cache.put(request, verifiedImageResponse);
          const entries = await cache.keys();
          for (const entry of entries.slice(0, Math.max(0, entries.length - MAX_COVERS))) {
            await cache.delete(entry);
          }
        })().catch(() => {}));
      }
      return response;
    } catch {
      // Offline/CORS/service-worker faults never block the pre-existing direct
      // cover request. A failed fallback is allowed to fail visibly as before.
      return fetch(request);
    }
  })());
});
