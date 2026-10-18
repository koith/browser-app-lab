'use strict';
/* Regression against original board.jpg / battle.jpg: the visible ROLL disc
 * occupies the battlefield, but delegates to the actual turn engine. No
 * fake dice, no second game state, no screenshot/background click overlay. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  hasTouch:mobile,isMobile:mobile,deviceScaleFactor:mobile?2:1,
  serviceWorkers:'block'});
 const errors=[];page.on('pageerror',err=>errors.push(String(err)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOURCE_ROLL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const source=page.locator('#dice-source-roll'),primary=page.locator('#roll-btn');
  await page.waitForFunction(()=>{
   const btn=document.querySelector('#dice-source-roll');
   const img=btn?.querySelector('.dice-original-roll-spr');
   return btn?.dataset.nativeRollSource==='ready'&&
    img?.complete&&img.naturalWidth===69&&img.naturalHeight===51;
  },null,{timeout:12000});
  const originalRollSprite=await page.evaluate(()=>({
   state:window.__LEAF_SOURCE_ROLL__.getState(),
   source:document.querySelector('#dice-source-roll .dice-original-roll-spr')?.getAttribute('src'),
   natural:[document.querySelector('#dice-source-roll .dice-original-roll-spr')?.naturalWidth,
    document.querySelector('#dice-source-roll .dice-original-roll-spr')?.naturalHeight],
   shown:getComputedStyle(document.querySelector('#dice-source-roll .dice-original-roll-spr')).display
  }));
  assert.equal(originalRollSprite.state.originalSource,'Dice/IMG.pak:eventRoll1.spr');
  assert.equal(originalRollSprite.state.nativeFrameCount,16);
  assert.ok(originalRollSprite.source.endsWith('/SourceSPR/eventRoll1-00.png'));
  assert.deepEqual(originalRollSprite.natural,[69,51]);
  assert.notEqual(originalRollSprite.shown,'none');
  console.log('GENUINE_SOURCE_ROLL_SPR_ACTIVE '+JSON.stringify(originalRollSprite));

  assert.equal(await source.count(),1,'a single real battlefield ROLL surface is mounted');
  assert.equal(await source.isVisible(),true,'battlefield ROLL is visible on real match');
  assert.equal(await primary.isEnabled(),true,'existing genuine roll handler is ready');
  assert.equal(await source.isEnabled(),true,'battlefield ROLL mirrors real turn permissions');
  const before=await page.evaluate(()=>{
   const game=document.querySelector('#game'),button=document.querySelector('#dice-source-roll');
   const source=window.__LEAF_SOURCE_ROLL__.getState();
   const gr=game.getBoundingClientRect(),br=button.getBoundingClientRect();
   const x=br.x+br.width/2,y=br.y+br.height/2;
   return {source,scene:[gr.x,gr.y,gr.width,gr.height],
    click:[x,y],button:[br.x,br.y,br.width,br.height],
    target:document.elementFromPoint(x,y)?.closest('#dice-source-roll')?.id||null,
    tileCount:document.querySelectorAll('#board-nodes .tile').length,
    forest:getComputedStyle(document.querySelector('#board-world')).backgroundImage
   };
  });
  assert.equal(before.source.evidence,'original-2002-IMG-SPR/palette-frames',
   'genuine source IMG.pak artwork must replace the old CSS orb when the native sprite is present');
  assert.equal(before.tileCount,104,'native 104-cell DMP remains intact under the ROLL HUD');
  assert.ok(before.forest.includes('IMG/bgtile.png'),
   'real original terrain art remains the original interactive game background');
  assert.equal(before.target,'dice-source-roll',
   'physical press reaches source-positioned ROLL without a transparent overlay blocking it');
  assert.ok(before.click[0]>=0&&before.click[1]>=0
   &&before.click[0]<= (mobile?390:1280)
   &&before.click[1]<= (mobile?844:900),'physical ROLL center stays on-screen');
  if(!mobile){
   const px=(before.click[0]-before.scene[0])/before.scene[2];
   assert.ok(px>.47&&px<.53,'original 800px reference centers ROLL at x400');
   assert.ok(before.button[2]>=70&&before.button[3]>=48,
    '2004 approximate ROLL mesh occupies ~74x53 original logical pixels');
  }else{
   assert.ok(before.button[2]>=60&&before.button[3]>=44,
    'mobile preserves a reachable physical ROLL control');
  }
  await page.screenshot({path:'leaf-source-roll-'+engine+(mobile?'-mobile':'-desktop')+'-before.png'});
  if(mobile)await page.touchscreen.tap(...before.click);
  else await source.click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box')?.dataset.rollCount)>0,
   null,{timeout:12000});
  const afterRoll=await page.evaluate(()=>({
   count:Number(document.querySelector('#dice-box').dataset.rollCount),
   match:window.__ROG_TEST__.getMatch(),
   nativeTriggers:window.__LEAF_SOURCE_ROLL__.getState().nativeTriggerCount
  }));
  assert.equal(afterRoll.nativeTriggers,1,
   'clicking the original source ROLL control must animate genuine eventRoll1.spr exactly once');
  assert.equal(afterRoll.count,1,'one click invokes exactly ONE genuine movement dice roll');
  assert.ok(afterRoll.match.lastRoll.length>=1&&
   afterRoll.match.lastRoll.every(eye=>eye>=1&&eye<=6),
   'visible dice were generated by real gameplay values');
  for(let n=0;n<110;n++){
   const state=await page.evaluate(()=>({
    active:window.__ROG_TEST__.getMatch().active,
    ready:!document.querySelector('#roll-btn').disabled,
    modal:!document.querySelector('#modal').classList.contains('hidden')
   }));
   if(state.active===1&&state.ready)break;
   if(state.modal){
    const confirm=page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).first();
    if(await confirm.count())await confirm.click();
   }
   await page.waitForTimeout(160);
  }
  const second=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch(),
   real:!document.querySelector('#roll-btn').disabled,
   source:!document.querySelector('#dice-source-roll').disabled,
   visible:document.querySelector('#dice-source-roll').getBoundingClientRect().width>0
  }));
  assert.equal(second.match.active,1,'genuine first participant turn advances normally');
  assert.ok(second.real&&second.source&&second.visible,
   'source ROLL follows second human participant without an AI fake turn');
  await primary.click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box')?.dataset.rollCount)===2,
   null,{timeout:12000});
  assert.equal(await page.locator('#dice-source-roll').getAttribute('data-roll-count'),'2',
   'both game control surfaces display one synchronized count from same engine');
  assert.equal(await page.evaluate(()=>
   window.__LEAF_SOURCE_ROLL__.getState().nativeTriggerCount),2,
   'main/keyboard-accessible ROLL must animate SAME recovered eventRoll1.spr once per roll');
  await page.screenshot({path:'leaf-source-roll-'+engine+(mobile?'-mobile':'-desktop')+'-after.png'});
  assert.deepEqual(errors,[],'the source-positioned ROLL has no uncaught Chromium/WebKit errors');
  console.log('SOURCE ROLL HUD + REAL GAME TURN PASS',JSON.stringify({
   engine,mobile,sourcePoint:before.click,originalTiles:before.tileCount,
   firstTurn:afterRoll.match.lastRoll,counts:2}));
 }finally{await browser.close()}
})().catch(error=>{
 console.error('SOURCE ROLL HUD FAILED',error.stack||error);
 process.exit(1);
});
