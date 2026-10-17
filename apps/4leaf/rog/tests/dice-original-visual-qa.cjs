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
  await page.waitForFunction(()=>[...document.querySelectorAll('#game #board-nodes .tile')].every(x=>x.dataset.tisAlpha==='ready'),null,{timeout:20000});
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
  const img=await game.screenshot({type:'jpeg',quality:70,animations:'disabled',timeout:18000});
  console.log('SOURCE_SCREENSHOT_QA '+JSON.stringify(audit));
  console.log('SOURCE_SCREENSHOT_JPEG_BASE64 '+img.toString('base64'));
  console.log('SOURCE_SCREENSHOT_END');
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
    rendered:[actor.x,actor.y,actor.width,actor.height],
    floor:[floor.x,floor.y,floor.width,floor.height],
    distanceFeetFromFloor:Math.round(actor.bottom-(floor.y+floor.height/2)),
    sameTilePeers:Number(node.dataset.cellPeerCount)};
  }));
  if(sourceActors.length!==2||
   sourceActors.some(a=>a.rig!=='original-obs-sprite'||!a.source.includes('/OBS/')))
    throw Error('Recovered source character renders as proxy or incorrect asset');
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
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE SCREENSHOT QA ERROR',e.stack||e);process.exit(1)});
