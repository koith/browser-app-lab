'use strict';
/* Live Chromium/WebKit test: a central authority is READY when it lists a
 * real user-created PUBLIC room, but its subsequent join returns HTTP 503.
 * Enter only as clearly labelled offline/local and never impersonate the
 * authority. A failed server CREATE must be visible on the real source field.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errs=[],custom={
  id:'server-user-public-1',name:'재연결 직전 채팅방',region:'north',
  district:'실버 호라이즌',capacity:4,background:3,locked:false,
  preset:false,occupants:0,created:1,isOwner:false
 };
 page.on('pageerror',e=>errs.push(String(e)));
 await page.route('https://chat-flaky.test/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(path==='/api/session')return route.fulfill({status:201,contentType:'application/json',
   body:JSON.stringify({token:'a'.repeat(64),id:'server-test-user',room:null})});
  if(path==='/api/rooms'&&req.method()==='GET')
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({rooms:[custom]})});
  if(path==='/api/snapshot')
   return route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({roomId:null,nextSequence:0,messages:[],peers:[]})});
  if(path==='/api/rooms'&&req.method()==='POST')
   return route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({error:'Room limit reached'})});
  if(path==='/api/rooms/'+custom.id+'/join')
   return route.fulfill({status:503,contentType:'text/html',body:'<h1>Temporarily Unavailable</h1>'});
  return route.fulfill({status:200,contentType:'application/json',body:'{}'});
 });
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='https://chat-flaky.test'});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().centralReady,{timeout:15000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').first().click();
  const marker=page.locator('.social-directory-row[data-room="server-user-public-1"]');
  await marker.waitFor();
  await marker.click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room');
  const state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.offlineRoom,true,'real server public room must be locally joinable during a temporary 503');
  assert.equal(state.roomId,custom.id,'keep the original server room identity');
  assert.match(await page.locator('#social-location-title').textContent(),/오프라인/);
  await page.locator('#message').fill('서버 장애에도 방 입장 후 실제 로컬 채팅');
  await page.locator('#chat-form button[type="submit"]').click();
  assert.match(await page.locator('#chat-log').textContent(),/서버 장애에도 방 입장 후 실제 로컬 채팅/);
  await page.locator('#social-back').click();
  await page.locator('#social-new-room').click();
  const name=page.locator('#social-modal [name="name"]');
  await name.fill('서버 실패 안내 검증');
  await page.locator('#social-modal button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#social-modal [name="name"]')?.validity.customError);
  assert.match(await name.evaluate(el=>el.validationMessage),/개설 실패/);
  await name.fill('다시 입력하면 수정 가능');
  assert.equal(await name.evaluate(el=>el.validity.customError),false,
   'editing the native owner field must permit retry after a failed server create');
  assert.deepEqual(errs,[]);
  console.log('4LEAF_CENTRAL_READY_THEN_503_PUBLIC_ROOM_PASS',JSON.stringify({
   engine:engine.name(),offlineRoom:state.offlineRoom,roomId:state.roomId,
   realLocalChat:true,createFailureVisible:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_CENTRAL_READY_THEN_503_PUBLIC_ROOM_FAIL',e.stack||e);process.exit(1)});
