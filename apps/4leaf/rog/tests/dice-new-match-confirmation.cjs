'use strict';
/* UI regression for saved 4LEAF game preservation. Create a real match from
 * WorldMap/Region/ROOM READY, leave via the actual in-game Exit control, then
 * attempt to create a second match. Neither cancellation nor validation may
 * modify the old game's state. Confirmation alone replaces it.
 * The original client behavior is unknown; this is a WEB data-safety rule.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const mobile=process.env.FOURLEAF_MOBILE==='1';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 const tap=loc=>mobile?loc.tap():loc.click();
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&window.__LEAF_WORLD__);
  await tap(page.locator('.world-location[data-region="dice"]'));
  await tap(page.locator('#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]'));
  await tap(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#point-limit').selectOption('12');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await tap(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
  assert.equal(await page.locator('#modal:not(.hidden)').count(),0,
   'a first-ever match must launch immediately, with no replacement dialog');
  const previous=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].position=5;
   m.history.push('TEST-SAVED-IN-PROGRESS');
   m.round=3;
   localStorage.setItem('rog_match',JSON.stringify(m));
   return JSON.stringify(m);
  });
  await tap(page.locator('#exit-game'));
  await page.waitForSelector('#modal:not(.hidden)');
  await tap(page.locator('#modal-buttons button').filter({hasText:'나가기'}));
  await page.waitForSelector('#lobby:not(.hidden)');
  await tap(page.locator('#lobby-create'));
  await page.locator('#map-select').selectOption('PK');
  await tap(page.locator('#start-game'));
  await page.waitForSelector('#modal:not(.hidden)');
  assert.match(await page.locator('#modal-title').textContent(),/진행 중인 경기 보호/);
  assert.match(await page.locator('#modal-content').textContent(),/기록이 교체됩니다/);
  const beforeCancel=await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch()));
  assert.equal(beforeCancel,previous,'opening replacement confirmation must not mutate old match');
  assert.equal(await page.evaluate(()=>localStorage.getItem('rog_match')),previous,
   'replacement confirmation must not mutate persisted match');
  await tap(page.locator('#modal-buttons button').filter({hasText:'기존 경기 유지'}));
  assert.equal(await page.locator('#modal:not(.hidden)').count(),0);
  const canceled=await page.evaluate(()=>({
   route:document.querySelector('.scene:not(.hidden)')?.id,
   memory:JSON.stringify(window.__ROG_TEST__.getMatch()),saved:localStorage.getItem('rog_match')
  }));
  assert.equal(canceled.route,'lobby');
  assert.equal(canceled.memory,previous);
  assert.equal(canceled.saved,previous);
  await tap(page.locator('#start-game'));
  await page.waitForSelector('#modal:not(.hidden)');
  await tap(page.locator('#modal-buttons button').filter({hasText:'새 경기 시작'}));
  await page.waitForSelector('#game:not(.hidden)');
  const next=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {map:m.map,round:m.round,positions:m.players.map(p=>p.position),
     history:m.history,startedAt:m.startedAt,stored:JSON.parse(localStorage.getItem('rog_match'))};
  });
  assert.equal(next.map,'PK','explicit confirmation starts the selected new map');
  assert.equal(next.round,1);
  assert.deepEqual(next.positions,[0,0]);
  assert.ok(!next.history.includes('TEST-SAVED-IN-PROGRESS'),
   'only explicit replacement may discard the prior game history');
  assert.equal(next.stored.map,'PK','new game must be persisted only after confirmation');
  assert.deepEqual(errors,[],'no uncaught browser errors during save protection');
  console.log('4LEAF SAVED MATCH REPLACEMENT CONSENT PASS '+JSON.stringify({
   engine:engine.name(),mobile,oldMap:'4LEAF',newMap:next.map,
   canceledKeepsExactMemory:true,canceledKeepsExactSavedJson:true,
   explicitConfirmationReplaces:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF SAVED MATCH REPLACEMENT CONSENT FAIL',e.stack||String(e));process.exit(1)});
