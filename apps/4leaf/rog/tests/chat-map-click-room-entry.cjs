'use strict';
/* R19: REAL click-through, no hidden navigate('rooms')/joinRoom cheats.
 * Original ChatTown district source -> spatial room MAP -> actual room
 * click -> live ChatRoom -> back to spatial room map -> another room.
 * Source client exact historical room coordinates are not verified. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const mobile=process.env.FOURLEAF_MOBILE==='1';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_WORLD__,null,{timeout:30000});
  const press=async el=>mobile?el.tap():el.click();
  const world=page.locator('.world-location[data-region="north"]');
  await press(world);
  await page.locator('#rooms:not(.hidden)').waitFor();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
  const town=page.locator('.social-district-hotspot');
  assert.equal(await town.count(),8);
  await press(town.first());
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory');
  const directory=await page.evaluate(()=>{
   const container=document.querySelector('#social-image-frame .social-directory');
   const map=document.getElementById('social-map-viewport');
   const rooms=[...document.querySelectorAll('#social-directory-list button')];
   const first=rooms[0]?.getBoundingClientRect(),view=map?.getBoundingClientRect();
   const styles=rooms[0]&&getComputedStyle(rooms[0]);
   return {defaultMode:container?.dataset.defaultRoomEntry,
    isSpatial:container?.classList.contains('web-estate-open'),
    toggle:document.getElementById('social-web-estate-toggle')?.textContent,
    togglePressed:document.getElementById('social-web-estate-toggle')?.getAttribute('aria-pressed'),
    rooms:rooms.length,roomId:rooms[0]?.dataset.room,
    position:styles?.position,left:styles?.left,top:styles?.top,
    button:first?.toJSON(),viewport:view?.toJSON(),
    caption:document.querySelector('.social-map-toolbar')?.textContent};
  });
  assert.equal(directory.defaultMode,'spatial-map');
  assert.equal(directory.isSpatial,true,'the actual map must be default, not hidden behind list toggle');
  assert.equal(directory.toggle,'목록');
  assert.equal(directory.togglePressed,'true');
  assert.ok(directory.rooms>=8,'canonical joinable rooms must be spatial entities');
  assert.equal(directory.position,mobile?'relative':'absolute',
   'desktop keeps source-map coordinates; phone uses native room buttons in readable map grid');
  assert.ok(directory.button.width>15&&directory.button.height>15);
  assert.ok(directory.caption.includes('원작 방 배치 좌표는 미확보'),
   'do not claim inferred geography is historically proven');
  if(mobile){
   assert.equal(await page.locator('#social-new-room').count(),1,
    'mobile map reuses exactly ONE original create button, not an obstructed clone');
   assert.equal(await page.locator('#social-mobile-room-map #social-new-room').count(),1);
   const createHit=await page.locator('#social-new-room').evaluate(el=>{
    const r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
    return {width:r.width,height:r.height,reachable:hit===el||el.contains(hit)};
   });
   assert.ok(createHit.width>=40&&createHit.height>=30&&createHit.reachable,
    'real create button must not be intercepted by mobile marker overlay');
   const pins=page.locator('#social-mobile-room-map .social-mobile-room-pin');
   assert.equal(await pins.count(),directory.rooms,'mobile map uses same room entities');
   const mobileReadable=await pins.first().evaluate(el=>{
    const rect=el.getBoundingClientRect();
    const label=el.querySelector('b');
    const labelSize=Number.parseFloat(getComputedStyle(label).fontSize);
    const occupancySize=Number.parseFloat(getComputedStyle(el.querySelector('small')).fontSize);
    const hit=document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2);
    return {width:rect.width,height:rect.height,labelSize,occupancySize,
     clickReachable:hit===el||el.contains(hit)};
   });
   assert.ok(mobileReadable.width>=130&&mobileReadable.height>=70,
    'real map rooms need 70px+ visible touch markers');
   assert.ok(mobileReadable.labelSize>=12&&mobileReadable.occupancySize>=10,
    'room names and occupancy must actually be readable on a phone');
   assert.ok(mobileReadable.clickReachable,'pin must be topmost at its real touch center');
  }
  await page.screenshot({path:'leaf-chat-map-primary-'+engine.name()+(mobile?'-mobile':'')+'.png'});
  // A direct map ROOM marker is an actual user click, never a text list choice.
  const first=mobile?page.locator('#social-mobile-room-map .social-mobile-room-pin').first():
    page.locator('#social-directory-list .social-directory-row').first();
  await first.scrollIntoViewIfNeeded();
  await press(first);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room',null,{timeout:20000});
  const entered=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(entered.roomId,directory.roomId);
  assert.ok(await page.locator('#social-image-frame.social-interior').count(),
   'live ChatRoom image must replace the map after the click');
  const back=page.locator('#social-back');
  await press(back);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='directory');
  assert.ok(await page.locator('#social-image-frame .social-directory.web-estate-open').count(),
   'EXIT must go BACK to spatial map by default, not a list');
  if(mobile)assert.ok(await page.locator('#social-mobile-room-map .social-mobile-room-pin').count(),
    'after EXIT mobile should return to readable original-style map markers');
  const next=mobile?page.locator('#social-mobile-room-map .social-mobile-room-pin').nth(1):
    page.locator('#social-directory-list .social-directory-row').nth(1);
  const secondId=await next.getAttribute('data-room');
  await next.scrollIntoViewIfNeeded();await press(next);
  await page.waitForFunction(id=>window.__LEAF_SOCIAL__?.getState().roomId===id,secondId,
   {timeout:20000});
  assert.notEqual(secondId,directory.roomId);
  console.log('CHAT_ORIGINAL_STYLE_MAP_CLICK_ROOM_ENTRY_PASS',JSON.stringify({
   engine:engine.name(),mobile,roomMarkers:directory.rooms,
   roomIds:[directory.roomId,secondId],returnedToMap:true}));
  assert.deepEqual(errors,[],'no JavaScript exception while navigating rooms');
 }finally{await browser.close()}
})().catch(e=>{console.error('CHAT_SPATIAL_MAP_ENTRY_FAILED',e.stack||String(e));process.exit(1)});
