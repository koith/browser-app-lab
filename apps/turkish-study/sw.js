const CACHE="turkce120-shell-v011";
const ASSETS=["./","./index.html","./app/release-gate.js","./manifest.webmanifest","./icon.svg"];
const LIVE=new Set(["curriculum.json","lessons.json","RELEASE_MANIFEST.json"]);
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>(k.startsWith("turkce120-shell-")||k.startsWith("turkce120-draft-"))&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",e=>{
 if(e.request.method!=="GET"||!e.request.url.startsWith(self.registration.scope))return;
 const path=new URL(e.request.url).pathname.split("/").pop();
 if(LIVE.has(path))return; // release data must be loaded atomically by app, never stale per-file responses
 e.respondWith(fetch(e.request).then(async r=>{if(r.ok&&ASSETS.some(p=>new URL(p,self.registration.scope).href===e.request.url)){try{const c=await caches.open(CACHE);await c.put(e.request,r.clone());}catch{}}return r;}).catch(()=>caches.open(CACHE).then(c=>c.match(e.request)).then(r=>r||Response.error())));
});