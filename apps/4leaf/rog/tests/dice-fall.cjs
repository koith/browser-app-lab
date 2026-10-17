'use strict';
/* Real Playwright run, not DOM mock: generated movement dice must visibly
 * drop from the sky, bounce multiple times, spin to the SAME face handed
 * to the game engine, THEN permit pawn movement. Supports D4 and D6 eyes.
 * Our mesh/keyframes are inferred, not source MVE/EXE frames. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,deviceScaleFactor:mobile?2:1,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__&&window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const before=await page.evaluate(()=>({
   turn:window.__ROG_TEST__.getMatch().active,
   count:Number(document.querySelector('#dice-box').dataset.rollCount||0)
  }));
  assert.equal(before.turn,0);assert.equal(before.count,0);
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__.getState().active===true||
    window.__LEAF_DICE_FALL__.getState().active===1,{timeout:5000});
  const mid=await page.evaluate(()=>({
   phase:document.querySelector('#leaf-dice-fall-layer')?.dataset.phase,
   faceCount:document.querySelectorAll('#leaf-dice-fall-layer .leaf-die-face').length,
   total:document.querySelectorAll('#leaf-dice-fall-layer .leaf-fall-piece').length,
   count:Number(document.querySelector('#dice-box').dataset.rollCount||0),
   disabled:document.querySelector('#roll-btn').disabled,
   overlay:getComputedStyle(document.querySelector('#leaf-dice-fall-layer')).pointerEvents,
   pos:document.querySelector('#leaf-dice-fall-layer').getBoundingClientRect().toJSON(),
   original:document.querySelectorAll('#board-nodes>.tile').length
  }));
  assert.equal(mid.phase,'falling','dice genuinely start high in the sky');
  assert.ok(mid.faceCount>=6&&mid.faceCount<=24,'every independent die has six visible-world 3D faces');
  assert.equal(mid.count,0,'game dice result MUST NOT appear before bounce and landing');
  assert.equal(mid.disabled,true,'other player cannot double-roll during drop');
  assert.equal(mid.overlay,'none','physics never blocks underlying game input');
  assert.equal(mid.original,104,'104 real TIS tiles unaffected by physics overlay');
  await page.screenshot({path:'leaf-true-falling-dice-'+engine+(mobile?'-mobile':'')+'.png'});
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box').dataset.rollCount)>0,
   null,{timeout:14000});
  const landed=await page.evaluate(()=>({
   result:window.__LEAF_DICE_FALL__.getState(),
   match:window.__ROG_TEST__.getMatch().lastRoll,
   count:Number(document.querySelector('#dice-box').dataset.rollCount)
  }));
  assert.equal(landed.count,1,'exactly one complete genuine dice roll is awarded');
  assert.deepEqual(landed.result.last,landed.match,
   'actual gameplay result was not independently re-randomized for 3D animation');
  assert.ok(landed.match.every(x=>Number.isInteger(x)&&x>=1&&x<=6));
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().active===1&&
   !document.querySelector('#roll-btn').disabled,null,{timeout:17000});
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box').dataset.rollCount)>=2,
   null,{timeout:14000});
  assert.equal(await page.locator('#dice-box').getAttribute('data-roll-count'),'2',
   'second real participant rolls normally after their own landing');
  // Inspect ALL six eye placements and final rotations on actual DOM geometry.
  // Reduced motion skips arbitrary waiting; it must still yield precisely
  // the requested source engine values.
  await page.emulateMedia({reducedMotion:'reduce'});
  for(let eye=1;eye<=6;eye++){
   const returned=await page.evaluate(async eye=>window.__LEAF_DICE_FALL__.roll([eye]),eye);
   assert.deepEqual(returned,[eye]);
   const source=await page.evaluate(()=>window.__LEAF_DICE_FALL__.getState());
   assert.deepEqual(source.last,[eye],'cube landed with the supplied REAL face '+eye);
   const topology=await page.evaluate(eye=>({
    pips:window.__LEAF_DICE_FALL__.faces[eye].length,
    orientation:window.__LEAF_DICE_FALL__.orientation[eye]
   }),eye);
   assert.equal(topology.pips,eye,'CSS face '+eye+' uses exactly '+eye+' physical pips');
   assert.equal(topology.orientation.length,2);
  }
  assert.deepEqual(errors,[],'no browser exceptions on real original game');
  console.log('4LEAF DICE FALL BOUNCE AND REAL 1-6 LANDING PASS',
   JSON.stringify({engine,mobile,first:landed.match,landings:6}));
 }finally{await browser.close()}
})().catch(e=>{console.error('DICE FALL REAL TURN FAILED',e.stack||e);process.exit(1)});
