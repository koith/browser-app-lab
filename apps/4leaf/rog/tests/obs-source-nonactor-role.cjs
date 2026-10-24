'use strict';
/* Actual OBS source pixel role test. A 2002 OBS.pak member may be an attack
 * effect, HUD glyph, weapon, or die numeral, NOT a playable chessman.
 * Never pass visual FX off as an original actor by merely choosing frame0.
 */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const native=await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.getState());
  assert.equal(Object.keys(native.nativeObsEffectMembers).length,38);
  const originals=await page.evaluate(()=>Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}));
  for(const id of ['0096','0097','0098','0100','0125','0128',
    '0133','0134','0136','0137','0138','0139','0141','0142',
    '0145','0146','0147','0159','0160','0161','0163','0164','0165','0167','0170',
    '0099','0127','0130','0131','0135','0140','0143','0144',
    '0156','0158','0162','0169','0171']){
   const result=await page.evaluate(id=>{
    const match=window.__ROG_TEST__.getMatch();match.players[0].team[0]='c_'+id;
    window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const card=pawn?.querySelector('.leaf-chess-original-card-fallback');
    return {id,rig:pawn?.dataset.actorRig,role:pawn?.dataset.originalObsMemberRole,
     source:pawn?.dataset.actorSource,sourceMember:!!window.ORIGINAL_LEAF_OBS_FRAMES[id],
     card:card?.getAttribute('src'),hidden:card?.hidden,anim:pawn?.dataset.sourceAnimation};
   },id);
   assert.equal(result.sourceMember,true,'genuine effects stay archived '+id);
   assert.equal(result.rig,'original-card-portrait-fallback',
    'native '+result.role+' cannot impersonate a Genesis warrior '+id);
   assert.equal(result.hidden,false);
   assert.ok(result.card?.includes('/original/CardData/'),JSON.stringify(result));
   assert.equal(result.anim,'unavailable');
  }
  const genuine=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();match.players[0].team[0]='c_0046';
   window.__ROG_TEST__.drawGame();
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   return {rig:pawn.dataset.actorRig,source:pawn.dataset.actorSource,
    frame:pawn.dataset.actorFrame,role:pawn.dataset.originalObsMemberRole||null};
  });
  assert.equal(genuine.rig,'original-obs-sprite');
  assert.equal(genuine.frame,'25');
  assert.equal(genuine.role,null);
  await page.screenshot({path:'leaf-real-chessman-vs-original-obs-hud-effects.png'});
  assert.deepEqual(errors,[]);
  console.log('SOURCE OBS PIXEL ROLE QA PASS '+JSON.stringify({
   nativeOriginalSourceMembers:originals.length,
   visuallyReviewedNonActors:Object.keys(native.nativeObsEffectMembers).length,
   realChessman:genuine}));
 }finally{await browser.close()}
})().catch(e=>{console.error('OBS SOURCE EFFECT ROLE QA FAILED',e.stack||e);process.exitCode=1});
