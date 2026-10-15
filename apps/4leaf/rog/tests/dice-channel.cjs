'use strict';
// Region/regionback.png with TOWN SELECT is a Genesis World dice channel menu.
// WorldMap north/south Haiacan are entirely separate ChatTown destinations.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1120,height:820}});
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.locator('[data-region="north"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'north Haiacan must be chat');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'north');
  assert.ok((await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/northback.png'));
  assert.equal(await page.locator('#dice-channels:not(.hidden)').count(),0,'no dice channel art within northern ChatTown');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('[data-region="south"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'south Haiacan must be chat');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
  assert.ok((await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/southback.png'));
  await page.locator('[data-route="sky"]').first().click();

  await page.locator('[data-region="dice"]').click();
  assert.ok(await page.locator('#dice-channels:not(.hidden)').isVisible(),'dice island alone opens TOWN SELECT');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28,'seven original dice channels with four seats each');
  assert.equal(await page.locator('#rooms:not(.hidden)').count(),0,'dice channel screen is not ChatTown');
  assert.ok((await page.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('Region/regionback.png'));
  await page.locator('#dice-channels [data-channel="ispin:3"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:3');
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'genesis','dice channels have no Haiacan chat region');
  assert.ok(await page.locator('#lobby:not(.hidden)').isVisible());
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  assert.deepEqual(await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();return [m.diceRegion,m.diceChannel]}),['genesis','ispin:3'],'saved game carries actual dice channel');
  await page.evaluate(()=>window.__ROG_TEST__.go('sky'));
  await page.locator('[data-region="south"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'playing dice does not rewire Haiacan chat');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="benya:4"]').click();
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['genesis','benya:4']);
  assert.equal(await page.locator('#lobby-room-list .lobby-room-row').count(),0,'a saved Ispin match does not leak into Benya channel');
  assert.ok(await page.locator('#lobby-room-list .lobby-room-empty').isVisible(),'other dice channel correctly has an empty lobby');

  // Retain chat logs saved by earlier incorrect region/channel mixing.
  await page.evaluate(()=>{
   const oldScope='town:north:ispin:2',key='leaf_social_log_'+encodeURIComponent(oldScope);
   localStorage.setItem(key,JSON.stringify([{id:'legacy-dice-chat-key-test',scope:oldScope,
    text:'보존되어야 할 이전 채팅 기록',user:'기존사용자',sender:'old-tab',time:Date.now()-50000}]));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__);
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['genesis','benya:4'],'dice channel persists independent of chat region');
  await page.locator('[data-region="north"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
  assert.ok((await page.locator('#chat-log').textContent()).includes('보존되어야 할 이전 채팅 기록'),'old misclassified chat history is preserved');
  assert.ok(await page.evaluate(()=>localStorage.getItem('leaf_social_log_'+encodeURIComponent('town:north:ispin:2'))!==null),'original saved chat keys not destroyed');
  await page.locator('#social-chat-south').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28,'ChatTown navigation never alters Genesis channel selector');
  await page.screenshot({path:'leaf-dice-channel-chat-independent.png'});
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('GENESIS DICE TOWN SELECT PASS: WorldMap Haiacan→ChatTown, dice→28 channel slots, saved match isolation and history');
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS DICE TOWN SELECT FAILED',e.stack||e);process.exit(1)});
