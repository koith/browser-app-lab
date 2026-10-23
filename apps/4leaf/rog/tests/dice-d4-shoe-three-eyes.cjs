'use strict';
/* Live original-rules D4+D4(+shoe) regression. 2002 gameplay source data
 * decides every eye; the WEB HUD must never hide an actual bonus die.
 * Neither the archived original 3D mesh nor original MVE FPS is claimed.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_FALL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const setup=await page.evaluate(()=>{
   const test=window.__ROG_TEST__,match=test.getMatch(),p=match.players[0];
   // Three genuinely archived D4 movement Chessmen, not synthetic roll eyes.
   p.team=['c_0043','c_0044','c_0048'];
   p.effects.shoe=1;
   // Avoid unrelated location triggers while measuring the presentation.
   for(let i=1;i<22;i++)match.tiles[i]='normal';
   test.drawGame();
   const stat=test.teamStats(p.team);
   return {sides:stat.move,bonus:p.effects.shoe,position:p.position,
    expectedCount:test.moveValues({...p,effects:{...p.effects}}).length};
  });
  assert.equal(setup.sides,2,'the genuine source party must roll D4+D4');
  assert.equal(setup.expectedCount,3,'the authentic shoe modifier creates a third D4');
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box').dataset.rollCount)>=1,
   null,{timeout:22000});
  const actual=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch(),box=document.getElementById('dice-box');
   const cells=[...box.querySelectorAll('.die')].map(x=>({
    eye:Number(x.dataset.eye),glyph:x.textContent,ordinal:x.dataset.rollIndex
   }));
   return {real:match.lastRoll,cells,count:Number(box.dataset.diceCount),
    metadata:box.dataset.actualEyes,extra:box.querySelectorAll('.leaf-extra-roll-eye').length,
    aria:box.getAttribute('aria-label'),position:match.players[0].position,
    motion:window.__LEAF_DICE_FALL__.getState()};
  });
  assert.equal(actual.real.length,3);
  assert.ok(actual.real.every(v=>Number.isInteger(v)&&v>=1&&v<=4));
  assert.equal(actual.count,3);
  assert.equal(actual.extra,1,'a real third D4 must have its own visible HUD die');
  assert.deepEqual(actual.cells.map(c=>c.eye),actual.real,
   'all rendered eyes must match the real authoritative source roll');
  assert.equal(actual.metadata,actual.real.join(','));
  assert.equal(actual.aria,'주사위 결과 '+actual.real.join(' + '));
  assert.deepEqual(actual.motion.last,actual.real);
  assert.equal(actual.motion.lastSides.join(','),'4,4,4');
  assert.ok(actual.position>=0);
  assert.deepEqual(errors,[]);
  console.log('AUTHENTIC D4 SHOE BONUS 3 ACTUAL EYES PASS '+JSON.stringify({mobile,actual}));
 }finally{await browser.close()}
})().catch(e=>{console.error('D4 THIRD EYE GAMEPLAY FAILED',e.stack||e);process.exit(1)});
