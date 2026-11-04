'use strict';
/* Browser QA: preserve 63 source-coordinate trailer frames as evidence,
 * but NEVER render their misdecoded per-block palettes in a live roll.
 * The older verified UI dice must remain usable and gameplay unchanged.
 */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_FALL__&&window.ORIGINAL_LEAF_EMBEDDED_DICE);
  const originals=await page.evaluate(()=>{
   const fall=window.__LEAF_DICE_FALL__,d6=fall.originalEmbeddedDice(6),d4=fall.originalEmbeddedDice(4);
   const s=fall.getState();
   return {d6:d6?.frames.length,d4:d4?.frames.length,
    chains6:d6?.chains,chains4:d4?.chains,
    faceCountD6:fall.originalD6()?.faces.length,
    faceCountD4:fall.originalD4()?.faces.length,
    allNative:s.nativeEmbeddedPrefetchCount,
    playable6:s.nativeEmbeddedPlayableD6Frames,
    playable4:s.nativeEmbeddedPlayableD4Frames,
    paletteStatus:s.nativeEmbeddedPaletteStatus,
    explicitStatus:s.nativeEmbeddedRole,
    d6Manifest:window.ORIGINAL_LEAF_EMBEDDED_DICE['obs-1171-c1']?.frames.length,
    d4Manifest:window.ORIGINAL_LEAF_EMBEDDED_DICE['obs-1223-c1']?.frames.length
   };
  });
  assert.deepEqual([originals.d6,originals.d4],[38,25],'63 genuine quarantined native trailer frames');
  assert.deepEqual(originals.chains6,['obs-1171-c0','obs-1171-c1','obs-1171-c2']);
  assert.deepEqual(originals.chains4,['obs-1223-c0','obs-1223-c1']);
  assert.deepEqual([originals.faceCountD6,originals.faceCountD4],[6,4],
   'old independently verified final game faces preserved');
  assert.equal(originals.d6Manifest,16);assert.equal(originals.d4Manifest,16);
  assert.match(originals.explicitStatus,/palette-UNVERIFIED/);
  assert.match(originals.paletteStatus,/QUARANTINED/);
  assert.deepEqual([originals.playable6,originals.playable4,originals.allNative],[0,0,0],
   'all miscoloured additional frames must remain off the live rendering path');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const matchBefore=await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch()));
  const run=async(sides,result)=>{
   const promise=page.evaluate(({sides,result})=>
    window.__LEAF_DICE_FALL__.roll([result],{sides}),{sides,result});
   await page.waitForFunction((n)=>{
    const p=document.querySelector('#leaf-dice-fall-layer .leaf-fall-piece');
    return p?.dataset.sides===String(n)&&p?.dataset.embeddedSourceChains==='';
   },sides,{timeout:10000});
   const during=await page.evaluate(()=>{
    const p=document.querySelector('.leaf-fall-piece'),img=p?.querySelector('img');
    return {chains:p?.dataset.embeddedSourceChains,
     status:p?.dataset.tumbleSource,role:p?.dataset.nativeSourceRole,
     source:img?.dataset.sourceChain,url:img?.getAttribute('src'),
     visible:p?.classList.contains('leaf-fall-original')};
   });
   assert.ok(during.visible,'previously verified UI OBS image must render in the die');
   assert.equal(during.chains,'','miscoloured additional source chains must not be live');
   assert.match(during.status,/index-ordered-INFERRED|partial-/);
   assert.match(during.role,/landing-faces-VERIFIED/);
   assert.ok(during.url?.startsWith('./original/OBS/ui/'),
    'only verified original UI dice frames are allowed, not embedded: '+during.url);
   assert.ok(['original-UI-OBS','OBS-1171-b0','OBS-1223-b0'].includes(during.source),during.source);
   assert.deepEqual(await promise,[result],'fall presentation may not alter input gameplay eyes');
   const state=await page.evaluate(()=>window.__LEAF_DICE_FALL__.getState());
   assert.deepEqual(state.last,[result]);assert.deepEqual(state.lastSides,[sides]);
  };
  await run(6,3);
  await page.setViewportSize({width:390,height:844});
  await run(4,2);
  const matchAfter=await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch()));
  assert.equal(matchAfter,matchBefore,'source die presentation must not modify match, RNG or turns');
  // Missing embedded archive must retain previously shipped original art.
  await page.evaluate(()=>{window.ORIGINAL_LEAF_EMBEDDED_DICE=null;});
  const fallback=await page.evaluate(()=>({
   d6:window.__LEAF_DICE_FALL__.originalEmbeddedDice(6),
   d4:window.__LEAF_DICE_FALL__.originalEmbeddedDice(4),
   face6:window.__LEAF_DICE_FALL__.originalD6()?.faces.length,
   face4:window.__LEAF_DICE_FALL__.originalD4()?.faces.length
  }));
  assert.equal(fallback.d6,null);assert.equal(fallback.d4,null);
  assert.deepEqual([fallback.face6,fallback.face4],[6,4]);
  assert.deepEqual(errors,[],'no browser runtime errors');
  console.log('DICE_EMBEDDED_WRONG_PALETTE_QUARANTINE_BROWSER_PASS '+JSON.stringify({
   browser:engine===webkit?'webkit':'chromium',archivedUnapprovedPixels:63,
   liveUnapprovedPixels:0,originalFinalFaceCounts:[6,4],realMatchUnchanged:true,
   previousOriginalUiSpritesRetained:true,webSequenceInferred:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error('DICE_EMBEDDED_NATIVE_BROWSER_FAILED',e.stack||e);process.exit(1)});
