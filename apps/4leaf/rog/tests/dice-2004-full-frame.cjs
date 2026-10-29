'use strict';
/* Source geometry measured from apps/4leaf/assets/board.jpg and battle.jpg.
 * The original 800x600 screenshot paints BOTH opponent rails outside the
 * central 608px IMG/menu strip. All regions remain real game DOM elements. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',err=>errors.push(String(err)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOURCE_ROLL__
   &&window.__LEAF_DICE_FRAME__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelector('#dice-native-minidock')?.dataset.active==='true'
   &&document.querySelectorAll('#game .battle-team-side').length===2);
  const measure=()=>page.evaluate(()=>{
   const rect=s=>{
    const node=document.querySelector(s);
    if(!node)return null;
    const r=node.getBoundingClientRect();
    return {x:r.x,y:r.y,w:r.width,h:r.height};
   };
   const app=rect('#app'),s=[
    'main#main','#game','#game .board-area','#game .scene-banner',
    '#game .battle-team-side.left','#game .battle-team-side.right',
    '.dice-native-minidock','#board-mini','.messenger',
    '#dice-original-selector','#dice-native-party',
    '#dice-source-roll','#roll-btn','#dice-client-sidebar',
    '#app>.workspace>.sidebar'];
   const source=s.map(sel=>[sel,rect(sel)]);
   const elements=Object.fromEntries(source.map(([sel,r])=>
    [sel,r?{x:r.x-app.x,y:r.y-app.y,w:r.w,h:r.h}:null]));
   return {app,source:elements,
    tiles:document.querySelectorAll('#board-nodes .tile').length,
    tileSource:document.querySelector('#board-nodes .tile')?.dataset.originalArt,
    terrain:getComputedStyle(document.querySelector('#board-world')).backgroundImage,
    roll:window.__LEAF_SOURCE_ROLL__.getState(),
    diceFrame:window.__LEAF_DICE_FRAME__.getState()};
  });
  const snap=await measure(),a=snap.source;
  const eq=(selector,key,want,eps=3)=>{
   assert.ok(a[selector]&&Math.abs(a[selector][key]-want)<=eps,
    selector+' '+key+' must be original '+want+'px, got '+a[selector]?.[key]);
  };
  assert.ok(Math.abs(snap.app.w-800)<=2&&Math.abs(snap.app.h-600)<=2,
   'historical desktop game fills original 800x600 client');
  eq('main#main','w',800);eq('#game','w',800);eq('#game .board-area','w',800);
  eq('#game .scene-banner','x',96);eq('#game .scene-banner','w',608);
  eq('#game .battle-team-side.left','x',0);eq('#game .battle-team-side.left','w',96);
  eq('#game .battle-team-side.right','x',704);eq('#game .battle-team-side.right','w',96);
  eq('#board-mini','x',0);eq('#board-mini','w',172);
  eq('.messenger','x',172);eq('.messenger','w',406);
  eq('#dice-original-selector','x',578);eq('#dice-original-selector','w',29);
  // Two actual 92px selector.spr cards plus the source 4px gap.
  eq('#dice-native-party','x',608);eq('#dice-native-party','w',188);
  eq('#app>.workspace>.sidebar','x',578);eq('#app>.workspace>.sidebar','w',222);
  eq('#dice-source-roll','x',400-37);eq('#dice-source-roll','w',74);
  assert.ok(Math.abs(a['.messenger'].y-a['#board-mini'].y)<2
   &&Math.abs(a['.messenger'].y-a['#dice-native-party'].y)<4,
   'all three authentic footer atlases share the same y row');
  assert.equal(snap.tiles,104,'full source 104 DMP cells remain fully rendered');
  assert.ok(snap.terrain.includes('original/IMG/bgtile.png'));
  assert.ok(snap.roll.isReady,'the original battlefield ROLL command stays usable');
  await page.screenshot({path:'leaf-2004-full-width-source-registration.png'});
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box')?.dataset.rollCount)>0,
   null,{timeout:15000});
  assert.equal(await page.locator('#dice-box').getAttribute('data-roll-count'),'1',
   'full-width HUD click drives ONE genuine die roll');
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('#game .board-area')?.clientWidth<520);
  const mobile=await page.evaluate(()=>({
   main:document.querySelector('#main').getBoundingClientRect().width,
   game:document.querySelector('#game').getBoundingClientRect().width,
   roll:document.querySelector('#dice-source-roll').getBoundingClientRect().width,
   sourceTile:document.querySelector('#board-nodes .tile')?.dataset.nativeTisSize,
   active:window.__ROG_TEST__.getMatch()?.active,
   count:document.querySelectorAll('#board-nodes .tile').length
  }));
  assert.ok(mobile.main<=390&&mobile.game<=390&&mobile.roll>=60,
   'narrow mobile keeps responsive interactive original assets without 800px overflow');
  assert.equal(mobile.sourceTile,'145x97');
  assert.equal(mobile.count,104);
  assert.deepEqual(errors,[],'no JavaScript runtime errors from source full-width frame');
  console.log('ORIGINAL 800x600 DICE FULL FRAME REGISTRATION PASS',
   JSON.stringify({map:snap.tiles,desktop:snap.source,mobile}));
 }finally{await browser.close()}
})().catch(error=>{console.error('ORIGINAL DICE FULL FRAME FAILED',error.stack||error);process.exit(1)});
