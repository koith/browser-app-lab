'use strict';
/* Persistent UI comparison frame: exact 800x600 source game, no UI mock.
 * A JPEG base64 source audit is included in CI logs ONLY so investigators
 * can compare original 2004 board.jpg against actual Chromium output.
 * This screenshot is NOT displayed as an in-game background.
 */
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,serviceWorkers:'block'});
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+require('node:path').resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOURCE_ROLL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>{
   const tiles=[...document.querySelectorAll('#game #board-nodes .tile')];
   return tiles.length>=40&&tiles.every(x=>x.dataset.tisAlpha==='ready');
  },null,{timeout:45000}).catch(async error=>{
   const states=await page.evaluate(()=>[...document.querySelectorAll(
    '#game #board-nodes .tile')].reduce((acc,t)=>{
    const key=t.dataset.tisAlpha||'missing';acc[key]=(acc[key]||0)+1;return acc;
   },{}));
   console.log('ORIGINAL_TIS_LOADING_DIAGNOSTICS '+JSON.stringify(states));
   throw error;
  });
  await page.waitForTimeout(550);
  const game=page.locator('#app');
  const size=await game.evaluate(el=>{const r=el.getBoundingClientRect();return {w:r.width,h:r.height}});
  if(Math.abs(size.w-800)>3||Math.abs(size.h-600)>3)throw Error('original fixed UI 800x600 missing');
  const audit=await page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes .tile')];
   const source=document.querySelector('#board-world');
   const r=source.getBoundingClientRect();
   return {
    tileCount:tiles.length,
    visibleTileCount:tiles.filter(el=>el.style.visibility!=='hidden').length,
    projection:window.__LEAF_CAMERA__?.getState?.().projectedPitch,
    cameraWorld:window.__LEAF_CAMERA__?.getState?.().size,
    nativeTileSize:tiles.slice(0,5).map(el=>[el.offsetWidth,el.offsetHeight]),
    worldBox:[r.x,r.y,r.width,r.height],
    orientation:getComputedStyle(tiles[0]).transform,
    alphaReady:tiles.filter(x=>x.dataset.tisAlpha==='ready').length,
    clipping:tiles[0].style.clipPath,
    tiles:tiles.slice(0,9).map(x=>({
      tile:x.dataset.tile,id:x.dataset.originalArt,x:x.dataset.dmpX,y:x.dataset.dmpY,
      left:x.style.left,top:x.style.top,
      z:Number(x.style.zIndex),image:getComputedStyle(x).backgroundImage.slice(-45)
    }))
   };
  });
  // REAL 2004 photo A/B shows the extracted TIS PNG lettering upside down.
  // Native decode_tis.py flips bottom-up rows during export. The ACTUAL
  // in-browser image must be vertically inverted again to show upright art.
  const nativeOrientation=await page.evaluate(()=>{
   const first=document.querySelector('#board-nodes>.tile');
   const matrix=new DOMMatrixReadOnly(getComputedStyle(first).transform);
   return {matrix:[matrix.a,matrix.b,matrix.c,matrix.d,matrix.e,matrix.f],
    det:matrix.a*matrix.d-matrix.b*matrix.c,
    size:[first.offsetWidth,first.offsetHeight],
    source:first.dataset.originalArt};
  });
  if(nativeOrientation.det>=0||nativeOrientation.size[0]!==145||
    nativeOrientation.size[1]!==97)
   throw Error('Upside-down source TIS or wrongly scaled source tile: '+
     JSON.stringify(nativeOrientation));
  console.log('SOURCE_TIS_UPRIGHT_ORIENTATION '+JSON.stringify(nativeOrientation));
  // Current source-photo 128x86 projection exposes ~12 legible raised
  // hexes in the real 800x600 window; the older 111x75 packed ~20 layers
  // and hid native top faces. Reject empty or again overpacked scenes.
  if(audit.visibleTileCount<8 || audit.visibleTileCount>24)
   throw Error('2004 native screenshot camera has wrong card density: '+
    JSON.stringify({visible:audit.visibleTileCount,pitch:audit.projection}));
  if(audit.nativeTileSize.some(([w,h])=>w!==145||h!==97))
   throw Error('Do not distort original 145x97 TIS artwork');
  if(!audit.orientation.includes('0, -1,'))
   throw Error('Native TIS rendering did not correct upside-down extractor bitmap');
  const img=await game.screenshot({type:'jpeg',quality:70,animations:'disabled',timeout:18000});
  console.log('SOURCE_SCREENSHOT_QA '+JSON.stringify(audit));
  console.log('SOURCE_SCREENSHOT_JPEG_BASE64 '+img.toString('base64'));
  console.log('SOURCE_SCREENSHOT_END');
  // Keep an independent nonproduction A/B: restore PREVIOUS erroneous
  // unflipped TIS art, capture it, then return to approved original source
  // orientation. The current 2004 screenshot comparison confirmed Y-inversion.
  const originalPhotoOrientation=await page.evaluate(()=>{
   const style=document.createElement('style');
   style.id='leaf-tis-source-orientation-ab';
   style.textContent='#app.app-classic-dice #game .board-world #board-nodes .tile[data-native-tis-size="145x97"]{transform:translate(-50%,-50%)!important}';
   document.head.append(style);
   return getComputedStyle(document.querySelector('#board-nodes>.tile')).transform;
  });
  if(!originalPhotoOrientation.startsWith('matrix(1, 0, 0, 1,'))
   throw Error('Source orientation A/B CSS did not override legacy orientation: '+originalPhotoOrientation);
  const inversePhoto=await game.screenshot({
   type:'jpeg',quality:77,animations:'disabled',timeout:18000});
  console.log('SOURCE_TIS_OLD_INVERTED_AB_GEOMETRY '+originalPhotoOrientation);
  console.log('SOURCE_TIS_OLD_INVERTED_AB_JPEG_BASE64 '+inversePhoto.toString('base64'));
  console.log('SOURCE_TIS_OLD_INVERTED_AB_END');
  await page.evaluate(()=>document.querySelector('#leaf-tis-source-orientation-ab')?.remove());

  // An independent LIVE source bitmap capture: two OBS.pak original Genesis
  // full-body characters stand on the actual DMP START cell. Card IDs are
  // test-only changes, never a static compositor or permanent game data.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0045';
   m.players[1].team[0]='c_0042';
   m.players[0].position=0;
   m.players[1].position=0;
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#board-pawns .leaf-chess-original-obs')]
   .length===2&&[...document.querySelectorAll(
   '#board-pawns .leaf-chess-original-obs')].every(i=>i.complete&&i.naturalWidth>20),
   null,{timeout:15000});
  const sourceActors=await page.evaluate(()=>[...document.querySelectorAll(
   '#board-pawns .board-pawn')].map(node=>{
   const img=node.querySelector('img.leaf-chess-original-obs');
   const tile=document.querySelector('#board-nodes .tile[data-tile="0"]');
   const actor=img.getBoundingClientRect(),floor=tile.getBoundingClientRect();
   return {id:node.dataset.chessmanId,rig:node.dataset.actorRig,
    source:img.getAttribute('src'),
    frame:Number(node.dataset.actorFrame),pose:node.dataset.actorPose,
    native:[img.naturalWidth,img.naturalHeight],
    flip:getComputedStyle(img).transform,
    grounding:node.dataset.sourceGrounding,
    nativePivot:[img.style.getPropertyValue('--leaf-obs-left').trim(),
     img.style.getPropertyValue('--leaf-obs-bottom').trim()],
    computedLeft:getComputedStyle(img).left,
    computedBottom:getComputedStyle(img).bottom,
    rendered:[actor.x,actor.y,actor.width,actor.height],
    floor:[floor.x,floor.y,floor.width,floor.height],
    distanceFeetFromFloor:Math.round(actor.bottom-(floor.y+floor.height/2)),
    sameTilePeers:Number(node.dataset.cellPeerCount)};
  }));
  if(sourceActors.some(a=>{
   // This assertion runs in Node, not the browser page; parse CSS matrix
   // numeric values without relying on a browser-only DOMMatrix global.
   const isMatrix=String(a.flip).startsWith('matrix(');
   const values=String(a.flip).replace('matrix(','').replace(')','').split(',').map(Number);
   return !isMatrix||values.length!==6||!values.every(Number.isFinite)||
    values[0]*values[3]-values[1]*values[2]>=0;
  }))throw Error('Original OBS indexed source is drawn upside down: '+
   JSON.stringify(sourceActors));
  if(sourceActors.length!==2||
   sourceActors.some(a=>a.rig!=='original-obs-sprite'||!a.source.includes('/OBS/')))
    throw Error('Recovered source character renders as proxy or incorrect asset');
  if(sourceActors.some(a=>
    a.nativePivot.some(x=>!/^calc\(/.test(x)||/\+\s*-|\-\s*-/.test(x))||
    a.computedLeft==='auto'||a.computedBottom==='auto'||
    !/px$/.test(a.computedLeft)||!/px$/.test(a.computedBottom)))
   throw Error('Native OBS pivot CSS expression failed for signed original offsets: '+
    JSON.stringify(sourceActors));
  const feetDifference=Math.abs(sourceActors[0].distanceFeetFromFloor-
   sourceActors[1].distanceFeetFromFloor);
  if(feetDifference>2)
   throw Error('Original source characters on same DMP tile must share a ground plane: '+
    JSON.stringify(sourceActors));
  console.log('SOURCE_NATIVE_OBS_BOARD_QA '+JSON.stringify({
   sourceActors,feetDifference}));
  const originalBodies=await game.screenshot({type:'jpeg',quality:82,
   animations:'disabled',timeout:18000});
  console.log('SOURCE_NATIVE_OBS_JPEG_BASE64 '+originalBodies.toString('base64'));
  console.log('SOURCE_NATIVE_OBS_END');
  // Compare actual LIVE duel to historical 800x600 original board.jpg /
  // battle.jpg. The combat engine produces the dice, values and Genesis
  // chessman IDs; this does not insert fixed screenshots or mock results.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForSelector('#battle-visual');
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#battle-visual .battle-visual-actor .leaf-chess-original-obs')]
   .length===2,null,{timeout:15000});
  const sourceBattle=await page.evaluate(()=>{
   const stage=document.querySelector('#battle-visual');
   return {
    nativeModels:[...stage.querySelectorAll('.battle-visual-actor')].map(x=>({
      id:x.dataset.chessmanId,rig:x.dataset.actorRig,source:x.dataset.actorSource
    })),
    score:[...stage.querySelectorAll('.battle-visual-total')].map(x=>x.textContent),
    dice:[...stage.querySelectorAll('.battle-visual-die')].map(x=>x.dataset.eye),
    banner:stage.querySelector('.battle-visual-head')?.textContent,
    podiums:stage.querySelectorAll('.battle-visual-pedestal').length
   };
  });
  if(sourceBattle.nativeModels.some(x=>x.rig!=='original-obs-sprite')||
   sourceBattle.banner!=='BATTLE'||sourceBattle.podiums!==2)
   throw Error('Original battle layout must show real selected Genesis actors and source-like dual podiums: '+
     JSON.stringify(sourceBattle));
  console.log('SOURCE_LIVE_DUEL_QA '+JSON.stringify(sourceBattle));
  const battleCapture=await game.screenshot({
    type:'jpeg',quality:78,animations:'disabled',timeout:18000});
  console.log('SOURCE_LIVE_DUEL_JPEG_BASE64 '+battleCapture.toString('base64'));
  console.log('SOURCE_LIVE_DUEL_END');
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE SCREENSHOT QA ERROR',e.stack||e);process.exit(1)});
