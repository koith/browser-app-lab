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
  // Two SEPARATE authenticated browser contexts click the SAME genuine
  // source room seat at the SAME TIME. Backend reserves unique logical
  // positions and each browser must show its server-confirmed figure slot.
  await Promise.all([host,guest].map(page=>page.evaluate(()=>{
   const frame=document.getElementById('social-image-frame');
   const box=frame.getBoundingClientRect();
   frame.dispatchEvent(new MouseEvent('click',{bubbles:true,
    clientX:box.left+box.width*.21,clientY:box.top+box.height*.66}));
  })));
  const realPeers=await Promise.all([host,guest].map(async page=>{
   await page.waitForFunction(()=>{
    const people=window.__LEAF_SOCIAL__?.getState()?.people||[];
    const seats=[...document.querySelectorAll('#social-avatar-layer .social-avatar')];
    return people.length===2&&seats.length===2&&
     new Set(people.map(p=>p.position.x+','+p.position.y)).size===2&&
     new Set(seats.map(p=>p.dataset.seat)).size===2&&
     seats.every(p=>Number.isFinite(Number(p.dataset.seat)));
   },null,{timeout:15000});
   return page.evaluate(()=>({
    logical:window.__LEAF_SOCIAL__.getState().people.map(p=>({
     id:p.id,position:p.position})),
    rendered:[...document.querySelectorAll('#social-avatar-layer .social-avatar')].map(p=>
     ({id:p.dataset.peer,seat:p.dataset.seat}))
   }));
  }));
  assert.ok(realPeers.every(view=>
   new Set(view.logical.map(p=>p.position.x+','+p.position.y)).size===2&&
   new Set(view.rendered.map(p=>p.seat)).size===2),
   'two real central users cannot occupy the same original Registry seat on either device: '+JSON.stringify(realPeers));
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
  // The ACTUAL two separate browsers use the original native Registry
  // actor menu. A real authenticated owner can transfer ownership to a
  // live peer, who then inherits the source owner toolbar server-side.
  await host.locator('.social-avatar:not(.self)').click();
  await host.locator('[data-moderation="transfer"]').click();
  await host.locator('#social-modal [data-room-moderation="transfer"]').click();
  await guest.waitForFunction(()=>Boolean(document.getElementById('social-close-room')),
   null,{timeout:15000});
  await host.waitForFunction(()=>!document.getElementById('social-close-room'),
   null,{timeout:15000});
  // The new owner can genuinely remove their predecessor; the backend
  // revokes room membership, chat and seat, not just a visual avatar.
  await guest.locator('.social-avatar:not(.self)').click();
  await guest.locator('[data-moderation="kick"]').click();
  await guest.locator('#social-modal [data-room-moderation="kick"]').click();
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory',
   null,{timeout:15000});
  assert.equal(await host.evaluate(()=>window.__LEAF_CENTRAL_CHAT__.joinedId),null,
   'kicked owner must have server-revoked membership, not a merely hidden actor');
  await guest.reload();
  await guest.waitForFunction(id=>
   window.__LEAF_CENTRAL_CHAT__?.ready&&
   window.__LEAF_SOCIAL__?.getState()?.roomId===id&&
   Boolean(document.getElementById('social-close-room')),newRoom,{timeout:15000});
  await guest.locator('#social-close-room').click();
  await guest.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory',
   null,{timeout:15000});
  assert.deepEqual(errors,[]);
  console.log('CENTRAL CHAT BROWSER PASS: independent peer chat, native seats, private owner transfer, kick, reload, closure');
 }finally{await browser.close()}
})().catch(e=>{console.error('CENTRAL CHAT BROWSER FAIL',e.stack||e);process.exit(1)});
