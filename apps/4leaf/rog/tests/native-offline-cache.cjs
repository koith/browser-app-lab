'use strict';
// Genuine WorldMap/ChatTown/ChatRoom assets must work after cold PWA install,
// not only if a user happened to browse each image once while online.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:800},serviceWorkers:'allow'});
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.evaluate(async()=>{
   await navigator.serviceWorker.register('./sw.js');
   await navigator.serviceWorker.ready;
  });
  const critical=[
   'chatroom-native-owner-dialog.js','chatroom-native-owner-dialog.css','original/ChatRoom/ownerdialog.png',
   'chatroom-native-expressions.js','chatroom-native-expressions.css','original/ChatRoom/expdialogbtn.png',
   'dice-native-dialog-event.css','original/IMG/dialog.png','original/IMG/eventmsgbox.png',
   'mainframe-native-toolbar.css','original/MainFrame/toolbarbtn.png','original/MainFrame/pannel.png',
   'knighttown-native.js','knighttown-native.css',
   ...['knightback','plain01','plain02','sea01','sea02','sea03','snow01'].map(s=>'original/KnightTown/'+s+'.png'),
   'world-social.css','social-chat.js','world-map.js','mainframe-native-snapshot.js','mainframe-native-snapshot.css','original/MainFrame/snaplogo.png','original/MainFrame/snapnumber.png',
   ...['mainstreet','knights','northchatrgn','southchatrgn','dice','m4leaf'].map(s=>'original/WorldMap/'+s+'.png'),
   ...['northback','southback','plainbtn','seabtn','snowbtn'].map(s=>'original/ChatTown/'+s+'.png'),
   ...Array.from({length:6},(_,n)=>'original/ChatRoom/room'+n+'.png'),
   ...[3,4,5].map(n=>'original/ChatRoom/room'+n+'t.png'),
   'original/Registry/sava00.png'
  ];
  await page.waitForFunction(async files=>{
   const cache=await caches.open('4leaf-revival-pwa-v46');
   return (await Promise.all(files.map(file=>cache.match('./'+file)))).every(Boolean);
  },critical,{timeout:40000});
  // An established controller must answer image and JS fetches offline.
  await page.reload();
  await page.waitForFunction(()=>!!navigator.serviceWorker.controller,null,{timeout:12000});
  await context.setOffline(true);
  await page.reload({waitUntil:'domcontentloaded',timeout:15000});
  await page.waitForFunction(()=>document.querySelector('#leaf-world-stage .world-backdrop')?.dataset.ready==='true'
   &&document.querySelectorAll('#leaf-world-stage .world-sprite[data-ready="true"]').length===6
   &&document.querySelector('#leaf-world-stage .leaf-native-snaplogo')?.dataset.ready==='true'
   &&document.querySelector('#leaf-world-stage .leaf-native-snapnumber')?.dataset.ready==='true',
   null,{timeout:18000});
  // Cold PWA installation must draw the true 120x270 MainFrame toolbar,
  // including its genuine four-state sprite and the 323x240 tiled panel.
  // This remains working even before the player ever navigates menus online.
  const offlineChrome=await page.evaluate(async()=>{
   const native=async name=>{
    const img=new Image();img.src='./original/MainFrame/'+name+'.png';
    await img.decode();return [img.naturalWidth,img.naturalHeight];
   };
   const nav=document.querySelector('#app>nav.toolbar');
   const first=nav.querySelector('[data-route="sky"]');
   return {
    atlas:await native('toolbarbtn'),panel:await native('pannel'),
    menuBackground:getComputedStyle(nav).backgroundImage,
    iconBackground:getComputedStyle(first).backgroundImage,
    sourceButton:parseInt(getComputedStyle(first).width,10)
   };
  });
  assert.deepEqual(offlineChrome.atlas,[120,270],'PWA has original MainFrame toolbar atlas without any prior menu visit');
  assert.deepEqual(offlineChrome.panel,[323,240],'PWA has original MainFrame tiled menu background');
  assert.ok(offlineChrome.menuBackground.includes('/original/MainFrame/pannel.png'));
  assert.ok(offlineChrome.iconBackground.includes('/original/MainFrame/toolbarbtn.png'));
  assert.equal(offlineChrome.sourceButton,30,'PWA menu retains clickable source 30px atlas cells');
  // Cold-offline source KnightTown region art and all its six sign frames
  // must work before a visitor ever browsed the Recordable in this session.
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openKnightTown();window.__ROG_TEST__.go('rooms')});
  await page.waitForFunction(()=>document.querySelectorAll('.knight-district-hotspot').length===6,null,{timeout:8000});
  const originalKnight=await page.evaluate(async()=>{
   const img=new Image();img.src='./original/KnightTown/knightback.png';
   await img.decode();
   return [img.naturalWidth,img.naturalHeight];
  });
  assert.deepEqual(originalKnight,[794,404],'native Recordable area backdrop is available on first offline entry');
  await page.locator('[data-knight-area="snow01"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().knightDistrict),'침묵의 설원',
   'original KnightTown areas work without the network');
  await page.locator('#social-back').click();
  await page.locator('#social-back').click();
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms');});
  await page.waitForFunction(()=>document.querySelectorAll('.social-district-hotspot').length===8,null,{timeout:8000});
  await page.locator('.social-district-hotspot').nth(3).click();
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('오프라인 원본 리소스 확인',4));
  await page.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true'
   &&document.querySelector('#rooms .social-interior > .leaf-native-snaplogo')?.dataset.ready==='true'
   &&document.querySelector('#rooms .social-interior > .leaf-native-snapnumber')?.dataset.ready==='true',
   null,{timeout:8000});
  const original=await page.locator('.social-room-foreground').evaluate(el=>({
   source:el.dataset.source,native:[el.width,el.height],
   position:[parseFloat(el.style.left),parseFloat(el.style.top)]
  }));
  // Source-native Room master must remain available without internet, even
  // if the visitor had never opened the original modal before going offline.
  const offlineRoomId=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
  await page.locator('#social-back').click();
  await page.locator('#social-new-room').click();
  await page.waitForFunction(()=>document.querySelector('form.social-native-owner-form')?.dataset.nativeOwnerReady==='true',null,{timeout:8000});
  const ownerArt=await page.locator('form.social-native-owner-form').evaluate(el=>({
   sprite:el.dataset.nativeOwnerSource,
   panel:[el.querySelector('canvas').width,el.querySelector('canvas').height]
  }));
  assert.equal(ownerArt.sprite,'ChatRoom/ownerdialog.png','original room-master works on first cold offline open');
  assert.deepEqual(ownerArt.panel,[309,126],'cold offline genuine room-owner panel shape preserved');
  await page.locator('.social-owner-native-cancel').click();
  // Return to the same already-created genuine room: testing the room-owner
  // popup should not silently vacate the subject of the original offline QA.
  await page.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),offlineRoomId);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().view==='room'
   &&document.querySelectorAll('.social-avatar.self').length===1,null,{timeout:8000});
  assert.equal(original.source,'room4t');
  assert.deepEqual(original.native,[115,103]);
  assert.deepEqual(original.position,[427,425]);
  assert.equal(await page.locator('.social-avatar.self').count(),1,'only genuine offline self occupant');
  await page.waitForFunction(()=>window.__LEAF_NATIVE_EXPRESSIONS__?.getState().ready,null,{timeout:8000});
  await page.locator('.social-exp-trigger').click();
  await page.locator('.social-native-expression-option[data-expression="좋아"]').click();
  assert.equal(await page.locator('.social-avatar.self .social-native-expression').getAttribute('data-native-expression'),'좋아',
   'fully offline original face sprite and genuine local chat event work on first opening');

  assert.deepEqual(errors,[],'no unexpected JavaScript errors during offline play');
  console.log('4LEAF NATIVE OFFLINE CACHE PASS',JSON.stringify({cached:critical.length,original}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE OFFLINE CACHE FAILED',e.stack||e);process.exit(1)});
