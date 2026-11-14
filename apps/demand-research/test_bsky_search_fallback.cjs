/* No network, no real people: proves third-party result URLs NEVER
 * reach the feed until official getProfiles and getPosts identities agree.
 */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const js=fs.readFileSync(path.join(__dirname,"bsky_search_fallback.js"),"utf8");
const html=fs.readFileSync(path.join(__dirname,"index.html"),"utf8");
const sw=fs.readFileSync(path.join(__dirname,"intersection-sw.js"),"utf8");
const docker=fs.readFileSync(path.join(__dirname,"Dockerfile"),"utf8");
const gateway=fs.readFileSync(path.join(__dirname,"gateway.py"),"utf8");
assert.match(html,/src="bsky_search_fallback\.js\?v=20261114-public-source-hydration-v2"/);
assert.match(sw,/bsky_search_fallback\.js\?v=20261114-public-source-hydration-v2/);
assert.match(sw,/Network-first avoids serving the previous HTML/);
assert.doesNotMatch(sw,/ignoreSearch:true/,"Script query version must be respected");
assert.match(docker,/COPY apps\/demand-research\/bsky_search_fallback\.js \/app\/bsky_search_fallback\.js/);
assert.match(gateway,/"bsky_search_fallback\.js"/);
assert.match(html,/window\.INTERSECTION_stopSearchFallback\?\.\(\)/);
assert.match(html,/window\.INTERSECTION_resumeSearchFallback\?\.\(\)/);

async function run(){
 const events={},seen=[],states=[],calls=[];
 const WINDOW=24*60*60*1000,now=Date.now();
 const goodURI="at://did:plc:aaaaaaaaaaaaaaaaaaaaaaaa/app.bsky.feed.post/3n275awaudk2f";
 const badURI="at://did:plc:bbbbbbbbbbbbbbbbbbbbbbbb/app.bsky.feed.post/3n275awaudk2f";
 let forged=false;
 const window={
   INTERSECTION_PUBLIC_SEARCH_DOWN:"",
   INTERSECTION_publicFeedRange:()=>({fromMs:now-30*WINDOW,toMs:now+WINDOW,run:1}),
   INTERSECTION_searchFallbackStatus:state=>states.push(state),
   INTERSECTION_receiveLiveBskyPost:post=>{
     seen.push(post);return true;
   },
   addEventListener:(name,fn)=>events[name]=fn
 };
 const get=async url=>{
   calls.push(String(url));
   const u=new URL(url);
   const uriList=u.searchParams.getAll("uris");
   if(u.host==="bsky.md"){
     // First-party Markdown is discovery ONLY. Forged body is never shown.
     return {ok:true,headers:{get:()=>null},text:async()=>(
       "# Search\n[View on Bluesky](https://bsky.app/profile/sample.bsky.social/post/3n275awaudk2f)\n"+
       "FAKE CONTENT FROM UNTRUSTED PROVIDER\n"
     )};
   }
   if(u.pathname.endsWith("getProfiles")){
     return {ok:true,headers:{get:()=>null},json:async()=>({profiles:[{
       handle:"sample.bsky.social",did:"did:plc:aaaaaaaaaaaaaaaaaaaaaaaa"
     }]})};
   }
   if(u.pathname.endsWith("getPosts")){
     return {ok:true,headers:{get:()=>null},json:async()=>({posts:uriList.map(uri=>({
       uri:forged?badURI:uri,author:{did:"did:plc:aaaaaaaaaaaaaaaaaaaaaaaa"},
       record:{text:"뒷계 validated first-party content",createdAt:new Date().toISOString()}
     }))})};
   }
   throw Error("Unexpected network target "+url);
 };
 const sandbox={window,URL,AbortController,Date,console,
   fetch:get,setTimeout,clearTimeout};
 vm.runInNewContext(js,sandbox,{filename:"bsky_search_fallback.js",timeout:1500});
 assert.equal(seen.length,0,"External search results must not appear before verification");
 events["intersection:public-search-unavailable"]();
 for(let i=0;i<100&&states.at(-1)?.state==="searching";i++)
   await new Promise(resolve=>setTimeout(resolve,0));
 // The async queue returns after all official validations, never after the
 // 3rd-party unverified text alone.
 for(let i=0;i<5;i++)await new Promise(resolve=>setTimeout(resolve,0));
 assert.ok(calls.some(x=>x.startsWith("https://bsky.md/search?q=")));
 assert.ok(calls.some(x=>x.includes("app.bsky.actor.getProfiles")));
 assert.ok(calls.some(x=>x.includes("app.bsky.feed.getPosts")));
 assert.ok(seen.length>=1);
 assert.equal(seen[0].uri,goodURI);
 assert.equal(states.at(-1)?.state,"partial");
 const accepted=seen.length;
 // A different original URI from the same unrelated search hit is refused.
 window.INTERSECTION_stopSearchFallback();
 forged=true;
 events["intersection:public-search-unavailable"]();
 for(let i=0;i<100&&states.at(-1)?.state==="searching";i++)
   await new Promise(resolve=>setTimeout(resolve,0));
 for(let i=0;i<5;i++)await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(seen.length,accepted,"Bad official response cannot be promoted");
 assert.ok(states.at(-1)?.state==="unavailable");
 window.INTERSECTION_stopSearchFallback();
 console.log("BSKY_PUBLIC_SEARCH_VERIFIED_FALLBACK_PASS",JSON.stringify({
   sourceRequests:calls.filter(x=>x.startsWith("https://bsky.md/")).length,
   officialProfileRequests:calls.filter(x=>x.includes("getProfiles")).length,
   officialPostRequests:calls.filter(x=>x.includes("getPosts")).length,
   verified:accepted,foreignPostRejected:true,withoutCredentials:true
 }));
}
run().catch(error=>{console.error(error);process.exitCode=1});
