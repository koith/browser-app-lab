'use strict';
/* Regression for a real user's two P0 complaints: the source DMP tiles must
 * preserve ORIGINAL 70x47 DMP logical coordinates without forcing the
 * full 145x97 source artwork to visually overlap by more than half, and
 * the genuine roll button must respond to a physical phone touch, twice.
 * No screenshot overlay, fake player, hard-coded die result or EXE height.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:390,height:844},
  isMobile:true,hasTouch:true,deviceScaleFactor:2,serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes>.tile').length===104);
  const board=await page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   return tiles.map(t=>({x:Number(t.dataset.dmpX),y:Number(t.dataset.dmpY),
    left:t.offsetLeft,top:t.offsetTop,z:Number(t.style.zIndex),
    pixels:[t.offsetWidth,t.offsetHeight],art:t.dataset.originalArt,
    clip:getComputedStyle(t).clipPath}));
  });
  assert.equal(board.length,104,'all 104 genuine DMP cells participate in the game');
  assert.ok(board.every(t=>t.art&&t.clip.startsWith('polygon(')&&
   t.pixels[0]===145&&t.pixels[1]===97),
   'native source platform dimensions and nonrectangular click silhouette preserved');
  const projection=await page.evaluate(()=>window.__LEAF_CAMERA__.getState());
  assert.deepEqual(projection.sourceGrid,{width:1450,height:1120,pitchX:70,pitchY:47});
  let horizontal=0,vertical=0,sameRow=0;
  for(let i=0;i<board.length;i++)for(let j=i+1;j<board.length;j++){
   const a=board[i],b=board[j];
   if(a.y===b.y){
    sameRow++;
    if(a.x!==b.x)assert.equal(Math.sign(b.z-a.z),Math.sign(b.x-a.x),
     'same DMP row must paint in source x order, never route-index parity');
   }else assert.equal(Math.sign(b.z-a.z),Math.sign(b.y-a.y),
    'different source rows must paint in verified y order');
   if(a.y===b.y&&Math.abs(a.x-b.x)===1){
    horizontal++;
    assert.ok(Math.abs(Math.abs(a.left-b.left)-projection.projectedPitch.x)<2.5&&Math.abs(a.left-b.left)>140,
     'DMP x delta stays 1 logical cell; web screen pitch keeps 145px tile art distinct');
   }
   if(a.x===b.x&&Math.abs(a.y-b.y)===1){
    vertical++;
    assert.ok(Math.abs(Math.abs(a.top-b.top)-projection.projectedPitch.y)<2.5&&Math.abs(a.top-b.top)>94,
     'DMP y delta stays 1 source cell; web screen pitch avoids huge native sprite overlap');
   }
  }
  assert.ok(horizontal>5&&vertical>5&&sameRow>5,
   'the recovered DMP map contains enough geometric adjacency samples');
  const mobileCamera=await page.evaluate(()=>window.__LEAF_CAMERA__.getState());
  assert.equal(mobileCamera.scale,.65,
   'phone initial camera fits a wider real DMP field than desktop 125%');
  await page.locator('#board-zoom-in').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_CAMERA__.getState().scale),.9,
   'the + zoom control still zooms the real world, not tile CSS');
  await page.locator('#board-zoom-reset').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_CAMERA__.getState().scale),.65,
   'phone reset returns to its source-preserving fit camera');
  const roll=page.locator('#roll-btn');
  const point=async()=>{
   assert.equal(await roll.isVisible(),true,'roll button remains visible in game');
   assert.equal(await roll.isEnabled(),true,'current manual human may roll');
   const b=await roll.boundingBox();
   assert.ok(b&&b.width>=40&&b.height>=28,'physical touch target is usable');
   assert.ok(b.x>=0&&b.y>=0&&b.x+b.width<=390&&b.y+b.height<=844,
    'roll button is not clipped outside the physical phone viewport');
   return {x:b.x+b.width/2,y:b.y+b.height/2};
  };
  const first=await point();
  await page.screenshot({path:'leaf-4leaf-mobile-dmp-before-roll.png'});
  await page.touchscreen.tap(first.x,first.y);
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box')?.dataset.rollCount)>0,
   null,{timeout:15000});
  async function finishTurn(nextPlayer){
   for(let n=0;n<110;n++){
    const state=await page.evaluate(()=>({
     active:window.__ROG_TEST__.getMatch()?.active,
     enabled:!document.getElementById('roll-btn').disabled,
     modal:!document.getElementById('modal').classList.contains('hidden')
    }));
    if(state.active===nextPlayer&&state.enabled)return;
    if(state.modal){
     const accept=page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).first();
     if(await accept.count())await accept.click();
    }
    await page.waitForTimeout(160);
   }
   throw new Error('A physical dice touch did not advance to participant '+nextPlayer);
  }
  await finishTurn(1);
  const firstTurn=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch(),
   rollCount:Number(document.getElementById('dice-box').dataset.rollCount),
   aria:document.getElementById('dice-box').getAttribute('aria-label')
  }));
  assert.ok(firstTurn.match.history.some(line=>line.includes('이동 주사위')||line.includes('감옥')),
   'a phone tap rolls genuine movement dice and records its game result');
  assert.ok(firstTurn.match.lastRoll.length>=1&&firstTurn.match.lastRoll.every(v=>v>=1&&v<=6),
   'live die face values equal a real saved roll, not a decorative animation');
  assert.equal(firstTurn.match.players[0].bot,false);
  assert.equal(firstTurn.match.players[1].bot,false,'second participant is human-controlled');
  const second=await point();
  await page.touchscreen.tap(second.x,second.y);
  await page.waitForFunction(previous=>Number(document.querySelector('#dice-box')?.dataset.rollCount)>previous,
   firstTurn.rollCount,{timeout:15000});
  const final=await page.evaluate(()=>({
   count:Number(document.getElementById('dice-box').dataset.rollCount),
   history:window.__ROG_TEST__.getMatch().history,
   aria:document.getElementById('dice-box').getAttribute('aria-label')
  }));
  assert.ok(final.history.some(line=>line.includes('플레이어 2 이동 주사위')||line.includes('플레이어 2 감옥')),
   'the second real participant can also roll using the phone touch surface');
  assert.ok(final.count>=2&&final.aria?.includes('주사위 결과'));
  await page.screenshot({path:'leaf-4leaf-mobile-dmp-after-roll.png'});
  assert.deepEqual(errors,[],'dice game has no unhandled Chromium runtime error');
  console.log('GENESIS DMP GRID + ACTUAL MOBILE DICE ROLL PASS ['+engine+']',
   JSON.stringify({cells:board.length,horizontal,vertical,sameRow,
    rolls:final.count,firstRoll:firstTurn.match.lastRoll}));
 }finally{await browser.close()}
})().catch(error=>{console.error('GENESIS DMP GRID + MOBILE ROLL FAILED',
 error.stack||error);process.exit(1)});
