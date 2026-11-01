'use strict';
/* Reliable source fallback, not a fake chessman:
 * when full 37-frame PNGs are blocked/offline, retain an authenticated
 * previous original OBS body frame and authoritative game state.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const path=require('node:path');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 let denied=0;
 await page.route(/\/original\/OBS\/action-full\/1043-\d+\.png(?:\?|$)/,
  route=>{denied++;return route.abort('failed')});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
   window.ORIGINAL_LEAF_FULL_ACTION_FRAMES?.['0043']?.frames.length===37&&
   window.ORIGINAL_LEAF_OBS_FRAMES?.['0043']?.frames?.length>0);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const start=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team=['c_0043'];
   window.__ROG_TEST__.setMatch(m);
   return {id:m.players[0].id,active:m.active,position:m.players[0].position};
  });
  await page.waitForFunction(id=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=p?.querySelector('img.leaf-chess-original-obs');
   return p?.dataset.sourceFullUnavailable==='true'&&img?.complete&&img?.naturalWidth>15&&
    img.getAttribute('src')?.includes('/original/OBS/bulk/');
  },start.id,{timeout:16000});
  const after=await page.evaluate(id=>{
   const m=window.__ROG_TEST__.getMatch();
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=pawn.querySelector('img.leaf-chess-original-obs');
   return {id:pawn.dataset.chessmanId,rig:pawn.dataset.actorRig,
    originalRecovered:pawn.dataset.actorOriginalModelRecovered,
    unavailable:pawn.dataset.obsUnavailable||null,
    fullUnavailable:pawn.dataset.sourceFullUnavailable,
    src:img.getAttribute('src'),pixels:[img.naturalWidth,img.naturalHeight],
    active:m.active,position:m.players[0].position};
  },start.id);
  assert.ok(denied>=1,'test must actually reject the new full-frame original files');
  assert.equal(after.id,'0043');
  assert.equal(after.rig,'original-obs-sprite');
  assert.equal(after.originalRecovered,'true');
  assert.equal(after.unavailable,null);
  assert.equal(after.fullUnavailable,'true');
  assert.ok(after.src.startsWith('./original/OBS/bulk/1043-'),
    'source is the earlier verified OBS body and never an invented proxy');
  assert.ok(after.pixels[0]>20&&after.pixels[1]>20);
  assert.deepEqual({active:after.active,position:after.position},
   {active:start.active,position:start.position});
  // Reuse the SAME DOM pawn so a failed 1043 full-source load cannot
  // poison an unrelated recovered 1046 member through a stale flag.
  const switchResult=await page.evaluate(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const portrait=pawn.querySelector('img.leaf-chess-portrait').getAttribute('src');
   window.__LEAF_GENESIS_ACTORS__.mount(pawn,{team:['c_0046']},portrait);
   return {samePawn:pawn.dataset.id===id,flag:pawn.dataset.sourceFullUnavailable||null};
  },start.id);
  assert.equal(switchResult.samePawn,true);
  assert.equal(switchResult.flag,null,'a fresh actor cannot inherit another full-source failure');
  await page.waitForFunction(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=pawn?.querySelector('img.leaf-chess-original-obs');
   return pawn?.dataset.chessmanId==='0046'&&
    pawn.dataset.sourceFullUnavailable!=='true'&&img?.complete&&img?.naturalWidth>15&&
    img.getAttribute('src')?.includes('/original/OBS/action-full/1046-');
  },start.id,{timeout:16000});
  // Reproduce a real second 1043 failure before testing online recovery.
  await page.evaluate(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const portrait=pawn.querySelector('img.leaf-chess-portrait').getAttribute('src');
   window.__LEAF_GENESIS_ACTORS__.mount(pawn,{team:['c_0043']},portrait);
  },start.id);
  await page.waitForFunction(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=pawn?.querySelector('img.leaf-chess-original-obs');
   return pawn?.dataset.sourceFullUnavailable==='true'&&img?.complete&&
    img.naturalWidth>15&&img.getAttribute('src')?.includes('/original/OBS/bulk/');
  },start.id,{timeout:16000});
  // Network reconnect (or the app's explicit recovery API) must promote the
  // genuine 37-frame original again without changing the match engine.
  await page.unroute(/\/original\/OBS\/action-full\/1043-\d+\.png(?:\?|$)/);
  await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.recoverAvailableOriginals());
  await page.waitForFunction(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=pawn?.querySelector('img.leaf-chess-original-obs');
   return pawn?.dataset.sourceFullUnavailable!=='true'&&
    pawn?.dataset.actorSourceLoad==='ready'&&img?.complete&&img?.naturalWidth>15&&
    img.getAttribute('src')?.includes('/original/OBS/action-full/1043-');
  },start.id,{timeout:16000});
  const restored=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {active:m.active,position:m.players[0].position,team:m.players[0].team.slice()};
  });
  assert.deepEqual(restored,{active:start.active,position:start.position,
   team:['c_0043']},'original-asset recovery does not mutate authoritative game state');
  assert.deepEqual(errors,[],'no JS runtime errors during original asset failure, swap or recovery');
  console.log('4LEAF FULL OBS OFFLINE ORIGINAL SOURCE FALLBACK PASS',
   JSON.stringify({engine,denied,after}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF FULL OBS OFFLINE FALLBACK FAILED',e.stack||e);process.exit(1)});
