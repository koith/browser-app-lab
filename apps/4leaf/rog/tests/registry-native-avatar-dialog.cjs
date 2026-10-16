'use strict';
// Source Registry/avatardialog1.png, avatardialog2.png, avatardialog3.png
// are genuine 4LEAF-era components; 75x141 actor is another independent
// pixel source. No fabricated level, GP or job in the original info panel.
// Real Chromium checks two browsers, true peer identity and actual selection.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const host=await context.newPage(),guest=await context.newPage();
 const errors=[];
 for(const page of [host,guest]){
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 }
 try{
  const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await host.goto(url);
  await guest.goto(url);
  await Promise.all([host,guest].map(page=>page.waitForFunction(()=>
   Boolean(window.__LEAF_SOCIAL__&&window.__ROG_TEST__&&window.__LEAF_NATIVE_AVATAR_DIALOG__))));
  const room=await host.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   return window.__LEAF_SOCIAL__.createRoom('원본 아바타 설정 및 동기화',4,12);
  });
  await guest.evaluate(roomId=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.joinRoom(roomId);
  },room);
  await Promise.all([host,guest].map(page=>page.waitForFunction(()=>
   document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,
   null,{timeout:20000})));
  const initial=await host.locator('.social-avatar.self img').getAttribute('src');
  await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  await host.waitForFunction(()=>
   document.querySelector('.social-native-avatar-panel .social-native-avatar-source')
    ?.dataset.sourceReady==='true',null,{timeout:16000});
  const source=await host.locator('#social-modal .social-native-avatar-panel').evaluate(async panel=>{
   const assets=async file=>{
    const img=new Image();img.src='./original/Registry/'+file;
    await img.decode();return [img.naturalWidth,img.naturalHeight];
   };
   const header=panel.querySelector('.social-native-avatar-header');
   const scene=panel.querySelector('.social-native-avatar-scene');
   const preview=panel.querySelector('.social-native-avatar-preview');
   const source=panel.querySelector('.social-native-avatar-source');
   return {
    source:panel.dataset.nativeAvatarDialog,
    sourceSet:panel.dataset.nativeAvatarSource,
    assets:{
     logo:await assets('avatardialog1.png'),
     title:await assets('avatardialog2.png'),
     info:await assets('avatardialog3.png'),
     actor:await assets('sava00.png')
    },
    headerImages:[...header.querySelectorAll('img')].map(i=>i.dataset.source),
    infoImage:source.dataset.source,
    frameStyle:getComputedStyle(scene).backgroundImage,
    infoBounds:[scene.getBoundingClientRect().width,scene.getBoundingClientRect().height],
    name:panel.querySelector('.social-native-avatar-name').textContent,
    actualAvatar:preview.getAttribute('src'),
    displayedActor:[preview.getBoundingClientRect().width,preview.getBoundingClientRect().height],
    actors:[...panel.querySelectorAll('.social-native-avatar-chooser button')].map(b=>({
     source:b.querySelector('img')?.getAttribute('src'),type:b.tagName,pressed:b.getAttribute('aria-pressed')
    })),
    genericTitle:getComputedStyle(panel.querySelector('.social-modal-title b')).display,
    closeVisible:getComputedStyle(panel.querySelector('.social-modal-title button')).display,
    feedback:panel.querySelector('.social-native-avatar-selection').textContent,
    text:panel.textContent
   };
  });
  assert.deepEqual(source.assets,{
   logo:[111,31],title:[180,29],info:[368,207],actor:[75,141]
  },'all three recovered original UI components plus genuine 75×141 actor decode at source size');
  assert.equal(source.source,'Registry/avatardialog3.png');
  assert.deepEqual(source.headerImages,['Registry/avatardialog1.png','Registry/avatardialog2.png']);
  assert.equal(source.infoImage,'Registry/avatardialog3.png');
  assert.ok(Math.abs(source.infoBounds[0]-368)<2&&Math.abs(source.infoBounds[1]-207)<2,
   'original UI info art stays at 1:1 logical source pixels on desktop');
  assert.ok(Math.abs(source.displayedActor[0]-75)<1&&Math.abs(source.displayedActor[1]-141)<1,
   'native original character preview is distinct, 1:1 and never screenshot pasted');
  assert.equal(source.actors.length,12,'show exactly twelve true saved Registry actors');
  assert.ok(source.actors.every(x=>x.source.startsWith('./original/Registry/sava')&&x.type==='BUTTON'),
   'all candidates are independent live buttons with recovered source sprites');
  assert.equal(source.genericTitle,'none','generic invented dialogue title does not cover true source header');
  assert.equal(source.closeVisible,'block','real legacy close control stays usable');
  assert.equal(source.actors.filter(x=>x.pressed==='true').length,1,
   'one genuine selected character rather than fabricated users');
  assert.ok(!source.text.includes('Lv 99')&&!source.text.includes('999999 GP'),
   'do not fabricate unsupported character progression / wealth');
  await host.screenshot({path:'leaf-original-registry-avatar-select.png'});
  const candidate=host.locator('.social-native-avatar-chooser button[data-avatar-index="7"]');
  await candidate.click();
  assert.equal(await host.locator('.social-native-avatar-preview').getAttribute('data-original-avatar'),'sava04');
  assert.equal(await host.locator('.social-native-avatar-chooser button.selected').count(),1);
  assert.equal(await host.locator('.social-avatar.self img').getAttribute('src'),initial,
   'preview selection alone must not overwrite current saved actor or peer presence');
  await host.locator('.social-native-avatar-confirm').click();
  await host.waitForFunction(()=>document.querySelector('.social-avatar.self img')?.getAttribute('src')
   ?.includes('sava04.png'),null,{timeout:8000});
  assert.equal(await host.locator('#social-modal').count(),0,'confirm closes native dialog');
  await guest.waitForFunction(()=>document.querySelector('.social-avatar:not(.self) img')?.getAttribute('src')
   ?.includes('sava04.png'),null,{timeout:15000});
  const realPeers=await guest.locator('.social-avatar').count();
  assert.equal(realPeers,2,'avatar changes do not spawn fake participants');
  assert.equal(await host.evaluate(()=>localStorage.getItem('leaf_social_avatar')),'7',
   'actual selected avatar index persisted, not a fake stand-in');

  await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  await host.locator('.social-native-avatar-chooser button[data-avatar-index="1"]').click();
  await host.locator('.social-native-avatar-cancel').click();
  assert.ok((await host.locator('.social-avatar.self img').getAttribute('src')).includes('sava04.png'),
   'cancel does not silently change the actual live character');

  await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  await host.locator('.social-native-avatar-chooser button[data-avatar-index="7"]').focus();
  await host.keyboard.press('ArrowRight');
  assert.equal(await host.locator('.social-native-avatar-panel').getAttribute('data-selected-avatar'),
   'sava03','native left/right key control selects a distinct archived actor');
  await host.keyboard.press('Escape');
  assert.equal(await host.locator('#social-modal').count(),0,'Escape closes native dialog without creating an actor');

  await host.setViewportSize({width:390,height:844});
  await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  const mobile=await host.locator('.social-native-avatar-panel').evaluate(panel=>{
   const rect=panel.getBoundingClientRect(),scene=panel.querySelector('.social-native-avatar-scene').getBoundingClientRect();
   const buttons=[...panel.querySelectorAll('.social-native-avatar-chooser button')];
   return {panel:[rect.x,rect.y,rect.width,rect.height],scene:[scene.width,scene.height],
    buttons:buttons.map(b=>b.getBoundingClientRect().width),
    cols:getComputedStyle(panel.querySelector('.social-native-avatar-chooser')).gridTemplateColumns,
    current:panel.dataset.selectedAvatar};
  });
  assert.ok(mobile.panel[0]>=-1&&mobile.panel[0]+mobile.panel[2]<=391,
   'full source dialogue stays inside narrow phone viewport');
  assert.ok(mobile.scene[0]<=368,'source panel uniformly fits mobile without horizontal crop');
  assert.ok(mobile.buttons.every(x=>x>30),'native actor selection remains touch-accessible at phone width');
  await host.locator('.social-native-avatar-chooser button[data-avatar-index="11"]').click();
  await host.locator('.social-native-avatar-confirm').click();
  await guest.waitForFunction(()=>document.querySelector('.social-avatar:not(.self) img')
   ?.getAttribute('src')?.includes('sava86.png'),null,{timeout:16000});
  assert.equal(await guest.locator('.social-avatar').count(),2,
   'mobile source dialog updates same two genuine players, no fake occupancy');
  await host.screenshot({path:'leaf-original-registry-avatar-mobile.png'});
  assert.deepEqual(errors,[],'all original Registry UI and live two-browser peer selection is exception-free');
  console.log('REGISTRY NATIVE AVATAR DIALOG PASS',JSON.stringify({assets:source.assets,
   selected:'sava86',previous:'sava04',realPeers,mobile}));
 }finally{await browser.close()}
})().catch(error=>{console.error('REGISTRY NATIVE AVATAR DIALOG FAILED:',error.stack||error);process.exit(1)});
