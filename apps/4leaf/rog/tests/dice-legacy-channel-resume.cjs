'use strict';
/* Real-browser regression: pre-Region-channel local saves must remain playable
 * after upgrading 4LEAF, while newly channel-bound games stay isolated.
 * Uses the normal WorldMap -> Region -> Create -> Ready path; only the legacy
 * storage fixture is modified after a genuine playable match has been saved.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',error=>errors.push(error.stack||String(error)));
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__ROG_TEST__);
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#point-limit').selectOption('12');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const initial=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   const saved=JSON.parse(localStorage.getItem('rog_match'));
   if(!m||!saved||m.diceChannel!=='ispin:1'||m.players.length!==2)
    throw Error('a real modern game must be saved before creating a legacy fixture');
   delete saved.diceChannel;
   delete saved.diceRegion;
   localStorage.setItem('rog_match',JSON.stringify(saved));
   return {startedAt:m.startedAt,players:m.players.map(p=>p.id),map:m.map};
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__ROG_TEST__);
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:2"]').click();
  await page.waitForSelector('#lobby:not(.hidden)');
  assert.equal(await page.locator('#lobby-room-list .lobby-room-row[data-match="saved"]').count(),1,
   'a local pre-channel match must not vanish from the upgraded lobby');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_match')).diceChannel),undefined,
   'simply browsing a channel must not silently rewrite an old match');
  await page.locator('#lobby-room-list .lobby-room-row[data-match="saved"]').click();
  await page.waitForSelector('#game:not(.hidden)');
  const resumed=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),stored=JSON.parse(localStorage.getItem('rog_match'));
   return {startedAt:m?.startedAt,players:m?.players.map(p=>p.id),map:m?.map,
    channel:m?.diceChannel,persistedChannel:stored?.diceChannel,
    region:stored?.diceRegion};
  });
  assert.equal(resumed.startedAt,initial.startedAt,'resume must not start over');
  assert.deepEqual(resumed.players,initial.players,'all saved participants must survive');
  assert.equal(resumed.map,initial.map);
  assert.equal(resumed.channel,'ispin:2');
  assert.equal(resumed.persistedChannel,'ispin:2','channel adoption must survive page reload');
  assert.equal(resumed.region,'genesis');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  assert.equal(await page.locator('#lobby-room-list .lobby-room-row[data-match="saved"]').count(),0,
   'a channel-bound game must not leak into another channel');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_match')).diceChannel),'ispin:2',
   'changing channel must never silently reassign an already bound match');
  assert.deepEqual(errors,[],'game restore must not throw browser exceptions');
  console.log('4LEAF LEGACY LOCAL MATCH RESUME PASS '+JSON.stringify({initial,resumed,otherChannelHidden:true}));
 }finally{await browser.close()}
})().catch(error=>{console.error('4LEAF LEGACY LOCAL MATCH RESUME FAIL',error.stack||String(error));process.exit(1)});
