/* Regressions: real Render host was excluded from automatic
 * X/Threads/Instagram discovery, producing zero cards during Bsky API outage.
 * No external network or personal account is contacted by this test.
 */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),
  path=require("node:path"),vm=require("node:vm");
const source=fs.readFileSync(path.join(__dirname,"free_discovery.js"),"utf8");
assert.match(source,/intersection-originals-free\.onrender\.com/);
assert.match(source,/koith\.github\.io/);
assert.match(source,/const TERMS=\["뒷계","섹트","섹블","일탈계"\]/);
async function run(host){
 const calls=[],received=[],events={};
 const window={
   INTERSECTION_receiveCandidates:r=>received.push(r),
   INTERSECTION_acceptPublicX:()=>({accepted:false}),
   addEventListener:(k,fn)=>events[k]=fn
 };
 const fakeFetch=async url=>{
   calls.push(String(url));
   return {ok:true,json:async()=>String(url).includes("keenable")?
     {results:[]}:{success:true,data:{web:[]}}};
 };
 let seq=0;
 const ctx={window,location:{hostname:host},fetch:fakeFetch,
   URL,AbortController,URLSearchParams,Date,
   setTimeout:(fn,delay)=>{if(delay===180)Promise.resolve().then(fn);return ++seq},
   clearTimeout:()=>{}};
 vm.runInNewContext(source,ctx,{filename:"free_discovery.js",timeout:1500});
 for(let i=0;i<25;i++)await Promise.resolve();
 const expected=host==="koith.github.io"||
    host==="intersection-originals-free.onrender.com";
 assert.equal(calls.length,expected?6:0,{host,calls});
 assert.equal(received.length>0,expected);
 if(expected)assert.equal(window.INTERSECTION_autoCoverageStatus?.completed,true);
 return {host,searchRequests:calls.length,enabled:expected};
}
(async()=>{
 const a=await run("intersection-originals-free.onrender.com");
 const b=await run("koith.github.io");
 const c=await run("untrusted.example");
 console.log("RENDER_FREE_SNS_DISCOVERY_PASS",JSON.stringify([a,b,c]));
})().catch(error=>{console.error(error);process.exitCode=1});
