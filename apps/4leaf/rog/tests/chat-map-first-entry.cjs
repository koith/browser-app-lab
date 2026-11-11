'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  const map=page.locator('#rooms .social-directory');
  assert.ok(await map.evaluate(e=>e.classList.contains('web-estate-open')),
   'native ChatTown room map must be DEFAULT; no directory list gate');
  assert.equal(await page.locator('#social-web-estate-toggle').innerText(),'목록');
  await page.locator('#social-new-room').click();
  await page.locator('#social-modal form [name="name"]').fill('지도 입장 QA 방');
  await page.locator('#social-modal form button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  const id=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
  await page.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
  await page.waitForFunction(()=>document.querySelector('#rooms .social-directory.web-estate-open'));
  const target=page.locator('#social-directory-list .social-directory-row').filter({hasText:'지도 입장 QA 방'});
  assert.equal(await target.count(),1);
  assert.ok((await target.getAttribute('aria-label')).startsWith('지도에서 '));
  await target.click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId),id);
  await page.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
  await page.locator('#social-web-estate-toggle').click();
  assert.equal(await map.evaluate(e=>e.classList.contains('web-estate-open')),false,
   'optional list accessible without replacing map-first default');
  assert.deepEqual(errors,[]);
  console.log('CHATTOWN_MAP_FIRST_ROOM_ENTRY_PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error('CHATTOWN_MAP_FIRST_ROOM_ENTRY_FAIL',e.stack||e);process.exit(1)});
