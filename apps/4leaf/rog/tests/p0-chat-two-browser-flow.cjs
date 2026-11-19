'use strict';
/* P0-CHAT acceptance flow: two SEPARATE browser processes (no shared
 * BroadcastChannel or storage) joined only through the central chat API.
 *   map -> "+ 방 만들기" -> enter -> 2nd browser enters from the map card ->
 *   messages both ways (log line "name : text" + speech balloon over the
 *   speaker) -> both rosters/avatars/count show both people -> EXIT ->
 *   join/leave presence lines -> re-entry from the map -> message again.
 * Views: desktop 1280x850 and phone landscape 844x390 (touch).
 * Every click is a real hit-tested click on a visible control.
 *
 * Server: by default this starts the repository's server/central.cjs on a
 * free local port. LEAF_CENTRAL_API_URL=<url> uses an existing server;
 * LEAF_CENTRAL_API_URL=page keeps the page's own <meta leaf-central-api>
 * (for the public Pages + Render check). FOURLEAF_TEST_URL sets the page. */
const assert=require('node:assert/strict');
const path=require('node:path');
const os=require('node:os');
const fs=require('node:fs');
const {spawn}=require('node:child_process');
const net=require('node:net');
const {chromium,webkit}=require('playwright');
const BASE=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const ENGINE=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const VIEWS=(process.env.P0_CHAT_VIEWS||'desktop,phone-landscape').split(',');
const VIEW_SPEC={
 'desktop':{viewport:{width:1280,height:850}},
 'phone-landscape':{viewport:{width:844,height:390},isMobile:true,hasTouch:true,deviceScaleFactor:3}
};
const freePort=()=>new Promise((ok,no)=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>ok(p))});s.on('error',no)});
async function startCentral(){
 if(process.env.LEAF_CENTRAL_API_URL)return {api:process.env.LEAF_CENTRAL_API_URL,stop(){}};
 const port=await freePort();
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'leaf-p0-chat-'));
 const child=spawn(process.execPath,[path.join(__dirname,'..','server','central.cjs')],
  {env:{...process.env,PORT:String(port),HOST:'127.0.0.1',LEAF_CENTRAL_ORIGINS:new URL(BASE).origin,LEAF_CENTRAL_STORAGE:path.join(dir,'central.json')},stdio:['ignore','pipe','pipe']});
 const api='http://127.0.0.1:'+port;
 for(let i=0;i<100;i++){
  try{const r=await fetch(api+'/api/health');if(r.ok)return {api,stop(){child.kill()}}}catch{}
  await new Promise(r=>setTimeout(r,100));
 }
 child.kill();throw Error('local central server did not start');
}
async function user(api,view,name){
 const browser=await ENGINE.launch(ENGINE===chromium?{args:['--no-sandbox']}:{});
 const ctx=await browser.newContext({...VIEW_SPEC[view],serviceWorkers:'block'});
 if(api!=='page')await ctx.addInitScript(a=>{window.LEAF_CENTRAL_API_URL=a},api);
 const page=await ctx.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(BASE);
 await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_CHATROOM_SCREEN__&&window.__LEAF_CENTRAL_CHAT__?.ready,null,{timeout:30000});
 await page.evaluate(n=>{const e=document.getElementById('profile-name');if(e)e.textContent=n},name);
 return {browser,page,errors,name};
}
async function hitClick(page,loc,label){
 await loc.scrollIntoViewIfNeeded().catch(()=>{});
 assert.ok(await loc.boundingBox(),label+' is visible');
 // A transient overlay (route fade, toast) may sit on the control for a
 // moment on a slow runner; a real user waits for it. It must clear in 5 s.
 let hit='';
 for(let i=0;i<25;i++){
  hit=await loc.evaluate(e=>{const r=e.getBoundingClientRect();const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   return t===e||e.contains(t)?'':(t?.id||'')+'.'+String(t?.className||'')+' '+String(t?.textContent||'').slice(0,40)});
  if(!hit)break;await page.waitForTimeout(200);
 }
 assert.equal(hit,'',label+' is not covered');
 await loc.click();
}
async function toMap(u){
 await hitClick(u.page,u.page.getByRole('button',{name:/북 하이아칸/}).first(),'north town');
 await u.page.locator('.social-district-hotspot').nth(2).waitFor({state:'visible'});
 await hitClick(u.page,u.page.locator('.social-district-hotspot').nth(2),'district');
 await u.page.locator('#social-new-room').waitFor({state:'visible',timeout:20000});
}
const view=page=>page.evaluate(()=>({
 view:window.__LEAF_SOCIAL__.getState().view,
 avatars:[...document.querySelectorAll('#social-avatar-layer .social-avatar .social-avatar-name')].map(e=>e.textContent).sort(),
 roster:[...document.querySelectorAll('#social-peer-list .social-user-row b')].map(e=>e.textContent).sort(),
 count:document.getElementById('social-native-user-count')?.textContent||'',
 lines:[...document.querySelectorAll('#chat-log>*')].map(e=>e.textContent)}));
