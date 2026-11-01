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
  assert.deepEqual(errors,[],'no JavaScript runtime errors in offline fallback');
  console.log('4LEAF FULL OBS OFFLINE ORIGINAL SOURCE FALLBACK PASS',
   JSON.stringify({engine,denied,after}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF FULL OBS OFFLINE FALLBACK FAILED',e.stack||e);process.exit(1)});
