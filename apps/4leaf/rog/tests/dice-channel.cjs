'use strict';
// Native Region/regionback.png belongs ONLY to Genesis World dice channels.
// Real Chromium integration: WorldMap > channel > actual lobby > match.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1120,height:820}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.locator('[data-region="north"]').click();
  assert.ok(await page.locator('#dice-channels:not(.hidden)').isVisible());
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28);
  assert.equal(await page.locator('#rooms:not(.hidden)').count(),0,'Town Select is not ChatTown');
  assert.ok((await page.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('Region/regionback.png'));
  await page.locator('#dice-channels [data-channel="ispin:3"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:3');
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'north');
  assert.ok(await page.locator('#lobby:not(.hidden)').isVisible());
  assert.equal(await page.locator('#social-image-frame.social-region-channels').count(),0,'No ChatTown channel scene exists');
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  assert.deepEqual(await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();return [m.diceRegion,m.diceChannel]}),['north','ispin:3'],'matches use the selected dice channel');
  await page.evaluate(()=>window.__ROG_TEST__.go('sky'));
  assert.ok(await page.locator('#sky:not(.hidden)').isVisible(),'game route restores the WorldMap');
  await page.locator('[data-region="south"]').click();
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28);
  await page.locator('#dice-channels [data-channel="benya:4"]').click();
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['south','benya:4']);
  assert.equal(await page.locator('#lobby-room-list .lobby-room-row').count(),0,'a northern Ispin saved match must not leak into southern Benya channel');
  assert.ok(await page.locator('#lobby-room-list .lobby-room-empty').isVisible(),'a different dice channel has an independent empty room list');
  // A previous reconstruction incorrectly put ChatTown log messages under
  // dice channel keys. Preserve those user messages across the correction.
  await page.evaluate(()=>{
   const oldScope='town:north:ispin:2',key='leaf_social_log_'+encodeURIComponent(oldScope);
   localStorage.setItem(key,JSON.stringify([{id:'legacy-dice-chat-key-test',scope:oldScope,
    text:'보존되어야 할 이전 채팅 기록',user:'기존사용자',sender:'old-tab',time:Date.now()-50000}]));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__);
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['south','benya:4'],'dice channel persists within the browsing session');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town','chat never becomes a dice channel');
  await page.locator('[data-route="rooms"]').first().click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'real ChatTown is independently accessible');
  assert.equal(await page.locator('.social-district-hotspot').count(),8);
  assert.ok((await page.locator('#chat-log').textContent()).includes('보존되어야 할 이전 채팅 기록'),'previously channel-misclassified chat history is safely migrated');
  assert.ok(await page.evaluate(()=>localStorage.getItem('leaf_social_log_'+encodeURIComponent('town:north:ispin:2'))!==null),'old user log keys are kept for non-destructive migration');
  await page.locator('#social-chat-south').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28,'ChatTown switching never modifies the dice selector');
  await page.screenshot({path:'leaf-dice-channel-chat-independent.png'});
  assert.deepEqual(errors,[],'no browser errors');
  console.log('GENESIS DICE TOWN SELECT PASS: both regions, 28 original selectors, lobby, real match channel, reload and independent chat');
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS DICE TOWN SELECT FAILED',e.stack||e);process.exit(1)});
