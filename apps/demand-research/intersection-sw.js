/* INTERSECTION public-shell cold-start bridge.
 * Render Free may sleep after 15 idle minutes. This worker shows the last
 * VERIFIED PUBLIC HTML/JS shell while the HTTP server wakes. It NEVER stores
 * account records, API JSON, uploaded media, authentication or private bytes.
 */
"use strict";
const VERSION="intersection-public-shell-v1-20261115-manual-account-block-v1";
const PREFIX="intersection-public-shell-v1-";
const FILES=[
  "/",
  "/live_feed_recovery.js?v=20261114-bsky-outage-v1",
  "/bsky_search_fallback.js?v=20261114-public-source-hydration-v1",
  "/post_activity_ranking.js",
  "/public_video_trends.js",
  "/target_archive_client.js?v=20261115-own-pending-v1",
  "/free_discovery.js",
  "/account_watch.js?v=20261110-first-tab",
  "/archive_tab.js?v=20261115-queue-dialog-v1",
  "/account_auto_analysis.js?v=20261105-account-ui-3",
  "/account_index_client.js?v=20261105-account-ui-3",
  "/account_group_client.js?v=20261105-account-ui-3"
];
const SCRIPT_PATHS=new Set(FILES.filter(p=>p!=="/").map(p=>new URL(p,self.location.origin).pathname));
async function publicResponse(path){
  const response=await fetch(path,{cache:"no-store",credentials:"omit"});
  if(!response.ok||response.type==="opaque")return null;
  const type=response.headers.get("content-type")||"";
  if(path==="/"){
    if(!type.includes("text/html"))return null;
    // Never cache a Render waking/loading placeholder or an error page.
    if(!(await response.clone().text()).includes("<title>INTERSECTION</title>"))return null;
  }else if(!type.includes("javascript"))return null;
  return response;
}
async function updatePublic(path){
  try{
    const fresh=await publicResponse(path);
    if(fresh)await (await caches.open(VERSION)).put(path,fresh);
  }catch{}
}
self.addEventListener("install",event=>{
  event.waitUntil((async()=>{
    for(const path of FILES)await updatePublic(path);
    await self.skipWaiting();
  })());
});
self.addEventListener("activate",event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k.startsWith(PREFIX)&&k!==VERSION)
      .map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;
  // Network-first avoids serving the previous HTML forever after a
  // successful deploy. If free Render is asleep/offline, recover the last
  // verified public shell; never cache APIs, personal data, or error pages.
  if(request.mode==="navigate"){
    if(url.pathname!=="/")return;
    event.respondWith((async()=>{
      const cache=await caches.open(VERSION);
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),3500);
      try{
        const response=await fetch(request,{signal:controller.signal,cache:"no-store"});
        if(response.ok&&(response.headers.get("content-type")||"").includes("text/html")&&
          (await response.clone().text()).includes("<title>INTERSECTION</title>")){
          await cache.put("/",response.clone());
          return response;
        }
      }catch{/* Serve verified public shell only when origin is unavailable. */}
      finally{clearTimeout(timer)}
      const cached=await cache.match("/");
      if(cached)return cached;
      return fetch(request);
    })());
    return;
  }
  if(!SCRIPT_PATHS.has(url.pathname))return;
  // Scripts are public app code. All /api/*, media and archive routes use
  // native network fetch and cannot be accidentally cached by this worker.
  event.respondWith((async()=>{
    const cached=await (await caches.open(VERSION)).match(request);
    if(cached)return cached;
    return fetch(request);
  })());
  event.waitUntil(updatePublic(FILES.find(x=>x.split("?")[0]===url.pathname)));
});
