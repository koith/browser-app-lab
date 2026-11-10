/* INTERSECTION — static-shell-only offline navigation.
 * Render Free can return a provider warmup page before our Python process
 * starts. Cache only authenticated-data-free HTML shells after a real, marker-
 * verified response. NEVER cache API, media, cookies, URLs or private records.
 */
"use strict";
const VERSION="intersection-shell-20261110-v1";
const ALLOWED=new Map([
  ["/",'id="viewPosts"'],
  ["/auto-archive",'id="search"'],
  ["/account-archive",'id="accountSelect"']
]);
self.addEventListener("install",event=>{
  event.waitUntil(self.skipWaiting());
});
self.addEventListener("activate",event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k.startsWith("intersection-shell-")&&k!==VERSION)
      .map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
async function sanitizedShell(path,response){
  if(!response||!response.ok||response.type!=="basic")return null;
  if(!(response.headers.get("content-type")||"").includes("text/html"))return null;
  const body=await response.clone().text();
  if(body.length>500000||!body.includes(ALLOWED.get(path)))return null;
  // A fresh response object strips Set-Cookie, no-store and provider headers.
  // The HTML files themselves contain no account, media or private credentials.
  return new Response(body,{status:200,headers:{
    "Content-Type":"text/html; charset=utf-8",
    "Referrer-Policy":"no-referrer",
    "X-Robots-Tag":"noindex, nofollow",
    "X-Content-Type-Options":"nosniff"
  }});
}
self.addEventListener("fetch",event=>{
  const request=event.request,url=new URL(request.url);
  if(request.mode!=="navigate"||request.method!=="GET"||
     url.origin!==self.location.origin||!ALLOWED.has(url.pathname))return;
  event.respondWith((async()=>{
    const cache=await caches.open(VERSION);
    const key=new Request(url.origin+url.pathname,{method:"GET"});
    const existing=await cache.match(key);
    if(existing){
      event.waitUntil((async()=>{
        try{
          const fresh=await sanitizedShell(url.pathname,await fetch(request,{cache:"no-store"}));
          if(fresh)await cache.put(key,fresh);
        }catch{} // Keep verified static shell; never cache provider warmup HTML.
      })());
      return existing;
    }
    const response=await fetch(request);
    try{
      const safe=await sanitizedShell(url.pathname,response);
      if(safe)event.waitUntil(cache.put(key,safe));
    }catch{}
    return response;
  })());
});