const waitLog=(page,text)=>page.waitForFunction(t=>[...document.querySelectorAll('#chat-log>*')].some(e=>e.textContent===t),text,{timeout:30000});
const waitAvatars=(page,n)=>page.waitForFunction(n=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===n,n,{timeout:30000});
async function say(u,text){await u.page.locator('#message').fill(text);await u.page.locator('#message').press('Enter')}
async function balloonOn(page,speaker,text){
 // the reader's page shows the speaker's balloon above the speaker's head
 await page.waitForFunction(t=>[...document.querySelectorAll('#social-avatar-layer .leaf-speech-layer>.social-speech')].some(b=>b.textContent.includes(t)),text,{timeout:15000});
 return page.evaluate(([speaker,text])=>{
  const frame=document.getElementById('social-image-frame').getBoundingClientRect();
  const b=[...document.querySelectorAll('#social-avatar-layer .leaf-speech-layer>.social-speech')].find(x=>x.textContent.includes(text));
  const av=[...document.querySelectorAll('#social-avatar-layer .social-avatar')].find(a=>a.querySelector('.social-avatar-name')?.textContent===speaker);
  const br=b.getBoundingClientRect(),ir=av.querySelector('img').getBoundingClientRect();
  const sx=frame.width/794;
  return {tag:b.querySelector('.leaf-speech-tag')?.textContent,text:b.querySelector('.native-talkbox-text')?.textContent,
   centerOff:Math.abs((br.left+br.width/2)-(ir.left+ir.width/2))/sx,
   aboveHead:br.top<ir.top+13*sx,insideFrame:br.left>=frame.left-1&&br.right<=frame.right+1&&br.top>=frame.top-1};
 },[speaker,text]);
}
async function run(api,viewName){
 const A=await user(api,viewName,'겔드'),B=await user(api,viewName,'일루드');
 const rec={view:viewName};
 try{
  await toMap(A);await toMap(B);
  await hitClick(A.page,A.page.locator('#social-new-room'),'+ 방 만들기');
  const roomName='P0 '+viewName.slice(0,5)+' '+Date.now()%100000;
  await A.page.locator('#social-modal [name="name"]').fill(roomName);
  await hitClick(A.page,A.page.locator('#social-modal button[type="submit"]'),'create');
  await A.page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',null,{timeout:30000});
  assert.deepEqual((await view(A.page)).roster,['겔드'],'creator alone in the new room');
  // second browser finds the room on the map and enters through its card
  const card=B.page.locator('.social-map-rooms>button',{hasText:roomName});
  await card.first().waitFor({state:'attached',timeout:30000});
  await hitClick(B.page,card.first(),'room card');
  await B.page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',null,{timeout:30000});
  await waitAvatars(A.page,2);await waitAvatars(B.page,2);
  for(const u of [A,B]){
   const v=await view(u.page);
   assert.deepEqual(v.avatars,['겔드','일루드'],u.name+' sees both avatars');
   assert.deepEqual(v.roster,['겔드','일루드'],u.name+' roster lists both');
   assert.match(v.count,/^2\s*명$/,u.name+' participant count');
  }
  await waitLog(A.page,'- 일루드 님이 들어왔습니다. -');
  // messages both ways: original log line "name : text" and a balloon
  await say(A,'안녕 일루드');
  await waitLog(B.page,'겔드 : 안녕 일루드');await waitLog(A.page,'겔드 : 안녕 일루드');
  rec.balloonOnB=await balloonOn(B.page,'겔드','안녕 일루드');
  await say(B,'반가워요 겔드');
  await waitLog(A.page,'일루드 : 반가워요 겔드');
  rec.balloonOnA=await balloonOn(A.page,'일루드','반가워요 겔드');
  for(const b of [rec.balloonOnA,rec.balloonOnB]){
   assert.ok(b.tag&&b.text,'balloon carries the speaker tag and the text '+JSON.stringify(b));
   assert.ok(b.centerOff<=2&&b.aboveHead&&b.insideFrame,'balloon sits over the speaker '+JSON.stringify(b));
  }
  await A.page.waitForTimeout(300);
  await A.page.screenshot({path:'p0-chat-'+viewName+'-A.png'}).catch(()=>{});
  await B.page.screenshot({path:'p0-chat-'+viewName+'-B.png'}).catch(()=>{});
  // EXIT, presence line, re-entry from the map
  await hitClick(B.page,B.page.locator('#social-back'),'EXIT');
  await B.page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='directory',null,{timeout:20000});
  await waitAvatars(A.page,1);
  await waitLog(A.page,'- 일루드 님이 나갔습니다. -');
  assert.deepEqual((await view(A.page)).roster,['겔드'],'roster drops the leaver');
  const card2=B.page.locator('.social-map-rooms>button',{hasText:roomName});
  await card2.first().waitFor({state:'attached',timeout:30000});
  await hitClick(B.page,card2.first(),'room card again');
  await waitAvatars(A.page,2);await waitAvatars(B.page,2);
  await say(B,'다시 왔어요');
  await waitLog(A.page,'일루드 : 다시 왔어요');
  const linesA=(await view(A.page)).lines,linesB=(await view(B.page)).lines;
  assert.equal(linesA.filter(l=>l==='- 일루드 님이 들어왔습니다. -').length,2,'A sees both entries');
  assert.ok(!linesB.some(l=>l==='- 겔드 님이 들어왔습니다. -'),'B is not told that the person already inside entered');
  assert.ok(!linesA.concat(linesB).some(l=>/\d{1,2}:\d{2}/.test(l)),'no web timestamps in the log');
  rec.linesA=linesA;rec.linesB=linesB;
  assert.deepEqual(A.errors,[]);assert.deepEqual(B.errors,[]);
  return rec;
 }finally{await A.browser.close();await B.browser.close()}
}
(async()=>{
 const central=await startCentral();
 try{
  for(const v of VIEWS){const rec=await run(central.api,v);console.log(JSON.stringify(rec))}
  console.log('P0 CHAT TWO BROWSER FLOW PASS',ENGINE.name(),VIEWS.join(','));
 }finally{central.stop()}
})().catch(e=>{console.error('P0 CHAT TWO BROWSER FLOW FAILED',e.stack||e);process.exit(1)});
