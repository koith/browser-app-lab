'use strict';
/* ChatTown source scene user journey: map-first room click, not list-first.
 * Verify real WorldMap region -> original ChatTown district -> clickable
 * spatial room map -> actual ChatRoom interior -> real local message -> exit
 * back to MAP, on Chromium desktop and WebKit/touch phone. Historical ROOM
 * coordinate table is explicitly not source-verified. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const phone=process.env.FOURLEAF_MOBILE==='1';
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const context=await browser.newContext({
  viewport:phone?{width:390,height:844}:{width:1280,height:850},
  isMobile:phone,hasTouch:phone,serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:30000});
  const world=page.locator('.world-location[data-region="north"]');
  if(phone)await world.tap();else await world.click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
  const district=page.locator('.social-district-hotspot').first();
  if(phone)await district.tap();else await district.click();
  await page.locator('.social-directory.web-estate-open[data-default-view="map"]').waitFor();
  assert.equal(await page.locator('#social-web-estate-toggle').textContent(),'목록',
   'native room entry must default to MAP with the list as optional access');
  assert.equal(await page.locator('#social-web-estate-toggle').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('.social-directory-row').count(),8);
  const state=await page.evaluate(()=>{
   const v=document.getElementById('social-map-viewport');
   const p=document.getElementById('social-map-plane');
   return {viewport:v.getBoundingClientRect().toJSON(),transform:getComputedStyle(p).transform,
    terrain:p.dataset.terrain,background:getComputedStyle(p).backgroundImage,
    roomNames:[...document.querySelectorAll('#social-directory-list .social-directory-row')]
     .map(e=>e.getAttribute('aria-label'))};
  });
  assert.equal(state.terrain,'unverified','room coords are NOT original EXE source');
  assert.ok(state.roomNames.every(x=>x.includes('채팅방 입장')));
  assert.ok(!state.roomNames.some(x=>!x),'all real destinations must be keyboard accessible');
  await page.screenshot({path:'chat-map-first-'+engine.name()+(phone?'-phone':'-desktop')+'.png'});
  // This is a TRUE spatial button situated at a map coordinate; no list
  // navigation, no test-only game or chat state injection.
  const room=page.locator('.social-directory-row[data-room="leaf-public-north-0-0"]');
  if(phone)await room.tap();else await room.click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room',null,{timeout:15000});
  const joined=await page.evaluate(()=>({
   roomId:window.__LEAF_SOCIAL__.getState().roomId,
   bg:document.getElementById('social-image-frame')?.style.backgroundImage,
   localActors:document.querySelectorAll('.social-avatar.self').length
  }));
  assert.equal(joined.roomId,'leaf-public-north-0-0');
  assert.ok(joined.bg.includes('/ChatRoom/room'), 'room must use archived ROOM interior, not room list');
  assert.equal(joined.localActors,1,'real own avatar visible in the room');
  await page.locator('#message').fill('지도에서 직접 입장한 실제 채팅');
  await page.locator('#chat-form button[type="submit"]').click();
  assert.ok((await page.locator('#chat-log').textContent()).includes('지도에서 직접 입장한 실제 채팅'));
  if(phone)await page.locator('#social-back').tap();else await page.locator('#social-back').click();
  await page.locator('.social-directory.web-estate-open').waitFor();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory',
   'room exit must RETURN to clickable room map');
  assert.equal(await page.locator('.social-directory-row').count(),8);
  // Optional accessibility list must not become the primary navigation.
  await page.locator('#social-web-estate-toggle').click();
  assert.equal(await page.locator('.social-directory:not(.web-estate-open)').count(),1);
  await page.locator('#social-web-estate-toggle').click();
  assert.equal(await page.locator('.social-directory.web-estate-open').count(),1);
  assert.deepEqual(errors,[],'actual room transitions must not throw exceptions');
  console.log('4LEAF_CHAT_MAP_FIRST_REAL_JOURNEY_PASS',JSON.stringify({
   browser:engine.name(),phone,terrain:state.terrain,room:joined.roomId,
   mappedRooms:state.roomNames.length,joinedActualRoom:true,returnedToMap:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_CHAT_MAP_FIRST_REAL_JOURNEY_FAIL',e.stack||String(e));process.exit(1)});
