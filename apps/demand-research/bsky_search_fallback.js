/* INTERSECTION — outage fallback public-search discovery.
 * Source: documented public CORS Markdown search at https://bsky.md/search.
 * DISCOVERY ONLY: its text, images, authors, dates and counts are NEVER shown
 * as verified data. Every candidate URL is resolved to an official Bluesky
 * DID via getProfiles, then exact original post is checked with getPosts.
 * This operates only on public posts and does not bypass platform labels,
 * privacy, deletion, authentication or consent. No cross-account identity merge.
 * Limited batches; 30-day coverage is partial unless provider pagination
 * can be exhaustively completed and all originals verified.
 */
(()=>{
 "use strict";
 const SEARCH="https://bsky.md/search";
 const PROFILES="https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles";
 const POSTS="https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts";
 const TERMS=["뒷계","섹트","섹블","일탈계"];
 const privateRender=typeof location!=="undefined"&&
   location.hostname==="intersection-originals-free.onrender.com";
 const SOURCE_LIMIT=40, INITIAL_PAGES=3, MORE_PAGES=3, MAX_PAGES=18;
 let enabled=false,epoch=0,processing=false;
 let cursors=new Map(),seen=new Set(),identity=new Map(),active=new Set();
 let status={state:"idle",verified:0,checked:0,pages:0,providerFailures:0,more:false};
 const publicState=()=>window.INTERSECTION_publicFeedRange?.();
 const report=(state)=>{
   status.state=state;
   window.INTERSECTION_searchFallbackStatus?.({...status});
 };
 function stop(){
   enabled=false;epoch++;
   for(const controller of active)controller.abort();
   active.clear();processing=false;seen.clear();identity.clear();cursors.clear();
   status={state:"idle",verified:0,checked:0,pages:0,providerFailures:0,more:false};
 }
 window.INTERSECTION_stopSearchFallback=stop;
 window.INTERSECTION_hasSearchFallbackMore=()=>enabled&&status.more&&!processing;
 function validHandle(s){
   return /^[a-z0-9][a-z0-9.-]{2,252}$/i.test(s)&&s.includes(".")&&
     !s.includes("..")&&!s.startsWith(".")&&!s.endsWith(".");
 }
 function parseLinks(text){
   const rows=[],dupes=new Set();
   // Markdown has repeated profile/post links; reject URLs outside Bluesky.
   const re=/https:\/\/bsky\.app\/profile\/([a-z0-9][a-z0-9.-]{2,252})\/post\/([a-z0-9]{6,32})(?=[^a-z0-9]|$)/gi;
   for(const match of String(text).matchAll(re)){
     const handle=match[1].toLowerCase(),rkey=match[2].toLowerCase();
     if(!validHandle(handle))continue;
     const id=handle+"/"+rkey;
     if(dupes.has(id))continue;
     dupes.add(id);rows.push({handle,rkey});
     if(rows.length>=SOURCE_LIMIT)break;
   }
   // Never blindly follow an arbitrary third-party link. Only copy a bounded
   // cursor (base64url token) into a fixed preselected HTTPS endpoint.
   const cursor=/[?&]cursor=([A-Za-z0-9_-]{4,1000})/.exec(String(text));
   return {rows,cursor:cursor?cursor[1]:""};
 }
 async function get(url,token,kind){
   if(token!==epoch)throw Error("stale search");
   const ctrl=new AbortController();active.add(ctrl);
   const timer=setTimeout(()=>ctrl.abort(),kind==="markdown"?12000:9000);
   try{
     const response=await fetch(url,{mode:"cors",credentials:"omit",
       cache:"no-store",headers:{"Accept":kind==="markdown"?"text/markdown":"application/json"},
       signal:ctrl.signal});
     if(!response.ok)throw Error(kind+" HTTP "+response.status);
     const len=Number(response.headers?.get("content-length")||0);
     if(len>650000)throw Error("oversized result");
     if(kind==="markdown"){
       const body=await response.text();
       if(body.length>650000)throw Error("oversized result");
       return body;
     }
     return await response.json();
   }finally{clearTimeout(timer);active.delete(ctrl)}
 }
 function batches(items,max){
   const out=[];
   for(let i=0;i<items.length;i+=max)out.push(items.slice(i,i+max));
   return out;
 }
 async function verify(rows,term,token){
   if(token!==epoch||!enabled||!rows.length)return;
   const unresolved=[...new Set(rows.map(r=>r.handle))].filter(h=>!identity.has(h));
   // Resolve handles, never treat an unverified handle as a DID.
   for(const group of batches(unresolved,25)){
     if(token!==epoch)return;
     const url=new URL(PROFILES);
     for(const actor of group)url.searchParams.append("actors",actor);
     let data;
     try{data=await get(url.href,token,"json")}
     catch{status.providerFailures++;continue}
     const verified=new Map();
     for(const p of Array.isArray(data.profiles)?data.profiles:[]){
       if(!p||typeof p.did!=="string"||!/^did:(plc|web):/.test(p.did))continue;
       const name=String(p.handle||"").toLowerCase();
       if(group.includes(name))verified.set(name,p.did);
     }
     for(const name of group)identity.set(name,verified.get(name)||"");
   }
   const uris=[];
   for(const row of rows){
     const did=identity.get(row.handle);
     if(!did)continue;
     const uri="at://"+did+"/app.bsky.feed.post/"+row.rkey;
     if(seen.has(uri))continue;
     seen.add(uri);uris.push(uri);
   }
   for(const group of batches(uris,20)){
     if(token!==epoch)return;
     const url=new URL(POSTS);
     for(const uri of group)url.searchParams.append("uris",uri);
     let result;
     try{result=await get(url.href,token,"json")}
     catch{status.providerFailures++;continue}
     const expected=new Set(group);
     for(const item of Array.isArray(result.posts)?result.posts:[]){
       // Even if the index returns unrelated or forged URLs, source post URI,
       // DID, original text and date must be re-validated before display.
       if(!item||!expected.has(item.uri)||!item.uri.startsWith("at://"+item.author?.did+"/")||
          typeof item.record?.text!=="string"||!item.record.text.includes(term))continue;
       status.checked++;
       if(window.INTERSECTION_receiveLiveBskyPost?.(item))status.verified++;
     }
     report("verifying");
   }
 }
 function currentRange(){
   const range=publicState();
   return range&&Number.isFinite(range.fromMs)&&Number.isFinite(range.toMs)?
     {since:new Date(range.fromMs).toISOString().slice(0,10),
      until:new Date(range.toMs).toISOString().slice(0,10),run:range.run}:null;
 }
 // Same-origin verification is independent of Safari's cross-origin CORS.
 // Source links and their text are still untrusted: the Render endpoint itself
 // resolves source DIDs and hydrates exact official getPosts originals.
 async function serverRecover(term,token,range){
   if(!privateRender||!range||token!==epoch)return false;
   const u=new URL("/api/public-search-verified",location.origin);
   u.searchParams.set("q",term);
   u.searchParams.set("since",range.since);
   u.searchParams.set("until",range.until);
   const ctrl=new AbortController();active.add(ctrl);
   const timer=setTimeout(()=>ctrl.abort(),39000);
   try{
     const r=await fetch(u.href,{credentials:"omit",cache:"no-store",
       headers:{"Accept":"application/json"},signal:ctrl.signal});
     if(!r.ok)throw Error("server search HTTP "+r.status);
     const data=await r.json();
     if(token!==epoch||currentRange()?.run!==range.run)return false;
     for(const p of Array.isArray(data.verified)?data.verified:[]){
       if(!p?.uri?.startsWith("at://did:")||
          typeof p.record?.text!=="string"||!p.record.text.includes(term))continue;
       status.checked++;
       if(window.INTERSECTION_receiveLiveBskyPost?.(p))status.verified++;
     }
     report("verifying");
     return true;
   }catch{
     status.providerFailures++;
     return false;
   }finally{clearTimeout(timer);active.delete(ctrl)}
 }
 async function searchPage(term,token){
   const old=cursors.get(term)||{cursor:"",pages:0,finished:false};
   if(old.finished||old.pages>=MAX_PAGES)return;
   const range=currentRange();
   if(!range)return;
   const u=new URL(SEARCH);
   u.searchParams.set("q",term);
   u.searchParams.set("limit",String(SOURCE_LIMIT));
   u.searchParams.set("since",range.since);
   u.searchParams.set("until",range.until);
   if(old.cursor)u.searchParams.set("cursor",old.cursor);
   let page;
   try{page=await get(u.href,token,"markdown")}
   catch{
     status.providerFailures++;
     // If iOS CORS fails, use the same-origin independently verified server
     // source. Its results cannot bypass official AppView identity checks.
     if(await serverRecover(term,token,range)){
       old.pages++;old.finished=true;cursors.set(term,old);status.pages++;
       return;
     }
     old.pages++;cursors.set(term,old);
     report("unavailable");
     return;
   }
   if(token!==epoch||currentRange()?.run!==range.run)return;
   const found=parseLinks(page);
   const newCursor=found.cursor&&found.cursor!==old.cursor?found.cursor:"";
   old.pages++;
   old.cursor=newCursor;
   old.finished=!newCursor||old.pages>=MAX_PAGES;
   cursors.set(term,old);status.pages++;
   await verify(found.rows,term,token);
 }
 async function run(pageCount){
   if(!enabled||processing)return;
   processing=true;let token=epoch;
   report("searching");
   try{
     // Two concurrent providers at most; avoid the 28*4 request storm that
     // previously left the iPhone at "게시글 검색 중" for minutes.
     let jobs=[...TERMS];
     const work=async()=>{
       while(jobs.length&&token===epoch&&enabled){
         const term=jobs.shift();
         for(let i=0;i<pageCount&&token===epoch;i++){
           const before=cursors.get(term);
           if(before?.finished)break;
           await searchPage(term,token);
         }
       }
     };
     await Promise.all([work(),work()]);
   }finally{
     if(token===epoch){
       processing=false;
       status.more=[...TERMS].some(t=>!(cursors.get(t)?.finished) &&
         (cursors.get(t)?.pages||0)<MAX_PAGES);
       report(status.verified?"partial":"unavailable");
     }
   }
 }
 function begin(){
   if(enabled)return;
   enabled=true;epoch++;
   cursors.clear();seen.clear();identity.clear();
   status={state:"searching",verified:0,checked:0,pages:0,providerFailures:0,more:false};
   const token=epoch,range=currentRange();
   // Prime one exact public term via our own server so a Render/iOS visitor
   // can see verified first-party originals even when external CORS is blocked.
   if(privateRender)void serverRecover("뒷계",token,range);
   void run(INITIAL_PAGES);
 }
 window.INTERSECTION_resumeSearchFallback=()=>{
   if(enabled&&!processing)void run(MORE_PAGES);
 };
 window.addEventListener("intersection:public-search-unavailable",begin);
 // Anonymous search can fail before deferred scripts execute.
 if(window.INTERSECTION_PUBLIC_SEARCH_DOWN)begin();
})();
