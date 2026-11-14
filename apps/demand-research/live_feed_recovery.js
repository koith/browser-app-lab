/* INTERSECTION public feed fallback after the Bluesky anonymous search API
 * returns 403/429/5xx. No key, cookie, cross-account correlation or persistence.
 * Official Jetstream live tail supplies *new* posts only; every displayed row
 * must independently hydrate from public AppView getPosts with the exact URI.
 * This does NOT backfill 30 days or guarantee network-wide coverage.
 */
(function(){
 "use strict";
 const TERMS=["뒷계","섹트","섹블","일탈계"];
 const STREAM="wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post";
 const POST_LOOKUP="https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts";
 let enabled=false,socket=null,connectionTimer=null,flushTimer=null;
 let queue=[],queued=new Set(),seen=new Set(),connecting=false;
 let tab="posts",generation=0,retryCount=0;
 const report=state=>window.INTERSECTION_liveFeedState?.(state);
 function pause(){
   generation++;
   if(connectionTimer!==null){clearTimeout(connectionTimer);connectionTimer=null;}
   if(flushTimer!==null){clearTimeout(flushTimer);flushTimer=null;}
   queue=[];queued.clear();seen.clear();
   const old=socket;socket=null;connecting=false;
   if(old){try{old.close(1000,"inactive")}catch{}}
 }
 window.INTERSECTION_stopLiveFeedRecovery=()=>{
   enabled=false;pause();
 };
 function canRun(){return enabled&&tab==="posts"&&document.visibilityState!=="hidden"&&navigator.onLine!==false}
 function retry(){
   if(!canRun())return;
   const wait=Math.min(30000,5000*Math.max(1,retryCount));
   if(connectionTimer!==null)clearTimeout(connectionTimer);
   report("reconnecting");
   connectionTimer=setTimeout(()=>{connectionTimer=null;connect()},wait);
 }
 function enqueue(event){
   if(!canRun()||event?.kind!=="commit"||event?.commit?.operation!=="create"||
      event?.commit?.collection!=="app.bsky.feed.post")return;
   const record=event.commit.record;
   if(typeof record?.text!=="string"||record.text.length>5000||
      !TERMS.some(term=>record.text.includes(term)))return;
   const date=Date.parse(String(record.createdAt||""));
   if(!Number.isFinite(date)||Math.abs(Date.now()-date)>15*60*1000)return;
   const did=String(event.did||"");
   const key=String(event.commit.rkey||"");
   if(!/^did:(plc|web):[a-z0-9._:%-]{8,200}$/i.test(did)||
      !/^[a-z0-9]{6,32}$/i.test(key))return;
   const uri="at://"+did+"/app.bsky.feed.post/"+key;
   if(seen.has(uri)||queued.has(uri))return;
   if(seen.size>=500)seen.clear();
   seen.add(uri);
   if(queue.length>=45)queue.shift(); // never grow unbounded on the device
   queue.push(uri);queued.add(uri);
   if(flushTimer===null)
     flushTimer=setTimeout(flush,900);
 }
 async function flush(){
   flushTimer=null;
   if(!canRun()){queue=[];queued.clear();return}
   const generationAtStart=generation;
   const uris=queue.splice(0,20);
   uris.forEach(uri=>queued.delete(uri));
   if(!uris.length)return;
   report("receiving");
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),9000);
   try{
     const url=new URL(POST_LOOKUP);
     for(const uri of uris)url.searchParams.append("uris",uri);
     const response=await fetch(url.href,{
       method:"GET",mode:"cors",credentials:"omit",cache:"no-store",
       headers:{"Accept":"application/json"},signal:controller.signal});
     if(!response.ok)throw Error("AppView "+response.status);
     const json=await response.json();
     if(generationAtStart!==generation||!canRun())return;
     const expected=new Set(uris);
     for(const post of Array.isArray(json.posts)?json.posts:[]){
       if(!post||!expected.has(post.uri)||
          !TERMS.some(term=>post.record?.text?.includes(term)))continue;
       window.INTERSECTION_receiveLiveBskyPost?.(post);
     }
   }catch{/* No verified original means no visible record; do not invent posts. */}
   finally{
     clearTimeout(timer);
     if(generationAtStart===generation&&canRun()){
       report("listening");
       if(queue.length&&flushTimer===null)flushTimer=setTimeout(flush,900);
     }
   }
 }
 function connect(){
   if(!canRun()||socket||connecting)return;
   if(typeof WebSocket!=="function"){report("unavailable");return}
   connecting=true;report("connecting");
   let ws;
   try{ws=new WebSocket(STREAM)}catch{
     connecting=false;retryCount++;retry();return;
   }
   socket=ws;
   ws.addEventListener("open",()=>{
     if(ws!==socket)return;
     connecting=false;retryCount=0;report("listening");
   });
   ws.addEventListener("message",event=>{
     if(ws!==socket||!canRun())return;
     const raw=event.data;
     if(typeof raw!=="string"||raw.length>140000||
        !TERMS.some(term=>raw.includes(term)))return;
     try{enqueue(JSON.parse(raw))}catch{/* malformed events never become posts */}
   });
   ws.addEventListener("error",()=>{if(ws===socket)report("unavailable")});
   ws.addEventListener("close",()=>{
     if(ws!==socket)return;
     socket=null;connecting=false;
     if(canRun()){retryCount++;retry()}
   });
 }
 function resume(){if(canRun())connect();else pause()}
 document.addEventListener("visibilitychange",resume);
 window.addEventListener("online",resume);
 window.addEventListener("offline",resume);
 window.addEventListener("intersection:tab-change",event=>{
   tab=String(event.detail?.view||"posts");
   resume();
 });
 window.addEventListener("intersection:public-search-unavailable",()=>{
   enabled=true;resume();
 });
 // A very fast provider failure may precede deferred-script installation.
 if(window.INTERSECTION_PUBLIC_SEARCH_DOWN){enabled=true;resume();}
})();
