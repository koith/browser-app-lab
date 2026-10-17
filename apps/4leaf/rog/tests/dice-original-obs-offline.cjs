'use strict';
/* Cold-install PWA test: authentic OBS body frames must work offline even
 * if the player never visited the Dice game while connected.
 * Source sprites are downloaded on install, NOT synthesized in CSS.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'allow'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_PWA__?.getState().registered===true,
   null,{timeout:15000});
  await page.evaluate(()=>navigator.serviceWorker.ready);
  // This is before entering the original Dice lobby: every authentic
  // source frame must already be install-cached for a cold offline visit.
  await page.waitForFunction(async()=>{
   const keys=(await caches.keys()).filter(x=>x.startsWith('4leaf-revival-pwa-v'));
   if(!keys.length)return false;
   const cache=await caches.open(keys[keys.length-1]);
   const manifest=window.ORIGINAL_LEAF_OBS_FRAMES||{};
   const urls=Object.values(manifest).flatMap(x=>(x.frames||[]).map(f=>f.url));
   if(Object.keys(manifest).length<46||urls.length<242)return false;
   const matches=await Promise.all(urls.map(url=>cache.match(url)));
   return matches.every(Boolean);
  },null,{timeout:90000,polling:650});
  const online=await page.evaluate(async()=>{
    const keys=(await caches.keys()).filter(x=>x.startsWith('4leaf-revival-pwa-v'));
    const cache=await caches.open(keys[keys.length-1]);
    const frames=Object.values(window.ORIGINAL_LEAF_OBS_FRAMES).flatMap(x=>x.frames);
    return {revision:keys[keys.length-1],actors:Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES).length,
      frames:frames.length,assets:(await Promise.all(frames.map(f=>cache.match(f.url)))).filter(Boolean).length};
  });
  await page.reload();
  await page.waitForFunction(()=>!!navigator.serviceWorker.controller,null,{timeout:16000});
  await context.setOffline(true);
  await page.reload({waitUntil:'domcontentloaded',timeout:18000});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_OBS_FRAMES?.['0043'],
   null,{timeout:18000});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0043';
   m.players[1].team[0]='c_0054';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#board-pawns .leaf-chess-original-obs')].length===2&&[...document.querySelectorAll(
   '#board-pawns .leaf-chess-original-obs')].every(x=>x.complete&&x.naturalWidth>20),
   null,{timeout:18000});
  const cached=await page.evaluate(()=>({
   tiles:document.querySelectorAll('#board-nodes .tile').length,
   actors:[...document.querySelectorAll('#board-pawns .board-pawn')].map(x=>({
     id:x.dataset.chessmanId,rig:x.dataset.actorRig,
     source:x.querySelector('.leaf-chess-original-obs')?.getAttribute('src')
   }))
  }));
  assert.equal(cached.tiles,104);
  assert.deepEqual(cached.actors.map(x=>x.id),['0043','0054']);
  assert.ok(cached.actors.every(x=>x.rig==='original-obs-sprite'&&x.source?.includes('/OBS/bulk/')));
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().lastRoll?.length>0,
   null,{timeout:20000});
  await page.screenshot({path:'leaf-original-obs-fully-offline.png'});
  assert.deepEqual(errors,[],'cold offline actor animation does not throw runtime errors');
  console.log('COLD OFFLINE NATIVE OBS CHESSMEN PASS '+JSON.stringify({online,cached}));
 }finally{await browser.close()}
})().catch(e=>{console.error('COLD OFFLINE NATIVE OBS FAILED',e.stack||e);process.exit(1)});
