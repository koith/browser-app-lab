/* Reuse only previously decoded, SHA-versioned Mimmi ALBUM COVER previews.
 * No originals, personal vault entries, credentials, source images or catalog
 * metadata are cached. This is a device-local reload optimization, not a CDN.
 */
'use strict';

const COVER_CACHE = 'mimmi-owner-saved-covers-v1';
const MAX_COVERS = 96;
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

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const name of await caches.keys()) {
    if (name.startsWith('mimmi-owner-saved-covers-') && name !== COVER_CACHE) {
      await caches.delete(name);
    }
  }
  await self.clients.claim();
})()));

self.addEventListener('fetch', event => {
  const request = event.request;
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
        mode: 'cors', credentials: 'omit', redirect: 'follow'
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
