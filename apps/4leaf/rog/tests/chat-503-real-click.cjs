'use strict';
/* LIVE click regression. A configured-but-unavailable (HTTP 503) central
 * service MUST NOT leave every 4LEAF chat-room marker and CREATE unusable.
 * This checks only honestly marked local room behavior, not internet chat. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.route('https://chat-503.test/**',async route=>{
  await route.fulfill({status:503,contentType:'text/html',body:'<h1>Service Unavailable</h1>'});
 });
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='https://chat-503.test'});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
  });
  await page.locator('.social-district-hotspot').first().click();
  assert.equal(await page.locator('.social-directory-row').count(),8);
  const marker=page.locator('.social-directory-row[data-room="leaf-public-north-0-0"]');
  await marker.click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  let state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.offlineRoom,true,'503 must use visibly local-only admission');
  assert.equal(state.roomId,'leaf-public-north-0-0');
  assert.match(state.scope,/^offline-room:/);
  assert.match(await page.locator('#social-location-title').textContent(),/오프라인/);
  assert.equal(await page.locator('.social-avatar.self').count(),1,
   'offline room must render the real local avatar, not an empty interior');
  await page.locator('#message').fill('503 방 입장 및 로컬 채팅 검증');
  await page.locator('#chat-form button[type="submit"]').click();
  assert.match(await page.locator('#chat-log').textContent(),/503 방 입장 및 로컬 채팅 검증/);
  await page.locator('#social-back').click();
  await page.locator('#social-new-room').click();
  await page.locator('#social-modal [name="name"]').fill('503 로컬 생성');
  await page.locator('#social-modal form button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.offlineRoom,true);
  assert.ok(state.roomId.startsWith('leaf-local-'),'offline created rooms must not impersonate server rooms');
  await page.locator('#social-back').click();
  assert.ok(await page.locator('.social-directory-row[data-room^="leaf-local-"]').count(),
   'locally created room must persist in the map');
  assert.deepEqual(errors,[]);
  console.log('4LEAF_CHAT_503_REAL_CLICK_PASS',JSON.stringify({presetEntered:true,created:true,roomId:state.roomId,localOnly:true}));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error('4LEAF_CHAT_503_REAL_CLICK_FAIL',e.stack||e);process.exitCode=1});
