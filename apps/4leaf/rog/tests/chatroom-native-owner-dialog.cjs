'use strict';
// Authentic 338x282 ChatRoom/ownerdialog.png with a working modern HTML form.
// This is NOT a screenshot covering a hidden room-creation modal.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];let transient=0,attempts=0;
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 await page.route('**/original/ChatRoom/ownerdialog.png*',async route=>{
  attempts++;
  if(transient<2){
   transient++;
   await route.fulfill({status:503,contentType:'text/plain',body:'Temporary CDN source art outage'});
  }else await route.continue();
 });
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_NATIVE_OWNER_DIALOG__);
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  assert.equal(await page.locator('.social-directory-row[data-permanent="true"]').count(),8,'real permanent ChatTown rooms are independent live routes, not fabricated users');
  await page.locator('#social-new-room').click();
  await page.waitForFunction(()=>document.querySelector('form.social-native-owner-form')?.dataset.nativeOwnerReady==='true',
    null,{timeout:18000});
  const source=await page.evaluate(async()=>{
   const form=document.querySelector('form.social-native-owner-form');
   const picture=new Image();picture.src='./original/ChatRoom/ownerdialog.png';
   await picture.decode();
   const art=form.querySelector('.social-owner-source-backdrop');
   const ctx=art.getContext('2d',{willReadFrequently:true});
   const image=ctx.getImageData(0,0,art.width,art.height).data;
   let keyed=0,visible=0;
   for(let i=0;i<image.length;i+=4){
    if(image[i+3]===0)keyed++;else visible++;
   }
   const origin=form.getBoundingClientRect();
   const field=(name)=>{
    const b=form.querySelector('[name="'+name+'"]').getBoundingClientRect();
    return {x:b.x-origin.x,y:b.y-origin.y,width:b.width,height:b.height};
   };
   return {
    atlas:[picture.naturalWidth,picture.naturalHeight],art:[art.width,art.height],
    keyed,visible,ready:form.dataset.nativeOwnerReady,
    source:form.dataset.nativeOwnerSource,
    frame:form.dataset.nativeOwnerAtlas,
    panelTitle:getComputedStyle(document.querySelector('.social-modal-title')).display,
    name:field('name'),capacity:field('capacity'),
    password:field('password'),background:field('background'),
    realInputs:form.querySelectorAll('input[name="name"],input[name="password"],select[name="capacity"],select[name="background"]').length,
    submitArt:getComputedStyle(form.querySelector('button[type="submit"]')).backgroundImage,
    cancelArt:getComputedStyle(form.querySelector('.social-owner-native-cancel')).backgroundImage
   };
  });
  assert.deepEqual(source.atlas,[338,282],'the real original owner dialog source is 338x282');
  assert.deepEqual(source.art,[309,126],'top-left source panel is independently cropped');
  assert.equal(source.source,'ChatRoom/ownerdialog.png');
  assert.equal(source.frame,'338x282');
  assert.ok(source.visible>20000&&source.keyed>300,'source actual RGBA content and green-key transparency are composed');
  assert.equal(source.panelTitle,'none','HTML generic title must not cover source Room master artwork');
  assert.equal(source.realInputs,4,'all four fields are actual editable HTML controls');
  assert.ok(Math.abs(source.name.x-57)<2&&Math.abs(source.name.y-28)<2,
   'real room name input is aligned to original form field at x57,y28');
  assert.ok(Math.abs(source.password.x-83)<2&&Math.abs(source.password.y-99)<2,
   'live password is registered over source original password field');
  assert.ok(source.submitArt.includes('data:image/png')&&source.cancelArt.includes('data:image/png'),
   'live submit and cancel actions use original atlas pieces, not fabricated buttons');
  assert.equal(transient,2,'test exercised two source HTTP 503 failures');
  assert.ok(attempts>=3,'source bitmap recovers through retries instead of silently reverting to screenshots');
  await page.screenshot({path:'leaf-native-room-owner-dialog.png'});
  await page.locator('form.social-native-owner-form [name="name"]').fill('원본 Room master 검증');
  await page.locator('form.social-native-owner-form [name="capacity"]').selectOption('2');
  await page.locator('form.social-native-owner-form [name="background"]').selectOption('4');
  await page.locator('form.social-native-owner-form [name="visibility"][value="private"]').check();
  const requiresPassword=await page.locator('form.social-native-owner-form [name="password"]').evaluate(el=>el.required);
  assert.equal(requiresPassword,true,'private mode enforces an actual password');
  await page.locator('form.social-native-owner-form button[type="submit"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory',
   'native room creation cannot submit with missing private password');
  await page.locator('form.social-native-owner-form [name="password"]').fill('pass12345');
  await page.locator('form.social-native-owner-form button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room');
  const actual=await page.evaluate(()=>{
   const s=window.__LEAF_SOCIAL__.getState();
   return {count:s.rooms.length,room:s.rooms.find(r=>r.id===s.roomId),frame:getComputedStyle(document.getElementById('social-image-frame')).backgroundImage};
  });
  assert.ok(actual.room?.id&&actual.room.name==='원본 Room master 검증','the genuine form created one real room');
  assert.equal(actual.room.capacity,2,'the native source capacity selector retains real room admission rules');
  assert.equal(actual.room.background,4,'the modern extra background selector changes the real room scene');
  assert.ok(actual.room.passwordProof,'private native owner dialog generated a real password proof');
  assert.ok(actual.frame.includes('original/ChatRoom/room4.png'),'a real native ChatRoom is entered');
  await page.locator('#social-back').click();
  await page.locator('#social-new-room').click();
  await page.waitForFunction(()=>document.querySelector('form.social-native-owner-form')?.dataset.nativeOwnerReady==='true');
  await page.locator('.social-owner-native-cancel').click();
  assert.equal(await page.locator('#social-modal').count(),0,'authentic Cancel closes form without creating any room');
  assert.equal(await page.locator('.social-directory-row').count(),9,'Cancel preserves eight canonical rooms and the single genuinely created room without a ghost');
  await page.setViewportSize({width:390,height:844});
  await page.locator('#social-new-room').click();
  await page.waitForFunction(()=>document.querySelector('form.social-native-owner-form')?.dataset.nativeOwnerReady==='true');
  assert.equal(await page.locator('.social-owner-source-backdrop').count(),1,
   'narrow mobile viewport still has exactly one original dialog component');
  await page.locator('.social-owner-native-cancel').click();
  assert.deepEqual(errors,[],'native source dialog and retries generated no page errors');
  console.log('ORIGINAL ROOM MASTER SOURCE DIALOG PASS',JSON.stringify({source,actualRoom:actual.room.id,attempts}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL OWNER DIALOG FAIL',e.stack||e);process.exit(1)});
