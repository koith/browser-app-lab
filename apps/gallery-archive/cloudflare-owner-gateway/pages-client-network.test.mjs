import assert from 'node:assert/strict';
import {pagesGateway} from './pages-client.mjs';

// All fixtures are synthetic. These test retry policy only, never claim
// real owner bytes, a successful production deployment, or browser decoding.
const SHA='a'.repeat(64),SIG='b'.repeat(64),NOW=1700000000000;
const endpoint='https://gallery-retry-example.workers.dev/';
const photo={ownerAlbum:'teddy-bear97',number:1,sha256:SHA,bytes:20000};
const expires=Math.floor(NOW/1000)+180;
const media=new URL('api/v1/media/yui/teddy-bear97/1/original',endpoint);
media.search=new URLSearchParams({h:SHA,b:'20000',e:String(expires),s:SIG}).toString();
const ok={status:200,redirected:false,json:async()=>({
 url:media.href,sha256:SHA,bytes:20000,expires_at:expires
})};
function gallery(fetcher){
 return pagesGateway({endpoint,model:'yui',fetcher,now:()=>NOW});
}
async function run(){
 let calls=0;
 const g=gallery(async (url,init)=>{
   calls++;
   assert.equal(url.pathname,'/api/v1/sign');
   assert.equal(init.credentials,'omit');
   assert.equal(init.redirect,'error');
   if(calls<3)throw new TypeError('temporary network/CORS transport failure');
   return ok;
 });
 const results=await Promise.all([g.asset(photo,'original'),g.asset(photo,'original')]);
 assert.deepEqual(results,[media.href,media.href]);
 assert.equal(calls,3,'exactly 2 bounded retries, coalesced in-flight lookup');
 assert.equal(await g.asset(photo,'original'),media.href);
 assert.equal(calls,3,'valid signed cache avoids extra network');

 calls=0;
 await assert.rejects(gallery(async()=>{calls++;return {status:403,redirected:false}}).asset(photo,'original'),/GALLERY_GATEWAY_HTTP_403/);
 assert.equal(calls,1,'authorization denial must never retry');
 calls=0;
 await assert.rejects(gallery(async()=>{calls++;return {status:404,redirected:false}}).asset(photo,'original'),/GALLERY_GATEWAY_HTTP_404/);
 assert.equal(calls,1,'HTTP 404 is not a network TypeError');
 calls=0;
 await assert.rejects(gallery(async()=>{calls++;throw Error('INVALID_SIGNED_PHOTO')}).asset(photo,'original'),/INVALID_SIGNED_PHOTO/);
 assert.equal(calls,1,'invalid source is never retried');
 calls=0;
 await assert.rejects(gallery(async()=>{calls++;throw new TypeError('permanent network failure')}).asset(photo,'original'),TypeError);
 assert.equal(calls,3,'permanent network failure must be bounded');
 // Actual HTTP response error is not a browser TypeError. Perform one
 // bounded attempt after a temporary 503, keeping the EXACT JSON body.
 calls=0;let firstBody;
 const g503=gallery(async(url,init)=>{
   calls++;
   if(!firstBody)firstBody=init.body;
   assert.equal(init.body,firstBody,'retries must not change photo identity');
   return calls===1?{status:503,redirected:false}:ok;
 });
 assert.equal(await g503.asset(photo,'original'),media.href);
 assert.equal(calls,2,'503 gets one and only one idempotent retry');
 calls=0;
 await assert.rejects(gallery(async()=>{calls++;return {status:503,redirected:false};})
   .asset(photo,'original'),/GALLERY_GATEWAY_HTTP_503/);
 assert.equal(calls,2,'permanent 503 must not trigger unbounded requests');
 calls=0;
 assert.equal(await gallery(async()=>{
   calls++;return calls===1?{status:429,redirected:false,headers:{get:()=> '1'}}:ok;
 }).asset(photo,'original'),media.href);
 assert.equal(calls,2,'429 with short Retry-After retries only once');
 calls=0;
 await assert.rejects(gallery(async()=>{
   calls++;return {status:429,redirected:false,headers:{get:()=> '120'}};
 }).asset(photo,'original'),/GALLERY_GATEWAY_HTTP_429/);
 assert.equal(calls,1,'long Retry-After must fail closed, no rate-limit bypass');
 calls=0;
 await assert.rejects(gallery(async()=>{
   calls++;return {status:429,redirected:false,headers:{get:()=> '1'}};
 }).asset(photo,'original'),/GALLERY_GATEWAY_HTTP_429/);
 assert.equal(calls,2,'repeat 429 must stop after one deferred retry');
 console.log('G09_REAL_HTTP_429_503_RETRY_AFTER_LIMITED_AUTH_FAIL_CLOSED_PASS');
 console.log('G09_SIGN_RETRY_NETWORK_ONLY_BOUNDED_CACHED_NO_HTTP_AUTH_BYPASS_PASS');
}
run().catch(error=>{console.error(error);process.exitCode=1});
