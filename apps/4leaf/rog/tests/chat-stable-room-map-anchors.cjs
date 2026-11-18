'use strict';
/* Real browser: adding and closing rooms must not shift existing map markers.
 * This verifies interaction stability, NOT native 2002 room coordinates.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:15000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  const snapshot=()=>page.evaluate(()=>Object.fromEntries(
   [...document.querySelectorAll('.social-map-rooms>.social-directory-row')].map(el=>
    [el.dataset.room,[el.style.left,el.style.top]])));
  const before=await snapshot();
  assert.equal(Object.keys(before).length,8);
  assert.equal(new Set(Object.values(before).map(v=>v.join(','))).size,8,
   'initial eight map room positions must be distinct');
  const create=async name=>{
   await page.locator('#social-new-room').click();
   await page.locator('#social-modal [name="name"]').fill(name);
   await page.locator('#social-modal button[type="submit"]').click();
   await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room',null,{timeout:15000});
   const id=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
   assert.ok(id.startsWith('leaf-local-'),'offline test creates a real persisted local room');
   await page.locator('#social-back').click();
   await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory',null,{timeout:8000});
   return id;
  };
  const a=await create('고정 좌표 실사용 테스트 1');
  const afterA=await snapshot();
  for(const [id,coords] of Object.entries(before))
   assert.deepEqual(afterA[id],coords,'canonical map marker moved after CREATE: '+id);
  assert.ok(afterA[a]);
  const b=await create('고정 좌표 실사용 테스트 2');
  const afterB=await snapshot();
  for(const [id,coords] of Object.entries(afterA))
   assert.deepEqual(afterB[id],coords,'existing room moved after second CREATE: '+id);
  assert.ok(afterB[b]);
  assert.equal(new Set(Object.values(afterB).map(v=>v.join(','))).size,10,
   'all ten room map hit targets must have unique positions');
  // Reload can reorder the local room catalogue (newest first). Its marker
  // coordinates must remain fixed because the assignments are persisted.
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  const afterReload=await snapshot();
  assert.deepEqual(afterReload,afterB,'reload must not reshuffle user-created rooms');
  await page.locator('.social-directory-row[data-room="leaf-public-north-3-0"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room',null,{timeout:15000});
  await page.locator('#message').fill('기존 방 좌표 유지 후 실제 입장 확인');
  await page.locator('#chat-form button[type="submit"]').click();
  assert.match(await page.locator('#chat-log').textContent(),/기존 방 좌표 유지 후 실제 입장 확인/);
  assert.deepEqual(errors,[]);
  console.log('STABLE_MAP_ROOM_ANCHORS_PASS',JSON.stringify({
   browser:engine.name(),initial:8,afterCreate:10,originalRoomStillJoinable:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('STABLE_MAP_ROOM_ANCHORS_FAILED',e.stack||e);process.exit(1)});
