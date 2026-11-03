'use strict';
/* A corrupted preexisting rog_match JSON string must NOT be destroyed by
 * initial profile rendering, which normally calls persist(). Starting a
 * genuine new game stores an exact raw-byte recovery snapshot first. A later
 * corrupt save must never overwrite the earlier backup. This is browser
 * data-loss prevention, not a claim of original 2002 archive recovery. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const mobile=process.env.FOURLEAF_MOBILE==='1';
(async()=>{
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
 const raw1='{"version":5,"players":[{"id":0},';
 const raw2='{"pending":[';
 const errors=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 const interact=locator=>mobile?locator.tap():locator.click();
 const start=async()=>{
  await interact(page.locator('.world-location[data-region="dice"]'));
  await interact(page.locator('#dice-channels [data-channel="ispin:1"]'));
  await interact(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#point-limit').selectOption('12');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await interact(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
  assert.equal(await page.locator('#modal:not(.hidden)').count(),0,
   'a malformed preexisting save must not block a real new game');
 };
 try{
  await page.addInitScript(raw=>{
   // addInitScript executes on every reload. Seed only the first navigation.
   if(sessionStorage.getItem('__leaf_corrupt_fixture'))return;
   sessionStorage.setItem('__leaf_corrupt_fixture','seeded');
   localStorage.setItem('rog_match',raw);
   window.LEAF_CENTRAL_API_URL='';
  },raw1);
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&window.__LEAF_WORLD__);
  let storage=await page.evaluate(()=>({
   raw:localStorage.getItem('rog_match'),
   oldBackup:localStorage.getItem('rog_match_invalid_backup_v1'),
   currentMatch:window.__ROG_TEST__.getMatch()
  }));
  assert.equal(storage.raw,raw1,
   'the bootstrap profileUI/persist must not erase a malformed match');
  assert.equal(storage.oldBackup,null,
   'do not move the invalid save to another key until replacement is committed');
  assert.equal(storage.currentMatch,null);
  await start();
  storage=await page.evaluate(()=>({
   backup:localStorage.getItem('rog_match_invalid_backup_v1'),
   saved:JSON.parse(localStorage.getItem('rog_match'))
  }));
  assert.equal(storage.backup,raw1,'new match must preserve original malformed bytes exactly');
  assert.equal(storage.saved.map,'4LEAF');
  assert.equal(storage.saved.players.length,2);
  await page.evaluate(raw=>localStorage.setItem('rog_match',raw),raw2);
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&window.__LEAF_WORLD__);
  storage=await page.evaluate(()=>({
   raw:localStorage.getItem('rog_match'),
   oldBackup:localStorage.getItem('rog_match_invalid_backup_v1')
  }));
  assert.equal(storage.raw,raw2,'second corrupt entry must survive the next bootstrap');
  assert.equal(storage.oldBackup,raw1,'older recovery data must never be overwritten');
  await start();
  storage=await page.evaluate(()=>({
   first:localStorage.getItem('rog_match_invalid_backup_v1'),
   archives:Object.keys(localStorage).filter(k=>k.startsWith('rog_match_invalid_backup_v1_'))
    .map(k=>({key:k,raw:localStorage.getItem(k)})),
   current:JSON.parse(localStorage.getItem('rog_match'))
  }));
  assert.equal(storage.first,raw1);
  assert.ok(storage.archives.some(a=>a.raw===raw2),
   'a second corrupt save requires a NEW versioned backup instead of clobbering the first');
  assert.equal(storage.current.map,'4LEAF');
  assert.deepEqual(errors,[],'recovery should not cause uncaught browser errors');
  console.log('4LEAF INVALID SAVED MATCH RAW RECOVERY PASS '+JSON.stringify({
   engine:engine.name(),mobile,firstExact:true,secondExact:true,
   independentBackups:storage.archives.length,newGamePlayable:true}));
 }finally{await browser.close()}
})().catch(e=>{
 console.error('4LEAF INVALID SAVED MATCH RAW RECOVERY FAIL',e.stack||String(e));
 process.exit(1);
});
