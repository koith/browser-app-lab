'use strict';
/* The real central.cjs already exposes exactly eight usable, permanent
 * server-authoritative room IDs per 16 4LEAF ChatTown districts.
 * Verify production UI shows them BEFORE the backend answers. No invented
 * historical usernames, occupancy, fake NPCs, or screenshots as hit areas. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1100,height:850},
  serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  for(const region of ['north','south']){
   await page.evaluate(region=>{
    window.__LEAF_SOCIAL__.openRegion(region);
    window.__ROG_TEST__.go('rooms');
   },region);
   for(let i=0;i<8;i++){
    await page.locator('.social-district-hotspot').nth(i).click();
    const rows=await page.evaluate(()=>{
     const r=window.__LEAF_SOCIAL__.getState();
     return {state:r,buttons:[...document.querySelectorAll('.social-directory-row')].map(b=>({
      id:b.dataset.room,preset:b.dataset.permanent,
      title:b.title,count:b.querySelector('.social-room-users')?.textContent,
      hasNativeHitArea:b.tagName==='BUTTON',disabled:b.disabled
     }))};
    });
    assert.equal(rows.state.view,'directory');
    assert.equal(rows.buttons.length,8,'all 16 actual regions display eight joinable server slots');
    assert.deepEqual(rows.buttons.map(b=>b.id),
     Array.from({length:8},(_,n)=>'leaf-public-'+region+'-'+i+'-'+n));
    assert.ok(rows.buttons.every(b=>b.preset==='true'&&b.count==='0/12명'
     &&b.hasNativeHitArea&&!b.disabled),
     'canonical server rooms stay clickable, no invented occupants');
    await page.locator('#social-back').click();
   }
  }
  await page.evaluate(()=>window.__LEAF_SOCIAL__.openRegion('north'));
  await page.locator('.social-district-hotspot').nth(3).click();
  const first=page.locator('.social-directory-row[data-room="leaf-public-north-3-0"]');
  assert.equal(await first.isVisible(),true);
  await first.click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  assert.equal(await page.locator('.social-avatar.self').count(),1,
   'the joined local original room is a real room without bot occupants');
  await page.locator('#message').fill('상설방 실제 전송 시험');
  await page.locator('#chat-form button[type="submit"]').click();
  assert.ok((await page.locator('#chat-log').textContent()).includes('상설방 실제 전송 시험'),
   'offline local-room path still supports actual chat input');
  await page.locator('#social-back').click();
  assert.equal(await page.locator('.social-directory-row[data-permanent="true"]').count(),8,
   'permanent rooms survive exit without needing real users to create them');
  await page.screenshot({path:'leaf-permanent-chatrooms-source-district.png'});
  assert.deepEqual(errors,[],'no exceptions through all canonical regions');
  console.log('ALL 128 CANONICAL CHAT ROOMS + REAL JOIN/CHAT PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error('CANONICAL CHAT ROOM FAILED',e.stack||e);process.exit(1)});
