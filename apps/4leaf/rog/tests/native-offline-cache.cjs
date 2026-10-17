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
  // The public entry point must register its own worker. Offline QA must
  // not conceal a missing production registration with an explicit test call.
  await page.waitForFunction(()=>window.__LEAF_PWA__?.getState().registered===true,
   null,{timeout:30000});
  await page.evaluate(()=>navigator.serviceWorker.ready);
  const critical=[
   'chatroom-native-owner-dialog.js','chatroom-native-owner-dialog.css','original/ChatRoom/ownerdialog.png',
   'registry-native-avatar-dialog.js','registry-native-avatar-dialog.css',
   ...['avatardialog1','avatardialog2','avatardialog3'].map(x=>'original/Registry/'+x+'.png'),
   'chatroom-native-expressions.js','chatroom-native-expressions.css','original/ChatRoom/expdialogbtn.png',
   'dice-native-dialog-event.css','original/IMG/dialog.png','original/IMG/eventmsgbox.png',
   'dice-source-dmp-terrain-explorer.js','dice-source-dmp-terrain-explorer.css','dice-native-battle-dice.css','dice-source-roll.css','dice-source-roll.js','dice-native-minimap-navigation.css','dice-native-tis-depth.css','dice-native-tis-orientation.css','dice-ai-autoplay.css','dice-native-pawn-dmp-depth.css','dice-native-tis-alpha.js',...['0000','0015','0024','0046'].map(x=>'original/Tiles/'+x+'.png'),
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
   const cache=await caches.open('4leaf-revival-pwa-v60');
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
  // including its genuine four-state sprite and the 323x124 tiled panel.
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
  assert.deepEqual(offlineChrome.panel,[323,124],'PWA has original MainFrame tiled menu background');
  assert.ok(offlineChrome.menuBackground.includes('/original/MainFrame/pannel.png'));
  assert.ok(offlineChrome.iconBackground.includes('/original/MainFrame/toolbarbtn.png'));
  assert.equal(offlineChrome.sourceButton,30,'PWA menu retains clickable source 30px atlas cells');
  // The original TIS source bitmap chroma-mask renderer is pre-cached too.
  // A user should be able to start a NEW match while entirely offline.
  assert.deepEqual(await page.evaluate(()=>window.__LEAF_TIS_ALPHA__?.getState().native),
   [145,97],'source TIS alpha compositor works on first cold offline load');

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
  // Three independent archived Registry panel assets must be decoded
  // on FIRST cold offline opening with no pre-visit of avatar selection.
  await page.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  await page.waitForFunction(()=>{
   const assets=[...document.querySelectorAll(
    '#social-modal .social-native-avatar-header img,#social-modal .social-native-avatar-source')];
   return assets.length===3&&assets.every(i=>i.dataset.sourceReady==='true');
  },null,{timeout:12000});
  const avatarPanel=await page.locator('#social-modal .social-native-avatar-panel').evaluate(el=>({
   source:el.dataset.nativeAvatarDialog,
   parts:[...el.querySelectorAll('.social-native-avatar-header img,.social-native-avatar-source')]
    .map(i=>[i.naturalWidth,i.naturalHeight]),
   count:el.querySelectorAll('.social-native-avatar-chooser button').length
  }));
  assert.equal(avatarPanel.source,'Registry/avatardialog3.png');
  assert.deepEqual(avatarPanel.parts,[[111,34],[168,23],[368,205]],
   'cold offline original Registry dialog images decoded at natural source pixels');
  assert.equal(avatarPanel.count,12,'all twelve actual Registry actors remain independently selectable offline');
  await page.locator('.social-native-avatar-chooser button[data-avatar-index="7"]').click();
  await page.locator('.social-native-avatar-confirm').click();
  assert.ok((await page.locator('.social-avatar.self img').getAttribute('src')).includes('sava04.png'),
   'cold offline source dialog updates same real room occupant, not a fake actor');

  await page.waitForFunction(()=>window.__LEAF_NATIVE_EXPRESSIONS__?.getState().ready,null,{timeout:8000});
  await page.locator('.social-exp-trigger').click();
  await page.locator('.social-native-expression-option[data-expression="좋아"]').click();
  assert.equal(await page.locator('.social-avatar.self .social-native-expression').getAttribute('data-native-expression'),'좋아',
   'fully offline original face sprite and genuine local chat event work on first opening');

  // Cold offline Genesis game MUST paint unscaled original 145x97 TIS
  // before a visitor has ever opened Dice gameplay online. The previous
  // client silently fell back to empty tile sprites without cached assets.
  await page.evaluate(()=>window.__ROG_TEST__.go('lobby'));
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelector('#board-nodes .tile')?.dataset.tisAlpha==='ready',
   null,{timeout:15000});
  const offlineTiles=await page.evaluate(async()=>{
   const node=document.querySelector('#board-nodes .tile[data-native-tis-size="145x97"]');
   const target=node?.dataset.originalArt;
   const image=new Image();image.src='./original/Tiles/'+target+'.png';await image.decode();
   const sampleCanvas=document.createElement('canvas');
   sampleCanvas.width=image.width;sampleCanvas.height=image.height;
   const sampleCtx=sampleCanvas.getContext('2d',{willReadFrequently:true});
   sampleCtx.drawImage(image,0,0);
   const originalCornerAlpha=sampleCtx.getImageData(0,0,1,1).data[3];
   return {
    count:document.querySelectorAll('#board-nodes .tile').length,
    original:[image.naturalWidth,image.naturalHeight],
    originalCornerAlpha,
    layout:[node.offsetWidth,node.offsetHeight],
    paint:getComputedStyle(node).backgroundImage,
    source:target,
    keyedSource:node.dataset.tisAlphaSource,
    decoded:node.dataset.tisAlpha,
    removed:Number(node.dataset.tisChromaRemoved)
   };
  });
  assert.equal(offlineTiles.count,104,'all original offline 4LEAF MVE path cells are live');
  assert.deepEqual(offlineTiles.original,[145,97],'offline native TIS asset decoded at full source shape');
  assert.deepEqual(offlineTiles.layout,[145,97],'offline live board no longer shrinks true original TIS artwork');
  assert.equal(offlineTiles.keyedSource,'Tiles/'+offlineTiles.source+'.png',
   'cold offline rendered bitmap retains exact recovered TIS provenance');
  assert.equal(offlineTiles.decoded,'ready','cold offline boot actually decoded the source, not just requested it');
  assert.ok(offlineTiles.paint.includes('/original/Tiles/'+offlineTiles.source+'.png')||
   offlineTiles.paint.includes('data:image/png'),
   'source-native offline board uses source bytes or genuinely required chroma-key processing');
  // Some original source PNGs (e.g. tile 0024) already have transparent
  // corners; those correctly require ZERO additional pixels removed.
  assert.ok(offlineTiles.removed>=0&&
   (offlineTiles.originalCornerAlpha<16||offlineTiles.removed>0),
   'preserve originally transparent pixels; only opaque outside mattes are keyed: '+
   JSON.stringify({source:offlineTiles.source,corner:offlineTiles.originalCornerAlpha,removed:offlineTiles.removed}));
  // First offline Genesis match also has the SAME navigable source canvas,
  // not a disconnected cosmetic map. Clicking it changes only camera view.
  await page.waitForFunction(()=>window.__LEAF_MINIMAP_NAV__?.getState().camera?.visible?.width>0);
  const beforeOfflineMini=await page.evaluate(()=>({
   transform:document.querySelector('#board-world').style.transform,
   players:window.__ROG_TEST__.getMatch().players.map(p=>p.position)
  }));
  const offlineMiniCanvas=page.locator('#mini-map-canvas');
  const offlineMiniBounds=await offlineMiniCanvas.boundingBox();
  await offlineMiniCanvas.click({position:{
   x:offlineMiniBounds.width*.88,y:offlineMiniBounds.height*.82
  }});
  const afterOfflineMini=await page.evaluate(()=>({
   transform:document.querySelector('#board-world').style.transform,
   players:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   source:window.__LEAF_MINIMAP_NAV__.getState().source
  }));
  assert.equal(afterOfflineMini.source,'IMG/minimap.png');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile[data-dmp-focusable]').length>30,null,{timeout:12000});
  const offlineDmp=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   const history=m.history.slice(),positions=m.players.map(p=>p.position);
   const navigated=window.__LEAF_DMP_EXPLORER__.focus(18);
   return {tile:navigated?.index,coord:navigated?.coord,art:navigated?.sourceArt,
    historyUnchanged:JSON.stringify(history)===JSON.stringify(m.history),
    positionsUnchanged:JSON.stringify(positions)===JSON.stringify(m.players.map(p=>p.position)),
    panel:document.querySelector('#dice-source-dmp-inspector')?.hidden===false};
  });
  assert.equal(offlineDmp.tile,18,'even offline the recovered DMP cell can be inspected');
  assert.ok(offlineDmp.art&&offlineDmp.coord&&offlineDmp.panel,'cold offline inspector uses actual original map art');
  assert.ok(offlineDmp.historyUnchanged&&offlineDmp.positionsUnchanged,
   'offline exploration must not fabricate gameplay or move any real player');
  assert.notEqual(afterOfflineMini.transform,beforeOfflineMini.transform,
   'original live minimap pans the real DMP game even entirely offline');
  assert.deepEqual(afterOfflineMini.players,beforeOfflineMini.players,
   'camera-only offline minimap interaction must not fake character movement');
  assert.deepEqual(errors,[],'no unexpected JavaScript errors during offline play');
  console.log('4LEAF NATIVE OFFLINE CACHE PASS',JSON.stringify({cached:critical.length,original}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE OFFLINE CACHE FAILED',e.stack||e);process.exit(1)});
