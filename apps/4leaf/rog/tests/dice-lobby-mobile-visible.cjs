'use strict';
/* Source-accurate native Map/Room waiting-room visual acceptance.
 * A prior click-only smoke test passed even though a 794px bitmap was
 * shrunk to unreadable ~390px on phones. Prove legibility-oriented zoom,
 * visibility of real participant/config data, reachable READY and game.
 * Interact with real WorldMap/Region/button UI, not hidden route APIs. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const phone=process.env.FOURLEAF_MOBILE==='1';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const ctx=await browser.newContext({viewport:phone?{width:390,height:844}:{width:1280,height:900},
  isMobile:phone,hasTouch:phone,serviceWorkers:'block'});
 const page=await ctx.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',
   {waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&
   window.__LEAF_DICE_NATIVE__&&window.__ROG_TEST__,null,{timeout:25000});
  const tap=el=>phone?el.tap():el.click();
  const region=page.locator('.world-location[data-region="dice"]');
  let opened=false;
  const rect=await region.boundingBox();
  for(const [xx,yy] of [[.5,.5],[.35,.42],[.6,.7]]){
   if(!rect)throw Error('no source WorldMap dice region');
   if(await page.locator('#dice-channels:not(.hidden)').count()){opened=true;break}
   await (phone?region.tap({position:{x:rect.width*xx,y:rect.height*yy}}):
    region.click({position:{x:rect.width*xx,y:rect.height*yy}}));
   await page.waitForTimeout(120);
  }
  assert.ok(opened||await page.locator('#dice-channels:not(.hidden)').count(),
   'a real source WorldMap region must enter Dice TOWN SELECT');
  await tap(page.locator('#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]'));
  await page.locator('#lobby:not(.hidden)').waitFor();
  await page.waitForFunction(()=>window.__LEAF_DICE_NATIVE__?.getState().scale>0);
  const original=await page.evaluate(async()=>{
   const img=async file=>{const i=new Image();i.src=file;await i.decode();
    return [i.naturalWidth,i.naturalHeight]};
   const [map,room]=await Promise.all([
    img('./original/Map/mapback.png'),img('./original/Room/roomback.png')]);
   const scene=document.getElementById('dice-lobby-scene');
   const stage=document.getElementById('dice-native-stage');
   return {map,room,source:window.__LEAF_DICE_NATIVE__.getState(),
    background:getComputedStyle(stage).backgroundImage,
    actualScene:scene.getBoundingClientRect().toJSON(),
    emptyAction:!!document.querySelector('#lobby-room-list .lobby-room-empty-create'),
    emptyMessage:document.querySelector('#lobby-room-list')?.textContent?.slice(0,110)};
  });
  assert.deepEqual(original.map,[794,404]);
  assert.deepEqual(original.room,[794,404]);
  assert.equal(original.source.source,'Map/mapback.png');
  assert.ok(original.background.includes('original/Map/mapback.png'));
  assert.ok(original.emptyAction,'zero stored matches require visible real CREATE action');
  if(phone){
   assert.equal(original.source.zoomed,true,'phone waiting room must open ENLARGED');
   assert.ok(original.source.scale>=original.source.fitScale*1.80);
   assert.ok(original.source.actualStageWidth>original.source.availableWidth*1.78,
    'native 794 source pixels must not shrink down to hard-to-read tiny text');
   assert.equal(await page.locator('#dice-room-zoom-toggle').getAttribute('aria-pressed'),'true');
  }else{
   assert.equal(original.source.zoomed,false);
   assert.ok(original.source.actualStageWidth<=original.source.availableWidth+1);
  }
  await page.screenshot({path:'leaf-room-select-actual-'+engine.name()+(phone?'-phone':'-desktop')+'.png'});
  await tap(page.locator('#lobby-room-list .lobby-room-empty-create'));
  await page.locator('#dice-lobby-scene.config-open').waitFor();
  assert.equal(await page.locator('#lobby-players .lobby-seat').count(),8,
   'room creation must display all eight REAL PLAYER slots');
  const config=await page.evaluate(()=>{
   const stage=document.getElementById('dice-native-stage');
   const seats=[...document.querySelectorAll('#lobby-players .lobby-seat')];
   const rect=el=>el.getBoundingClientRect().toJSON();
   return {background:getComputedStyle(stage).backgroundImage,
    view:window.__LEAF_DICE_NATIVE__.getState(),
    firstSeat:rect(seats[0]),room:rect(document.getElementById('dice-lobby-scene')),
    ready:rect(document.getElementById('start-game')),
    nativeButtons:window.__LEAF_DICE_ROOM_BUTTONS__?.getState(),
    selected:document.getElementById('game-mode').value};
  });
  assert.equal(config.view.source,'Room/roomback.png');
  assert.ok(config.background.includes('original/Room/roomback.png'));
  assert.ok(config.firstSeat.width>0&&config.firstSeat.height>0);
  if(phone){
   assert.equal(config.view.zoomed,true);
   assert.ok(config.firstSeat.x>=config.room.x-2&&
    config.firstSeat.x<config.room.right,
    'opening waiting room must place the real PLAYER list on-screen');
   assert.equal(await page.locator('#dice-room-settings-focus').isVisible(),true);
   assert.equal(await page.locator('#dice-room-ready-focus').isVisible(),true);
   await tap(page.locator('#dice-room-zoom-toggle'));
   assert.equal(await page.evaluate(()=>window.__LEAF_DICE_NATIVE__.getState().zoomed),false);
   const fit=await page.evaluate(()=>window.__LEAF_DICE_NATIVE__.getState());
   assert.ok(fit.actualStageWidth<=fit.availableWidth+2,
    'whole original ROOM must remain available via one clear action');
   await tap(page.locator('#dice-room-zoom-toggle'));
   await tap(page.locator('#dice-room-settings-focus'));
  }
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  if(phone)await tap(page.locator('#dice-room-ready-focus'));
  const ready=await page.evaluate(()=>{
   const source=document.getElementById('start-game');
   const room=document.getElementById('dice-lobby-scene');
   const a=source.getBoundingClientRect(),b=room.getBoundingClientRect();
   const hit=document.elementFromPoint(a.x+a.width/2,a.y+a.height/2);
   return {box:a.toJSON(),viewport:b.toJSON(),hit:hit?.id||hit?.closest('button')?.id||null};
  });
  assert.ok(ready.box.width>=45&&ready.box.height>=30);
  assert.ok(ready.box.x>=ready.viewport.x-2&&
   ready.box.right<=ready.viewport.right+2,
   'native ROOM READY must be fully reachable without offscreen tap');
  await page.screenshot({path:'leaf-room-wait-actual-'+engine.name()+(phone?'-phone':'-desktop')+'.png'});
  await tap(page.locator('#start-game'));
  await page.locator('#game:not(.hidden)').waitFor({timeout:18000});
  assert.equal(await page.locator('#board-nodes>.tile').count(),104,
   'real room READY must create all 104 original DMP cells');
  const match=await page.evaluate(()=>window.__ROG_TEST__.getMatch());
  assert.equal(match.players.length,2);
  assert.equal(match.diceChannel,'ispin:1');
  assert.deepEqual(errors,[],'room UI must not throw browser JS errors');
  console.log('4LEAF_GENESIS_ROOM_VISUAL_ACCESS_PASS',JSON.stringify({
   engine:engine.name(),phone,source:'Map/mapback and Room/roomback originals',
   initialScale:original.source.scale,fit:original.source.fitScale,
   creationScale:config.view.scale,
   nativeScreensVisible:true,players:8,readyOnScreen:true,gameTiles:104,
   errors:errors.length
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_GENESIS_ROOM_VISUAL_ACCESS_FAIL',e.stack||String(e));process.exit(1)});
