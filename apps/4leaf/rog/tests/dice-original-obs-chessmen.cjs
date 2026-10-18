'use strict';
/* True 2002-era Genesis chessman source frames on real playable DMP board.
 * This does NOT certify recovered pose labels; only pixels, origins,
 * card-ID mapping and current interactive turn engine are verified.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
   window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const players=window.__ROG_TEST__.getMatch().players;
   players[0].team[0]='c_0045';
   players[1].team[0]='c_0042';
   window.__ROG_TEST__.drawGame();
  });
  const sources=await page.evaluate(()=>({
   actors:window.__LEAF_GENESIS_ACTORS__.getState().rendered,
   cache:window.ORIGINAL_LEAF_OBS_FRAMES,
   visible:[...document.querySelectorAll('#board-pawns .board-pawn')].map(n=>({
    card:n.dataset.chessmanId,actor:n.dataset.actorRig,
    source:n.dataset.actorSource,
    poseMapping:n.dataset.sourcePoseMapping,
    src:n.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
    hidden:getComputedStyle(n.querySelector('.leaf-chess-actor')).display,
    img:n.querySelector('.leaf-chess-original-obs')?.getBoundingClientRect().toJSON()
   })),
   tiles:document.querySelectorAll('#board-nodes .tile').length
  }));
  assert.equal(sources.tiles,104,'real recovered DMP board preserved');
  assert.deepEqual(sources.visible.map(x=>x.card),['0045','0042']);
  assert.deepEqual(sources.visible.map(x=>x.actor),
   ['original-obs-sprite','original-obs-sprite'],
   'original source full-body replaces all synthetic puppets when available');
  assert.ok(sources.visible.every(x=>x.hidden==='none'&&x.poseMapping==='unverified'),
   'no CSS-generated humanoid or invented native pose metadata is displayed');
  assert.deepEqual(sources.visible.map(x=>x.source),['OBS/1045.obs','OBS/1042.obs']);
  assert.ok(sources.visible.every(x=>x.src?.startsWith('./original/OBS/')));
  assert.ok(sources.actors.every(x=>x.originalRecovered==='true'));
  assert.equal(sources.cache['0045'].originalAnimationCount,37);
  assert.equal(sources.cache['0042'].originalAnimationCount,37);
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')].every(img=>img.complete&&img.naturalWidth>20&&img.naturalHeight>60),
   null,{timeout:15000});
  // A loaded authentic OBS character is ANIMATED, not a still bitmap:
  // original source frame zero for 1045/1042 has one size, later real
  // OBS frames have DIFFERENT source dimensions. Old hard-coded sizes
  // [[44,82],[33,71]] falsely rejected genuine 57x69 / 32x69 frames.
  // Compare each ACTUALLY DISPLAYED image URL + natural dimensions
  // against the corresponding original archived frame manifest.
  const sourceFrames=await page.evaluate(()=>[...document.querySelectorAll(
   '#board-pawns .board-pawn')].map(pawn=>{
   const img=pawn.querySelector('.leaf-chess-original-obs');
   const id=pawn.dataset.chessmanId;
   const manifest=window.ORIGINAL_LEAF_OBS_FRAMES[id];
   const frame=manifest?.frames.find(f=>f.url===img?.getAttribute('src'));
   return {id,src:img?.getAttribute('src'),loaded:!!img?.complete,
    sourceMember:manifest?.originalMember,
    actual:[img?.naturalWidth,img?.naturalHeight],
    expected:frame?[frame.width,frame.height]:null,
    sourceFrame:frame?.index,
    poseMapping:pawn.dataset.sourcePoseMapping};
  }));
  assert.deepEqual(sourceFrames.map(f=>f.id),['0045','0042']);
  for(const frame of sourceFrames){
   assert.ok(frame.loaded&&frame.expected,'loaded frame must be in original OBS.pak archive manifest: '+JSON.stringify(frame));
   assert.deepEqual(frame.actual,frame.expected,
    'the current live animation frame must retain its own genuine native dimensions: '+JSON.stringify(frame));
   assert.match(frame.sourceMember,/^10(45|42)\.obs$/);
   assert.equal(frame.poseMapping,'unverified','do not invent historically proven OBS action names');
  }
  const sizes=sourceFrames.map(f=>f.actual);
  assert.equal(await page.locator('#board-pawns img[src*="/Registry/sava"]').count(),0);
  const before=await page.locator('#board-pawns .leaf-chess-original-obs').first().getAttribute('src');
  await page.evaluate(()=>{
   const id=window.__ROG_TEST__.getMatch().players[0].id;
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(id,'walk',750);
  });
  await page.waitForFunction(prev=>{
   const src=document.querySelector('#board-pawns .leaf-chess-original-obs')?.getAttribute('src');
   return src&&src!==prev&&src.includes('1045-');
  },before,{timeout:5000});
  const movement=await page.locator('#board-pawns .leaf-chess-original-obs').first().getAttribute('src');
  assert.notEqual(movement,before,'original OBS walk moves between actual game bitmap frames');
  await page.waitForFunction(()=>document.querySelector('#board-pawns .board-pawn')?.dataset.actorPose==='idle',null,{timeout:4000});
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box')?.dataset.rollCount)>=1,
   null,{timeout:16000});
  const after=await page.evaluate(()=>({
   count:Number(document.querySelector('#dice-box').dataset.rollCount),
   source:window.__LEAF_GENESIS_ACTORS__.getState(),
   roll:window.__ROG_TEST__.getMatch().lastRoll
  }));
  assert.equal(after.count,1,'actual click still rolls real dice');
  assert.ok(after.roll.every(x=>Number.isInteger(x)&&x>=1&&x<=6));
  assert.ok(after.source.rendered[0].counts.walk>=1,'real gameplay movement drives source pose');
  await page.screenshot({path:'leaf-genuine-original-2002-obs-chessmen-'+engine+'.png'});
  assert.deepEqual(errors,[],'no runtime exceptions playing original sprites');
  console.log('AUTHENTIC GENESIS 2002 OBS CHESSMEN + ACTUAL MOVEMENT PASS',
   JSON.stringify({engine,cards:sources.visible.map(x=>x.card),originalPixelSizes:sizes,
    actualFirstRoll:after.roll,sourceFile:movement}));
 }finally{await browser.close()}
})().catch(e=>{console.error('AUTHENTIC OBS CHARACTER FAILED',e.stack||e);process.exit(1)});
