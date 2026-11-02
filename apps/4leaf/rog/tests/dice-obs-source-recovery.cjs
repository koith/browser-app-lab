'use strict';
/* FL-09/10 source-resource availability E2E. Full-body OBS graphics come ONLY
 * from original extracted PNG files; failures may never invent fake actors.
 * Historical action-to-frame mapping and 34 missing actors remain unverified.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 let failures0045=0,failures0042=0;
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.route('**/original/OBS/action-full-ext/1045-18.png*',async route=>{
   if(failures0045++<2)await route.fulfill({status:503,body:'transient original OBS source'});
   else await route.continue();
  });
  await page.route('**/original/OBS/action-full-ext/1042-22.png*',async route=>{
   failures0042++;
   await route.fulfill({status:503,body:'offline original OBS source'});
  });
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const players=window.__ROG_TEST__.getMatch().players;
   players[0].team[0]='c_0062';players[1].team[0]='c_0059';
   window.__ROG_TEST__.drawGame();
  });
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(p=>({
   id:p.id,position:p.position,team:p.team[0]
  })));
  // The first genuine OBS asset was temporarily unavailable twice,
  // but should load its OWN SHA-authenticated original bytes after retry.
  await page.waitForFunction(()=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="0045"]');
   const img=p?.querySelector('.leaf-chess-original-obs');
   return p?.dataset.actorSourceLoad==='ready'&&img?.complete&&img.naturalWidth>20;
  },null,{timeout:18000});
  assert.ok(failures0045>=3,'original OBS source must retry after transient HTTP errors');
  const restored=await page.evaluate(()=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="0045"]');
   const img=p.querySelector('.leaf-chess-original-obs');
   return {rig:p.dataset.actorRig,source:p.dataset.actorSource,
    load:p.dataset.actorSourceLoad,original:p.dataset.actorOriginalModelRecovered,
    path:img.getAttribute('src'),native:[img.naturalWidth,img.naturalHeight],
    missing:p.dataset.obsUnavailable};
  });
  assert.equal(restored.rig,'original-obs-sprite');
  assert.equal(restored.source,'OBS/OBS.pak/1045.obs');
  assert.equal(restored.original,'true');
  assert.ok(restored.path.startsWith('./original/OBS/action-full-ext/1045-18.png'));
  assert.ok(restored.native[0]>20&&restored.native[1]>50);
  assert.equal(restored.missing,undefined);

  // If the new 0042 full-source image is unreachable, retain an older
  // original OBS body as fallback. Do NOT drop to a CardData portrait.
  // Once reconnected, retry the full original extended series.
  await page.waitForFunction(()=>document.querySelector(
   '#board-pawns .board-pawn[data-chessman-id="0042"]')?.dataset.sourceFullUnavailable==='true',
   null,{timeout:22000});
  const unavailable=await page.evaluate(()=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="0042"]');
   return {rig:p.dataset.actorRig,source:p.dataset.actorSource,
    load:p.dataset.actorSourceLoad,cardVisible:!!p.querySelector('.leaf-chess-original-card-fallback:not([hidden])'),
    legacy:p.querySelector('img.leaf-chess-original-obs')?.getAttribute('src')};
  });
  assert.equal(unavailable.rig,'original-obs-sprite');
  assert.ok(unavailable.legacy.includes('./original/OBS/1042-25.png'));
  assert.equal(unavailable.cardVisible,false);
  assert.ok(failures0042>=1,'the extended source must be attempted before authentic legacy fallback');
  await page.unroute('**/original/OBS/action-full-ext/1042-22.png*');
  await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.recoverAvailableOriginals());
  await page.waitForFunction(()=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="0042"]');
   const img=p?.querySelector('.leaf-chess-original-obs');
   return p?.dataset.actorSourceLoad==='ready'&&p.dataset.sourceFullUnavailable!== 'true'&&
    img?.getAttribute('src')?.includes('action-full-ext/1042-22.png')&&p.dataset.actorRig==='original-obs-sprite'&&
    p.dataset.actorOriginalModelRecovered==='true'&&img?.naturalWidth>20&&!img.hidden;
  },null,{timeout:15000});
  const after=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(p=>({
   id:p.id,position:p.position,team:p.team[0]
  })));
  assert.deepEqual(after,before,'recovering original OBS art must not change turns, team or DMP location');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-real-obs-reconnect-original-full-body.png'});
  console.log('AUTHENTIC OBS SOURCE RETRY / RECONNECT PASS '+JSON.stringify({
   fail0045:failures0045,fail0042:failures0042,restored,unavailable,
   after,source:'real OBS PNG only; 6 native models still missing'
  }));
 }finally{await browser.close()}
})().catch(error=>{console.error('ORIGINAL OBS SOURCE RECOVERY FAILED',error.stack||error);process.exit(1)});
