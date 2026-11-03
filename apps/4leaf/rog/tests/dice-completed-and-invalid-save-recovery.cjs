'use strict';
/* The existing boot path used to erase both finished games and structurally
 * broken (but valid JSON) matches. Use genuine ROOM READY to create a match,
 * then seed separate real localStorage scenarios and verify exact recovery
 * snapshots before starting the next game. No fake gameplay success claimed.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const mobile=process.env.FOURLEAF_MOBILE==='1';
(async()=>{
 const browser=await browserType.launch({headless:true,...(browserType===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'
 });
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const click=locator=>mobile?locator.tap():locator.click();
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const create=async()=>{
  await page.locator('.world-location[data-region="dice"]').waitFor();
  await click(page.locator('.world-location[data-region="dice"]'));
  await click(page.locator('#dice-channels [data-channel="ispin:1"]'));
  await click(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#point-limit').selectOption('12');
  await click(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
 };
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&window.__LEAF_WORLD__);
  await create();
  const completedRaw=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.finished=true;m.winner=0;m.round=4;m.history.push('FINISHED-MATCH-HISTORY-PRESERVE');
   const text=JSON.stringify(m);
   localStorage.setItem('rog_match',text);
   return text;
  });
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_WORLD__);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch()),null,
   'completed match should not be treated as ongoing');
  assert.equal(await page.evaluate(()=>localStorage.getItem('rog_match')),completedRaw,
   'visiting the app must not wipe a finished match or its history');
  assert.equal(await page.evaluate(()=>localStorage.getItem('rog_match_finished_backup_v1')),null,
   'no recovery copy is needed until the user starts another game');
  await create();
  const finished=await page.evaluate(()=>({
   backup:localStorage.getItem('rog_match_finished_backup_v1'),
   current:JSON.parse(localStorage.getItem('rog_match'))
  }));
  assert.equal(finished.backup,completedRaw,
   'committing new game preserves finished-match raw bytes before replacement');
  assert.equal(finished.current.finished,false,'replacement starts a genuinely playable new match');
  assert.equal(finished.current.round,1);
  // A syntactically valid but incomplete record is also unsafe to mount.
  // Profile/bootstrap rendering must never turn this exact raw JSON to null.
  const broken=JSON.stringify({version:5,map:'4LEAF',mode:'hotseat',
   tiles:['start','goal'],players:[null,{id:1,name:'other'}],
   active:0,round:3,finished:false,history:['UNRECOVERABLE-SHAPE']});
  await page.evaluate(raw=>localStorage.setItem('rog_match',raw),broken);
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_WORLD__);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch()),null,
   'incomplete player objects must never be promoted into live engine state');
  assert.equal(await page.evaluate(()=>localStorage.getItem('rog_match')),broken,
   'bootstrap preserves exact valid JSON that is unsafe for live play');
  await create();
  const restored=await page.evaluate(()=>({
   invalidBackup:localStorage.getItem('rog_match_invalid_backup_v1'),
   completedBackup:localStorage.getItem('rog_match_finished_backup_v1'),
   current:JSON.parse(localStorage.getItem('rog_match'))
  }));
  assert.equal(restored.invalidBackup,broken,
   'new game preserves semantically broken saved JSON without erasing it');
  assert.equal(restored.completedBackup,completedRaw,
   'later recovery must not overwrite an older completed-game snapshot');
  assert.equal(restored.current.map,'4LEAF');
  assert.equal(restored.current.players.length,2);
  assert.equal(restored.current.finished,false);
  assert.deepEqual(errors,[],'no uncaught runtime exception');
  console.log('4LEAF COMPLETED + STRUCTURALLY INVALID SAVE PRESERVATION PASS '+
   JSON.stringify({browser:browserType.name(),mobile,finishedRetained:true,
    completedBackup:true,invalidShapeRetained:true,invalidBackup:true,newMatchPlayable:true}));
 }finally{await browser.close()}
})().catch(e=>{
 console.error('4LEAF COMPLETED + STRUCTURALLY INVALID SAVE PRESERVATION FAIL',
  e.stack||String(e));process.exit(1);
});
