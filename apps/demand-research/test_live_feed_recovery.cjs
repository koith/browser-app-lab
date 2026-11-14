/* Deterministic, network-free tests of official Jetstream source verification.
 * Exercises the production JS unchanged in a mocked browser event loop.
 */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"live_feed_recovery.js"),"utf8");
const shell=fs.readFileSync(path.join(__dirname,"index.html"),"utf8");
const worker=fs.readFileSync(path.join(__dirname,"intersection-sw.js"),"utf8");
assert.match(shell,/src="live_feed_recovery\.js\?v=20261114-bsky-outage-v1"/);
assert.match(worker,/live_feed_recovery\.js\?v=20261114-bsky-outage-v1/);
assert.match(shell,/intersection:public-search-unavailable/);
assert.match(shell,/feedSourceNotice/);
assert.match(shell,/Bluesky 공개 검색 실패/);
assert.match(shell,/INTERSECTION_receiveLiveBskyPost/);
assert.match(shell,/id="retryFeed"/);
assert.match(shell,/if\(bskySearchFailureCode&&!cloudMode\)return false/);

async function main(){
 const listeners=new Map();
 const document={visibilityState:"visible",addEventListener(type,fn){listeners.set("doc:"+type,fn)}};
 const navigator={onLine:true};
 const states=[],accepted=[],fetched=[],timers=new Map();
 let nextTimer=0,valid=true;
 class WebSocket {
   static all=[];
   constructor(url){this.url=url;this.handlers=new Map();this.closed=false;WebSocket.all.push(this)}
   addEventListener(type,fn){this.handlers.set(type,fn)}
   send(type,payload={}){this.handlers.get(type)?.(payload)}
   close(){this.closed=true;this.send("close")}
 }
 const window={
   INTERSECTION_liveFeedState:state=>states.push(state),
   INTERSECTION_receiveLiveBskyPost:post=>accepted.push(post),
   addEventListener(type,fn){listeners.set("win:"+type,fn)}
 };
 const fakeFetch=async url=>{
   fetched.push(String(url));
   const requested=new URL(String(url)).searchParams.getAll("uris");
   assert.equal(requested.length,1);
   assert.match(String(url),/^https:\/\/public\.api\.bsky\.app\/xrpc\/app\.bsky\.feed\.getPosts/);
   return {ok:true,json:async()=>({posts:[{uri:valid?requested[0]:"at://did:plc:evil/app.bsky.feed.post/wrong",
      record:{text:"뒷계 실시간 원문",createdAt:new Date().toISOString()},
      author:{handle:"example.bsky.social"}}]})};
 };
 const sandbox={window,document,navigator,WebSocket,fetch:fakeFetch,URL,Date,JSON,
   AbortController,setTimeout(fn){const id=++nextTimer;timers.set(id,fn);return id},
   clearTimeout(id){timers.delete(id)},console};
 vm.runInNewContext(source,sandbox,{timeout:1200,filename:"live_feed_recovery.js"});
 assert.equal(WebSocket.all.length,0,"Never stream when search is healthy");
 listeners.get("win:intersection:public-search-unavailable")();
 assert.equal(WebSocket.all.length,1,"Search outage must initiate one stream");
 const ws=WebSocket.all[0];
 assert.match(ws.url,/jetstream2\.us-east\.bsky\.network\/subscribe/);
 ws.send("open");assert.equal(states.at(-1),"listening");
 const record={text:"뒷계 실시간 원문",createdAt:new Date().toISOString()};
 const event={kind:"commit",did:"did:plc:aaaaaaaaaaaaaaaaaaaaaaaa",
   commit:{operation:"create",collection:"app.bsky.feed.post",
     rkey:"3n27yge3hys24",record}};
 ws.send("message",{data:JSON.stringify({...event,commit:{...event.commit,collection:"app.bsky.feed.like"}})});
 assert.equal(fetched.length,0,"Likes are never source posts");
 ws.send("message",{data:JSON.stringify(event)});
 assert.equal(timers.size,1,"One batched official hydration request expected");
 const queued=[...timers.entries()];timers.clear();
 // Execute the 900ms batch timer and settle promises from fake fetch.
 queued[0][1]();
 for(let i=0;i<8;i++)await Promise.resolve();
 assert.equal(fetched.length,1,"One official getPosts request");
 assert.equal(accepted.length,1,"Only verified URI is accepted");
 assert.equal(states.at(-1),"listening");
 ws.send("message",{data:JSON.stringify(event)});
 assert.equal(timers.size,0,"Duplicate event must never be rehydrated");
 valid=false;
 const altered={...event,commit:{...event.commit,rkey:"3n27yge3hys25"}};
 ws.send("message",{data:JSON.stringify(altered)});
 const queued2=[...timers.entries()];timers.clear();queued2[0][1]();
 for(let i=0;i<8;i++)await Promise.resolve();
 assert.equal(accepted.length,1,"Mismatched getPosts URI must be rejected");
 document.visibilityState="hidden";listeners.get("doc:visibilitychange")();
 assert.equal(ws.closed,true,"Pause streaming when tab is backgrounded");
 const n=WebSocket.all.length;
 window.INTERSECTION_stopLiveFeedRecovery();
 listeners.get("doc:visibilitychange")();
 assert.equal(WebSocket.all.length,n,"Stop must suppress automatic reconnect");
 console.log("INTERSECTION_LIVE_FEED_RECOVERY_PASS",
   JSON.stringify({officialHydrations:fetched.length,accepted:accepted.length,
     duplicateBlocked:true,foreignUriBlocked:true,backgroundPaused:true,
     statusStates:states.slice(0,5)}));
}
main().catch(err=>{console.error(err);process.exitCode=1});
