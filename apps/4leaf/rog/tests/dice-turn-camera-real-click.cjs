'use strict';
/* Real mouse-driven first Dice roll: camera must return from an unrelated
 * manual pan to the actual pawn; turn owner visible in Korean to players. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_CAMERA__&&window.__LEAF_LOBBY__&&window.__ROG_TEST__);
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  await page.locator('#lobby-create').click();
  await page.locator('#map-select').selectOption('No Item');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.locator('#game:not(.hidden)').waitFor();
  assert.match(await page.locator('#dice-turn-banner').textContent(),/내 차례/);
  assert.equal(await page.locator('#dice-turn-banner').getAttribute('data-turn-owner'),'local');
  const before=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),c=window.__LEAF_CAMERA__;
   c.panBy(100000,100000);
   return {position:m.players[0].position,active:m.active,view:c.getState().visible};
  });
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>{
   const m=window.__ROG_TEST__?.getMatch();
   return m?.players?.[0]?.position>0||m?.active!==0||m?.finished;
  },null,{timeout:45000});
  const after=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),v=window.__LEAF_CAMERA__.getState().visible;
   const pawn=m.players[0],path=window.__LEAF_CAMERA__.getState().path;
   const point=path?.[pawn.position];
   return {position:pawn.position,active:m.active,view:v,point,
    banner:document.getElementById('dice-turn-banner')?.textContent};
  });
  assert.ok(after.position>0,'the actual source pawn moved after the native roll');
  assert.ok(after.point&&after.view,'source camera has a visible window and real pawn');
  const x=after.point.x/100,y=after.point.y/100,v=after.view;
  assert.ok(x>=v.x-.025&&x<=v.x+v.width+.025&&y>=v.y-.025&&y<=v.y+v.height+.025,
   'moved pawn must remain within the actual camera viewport '+JSON.stringify(after));
  // No simulated turn changes: watch for actual dice-game advancement to AI.
  await page.waitForFunction(()=>{
   const m=window.__ROG_TEST__?.getMatch();
   return m?.players?.[m.active]?.bot===true||m?.finished;
  },null,{timeout:45000});
  if(!(await page.evaluate(()=>window.__ROG_TEST__.getMatch().finished))){
   assert.match(await page.locator('#dice-turn-banner').textContent(),/상대 AI 차례/);
   assert.equal(await page.locator('#dice-turn-banner').getAttribute('data-turn-owner'),'opponent');
  }
  assert.deepEqual(errors,[]);
  console.log('4LEAF_REAL_DICE_TURN_CAMERA_PASS',JSON.stringify({
   panBefore:before.view,rollMove:after.position,actualPawnVisible:true,
   owner:await page.locator('#dice-turn-banner').getAttribute('data-turn-owner')
  }));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error('4LEAF_REAL_DICE_TURN_CAMERA_FAIL',e.stack||e);process.exitCode=1});
