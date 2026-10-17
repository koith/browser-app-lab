'use strict';
// Real Chromium, two independent browser contexts sharing only a central API.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const BASE='http://127.0.0.1:8765/',API='http://127.0.0.1:8877';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const a=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const b=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 await Promise.all([a.addInitScript(url=>window.LEAF_CENTRAL_API_URL=url,API),
                    b.addInitScript(url=>window.LEAF_CENTRAL_API_URL=url,API)]);
 const host=await a.newPage(),guest=await b.newPage();
 const errors=[];for(const p of [host,guest])p.on('pageerror',e=>errors.push(e.message));
 const enterTown=async page=>{
  await page.goto(BASE);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_CENTRAL_CHAT__?.ready,{timeout:12000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  assert.equal(await page.locator('.social-public-room').count(),0,'no fake public rooms');
  assert.equal(await page.locator('.social-directory-row[data-permanent="true"]').count(),8,
   'canonical permanent rooms must be visible even before a server refresh');
  assert.ok((await page.locator('.social-directory-row[data-permanent="true"] .social-room-users').allTextContents())
   .every(value=>value==='0/12명'),'no fake participants in permanent rooms');
 };
 try{
  await enterTown(host);await enterTown(guest);
  await host.locator('#social-new-room').click();
  await host.locator('#social-modal [name="name"]').fill('중앙 테스트 공개방');
  await host.locator('#social-modal button[type="submit"]').click();
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',{timeout:15000});
  const publicRoom=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
  await guest.waitForFunction(id=>document.querySelector('.social-directory-row[data-room="'+id+'"] .social-room-users')?.textContent==='1/12명',
   publicRoom,{timeout:15000});
  assert.equal(await guest.locator('.social-directory-row[data-room="'+publicRoom+'"] .social-room-users').textContent(),'1/12명',
   'central API occupancy is real, not a fake preset count');
  await guest.locator('.social-directory-row[data-room="'+publicRoom+'"]').evaluate(el=>el.click());
  await guest.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',{timeout:15000});
  await Promise.all([
   host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,{timeout:15000}),
   guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,{timeout:15000})
  ]);
  await host.locator('#message').fill('멀티기기 중앙 서버 메시지');
  await host.locator('#message').press('Enter');
  await guest.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('멀티기기 중앙 서버 메시지'),{timeout:15000});
  const before=await guest.locator('.social-avatar:not(.self) img').evaluate(el=>el.style.transform);
  await host.locator('.social-avatar.self').click();
  await guest.waitForFunction(initial=>{
   const avatar=document.querySelector('.social-avatar:not(.self) img');return avatar&&avatar.style.transform!==initial
  },before,{timeout:15000});
  await host.locator('#social-back').click();
  await host.waitForFunction(()=>window.__LEAF_CENTRAL_CHAT__.joinedId===null,{timeout:12000});
  await host.locator('#social-new-room').click();
  await host.locator('#social-modal [name="name"]').fill('중앙 테스트 비밀방');
  await host.locator('#social-modal [name="capacity"]').selectOption('2');
  await host.locator('#social-modal [name="password"]').fill('test123456');
  await host.locator('#social-modal button[type="submit"]').click();
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',{timeout:15000});
  const newRoom=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
  assert.ok(newRoom);
  await guest.locator('#social-back').click();
  await guest.waitForFunction(id=>document.querySelector('.social-directory-row[data-room="'+id+'"]'),newRoom,{timeout:15000});
  await guest.locator('.social-directory-row[data-room="'+newRoom+'"]').evaluate(el=>el.click());
  await guest.locator('#social-modal input[type="password"]').fill('test123456');
  await guest.locator('#social-modal button[type="submit"]').click();
  await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().roomId===id,newRoom,{timeout:15000});
  assert.equal(await guest.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'room');
  await host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,{timeout:15000});
  // SessionStorage survives reload, but not across independent contexts.
  // The authority alone decides whether the room/owner can be restored.
  await host.reload();
  await host.waitForFunction(id=>{
   const social=window.__LEAF_SOCIAL__,central=window.__LEAF_CENTRAL_CHAT__;
   return central?.ready&&central.joinedId===id&&social?.getState().roomId===id
    &&social.getState().view==='room';
  },newRoom,{timeout:15000});
  assert.equal(await host.locator('#social-close-room').count(),1,
   'the real server owner can still close the room after browser reload');
  await guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,{timeout:15000});
  await host.locator('#social-close-room').click();
  await guest.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory',{timeout:15000});
  assert.equal(await guest.evaluate(()=>window.__LEAF_CENTRAL_CHAT__.joinedId),null,
   'the guest is evicted from a room closed by its authenticated owner');
  assert.deepEqual(errors,[]);
  console.log('CENTRAL CHAT BROWSER PASS: independent peers, messaging, facing, secret room and capacity');
 }finally{await browser.close()}
})().catch(e=>{console.error('CENTRAL CHAT BROWSER FAIL',e.stack||e);process.exit(1)});
