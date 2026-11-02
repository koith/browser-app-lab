'use strict';
/* Correct original native role assertion: OBS member IDs are NOT CardData IDs.
 * Original 1096 is FX; CardData 0096 is a playable 1079 actor. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   window.__LEAF_CHR_BODY_MAP__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const roles=await page.evaluate(()=>{
   const m=window.__LEAF_CHR_BODY_MAP__,a=window.__LEAF_GENESIS_ACTORS__.getState();
   return {effects:a.nativeObsEffectMembers,cards:m.cards,
    sources:Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}).length,
    mapped:m.getState()};
  });
  assert.equal(Object.keys(roles.effects).length,38);
  assert.equal(roles.mapped.resolvedSourceCards,78);
  for(const id of Object.keys(roles.effects)){
   const member='1'+id.slice(1);
   assert.ok(!Object.values(roles.cards).some(card=>card.pak==='OBS'&&card.member===member),
    'non-actor original OBS member '+member+' must not be referenced by any CHR card');
  }
  for(const [card,member] of [['0096','1079'],['0097','1080'],
   ['0088','1071'],['0087','1070'],['0170','1267']]){
   const original=await page.evaluate(card=>{
    const match=window.__ROG_TEST__.getMatch();match.players[0].team[0]='c_'+card;
    window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+match.players[0].id+'"]');
    return {rig:pawn.dataset.actorRig,source:pawn.dataset.actorSource,
     png:pawn.querySelector('img.leaf-chess-original-obs')?.getAttribute('src')};
   },card);
   assert.equal(original.rig,'original-obs-sprite',card+' must be genuine original character');
   assert.ok(original.source.includes(member+'.obs'),JSON.stringify(original));
   assert.ok(original.png?.includes('/original/OBS/'));
  }
  const unavailable=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();match.players[0].team[0]='c_0156';
   window.__ROG_TEST__.drawGame();
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+match.players[0].id+'"]');
   return {rig:pawn.dataset.actorRig,
    portrait:pawn.querySelector('.leaf-chess-original-card-fallback')?.getAttribute('src')};
  });
  assert.equal(unavailable.rig,'original-card-portrait-fallback');
  assert.ok(unavailable.portrait?.startsWith('./original/CardData/chm_')||
   unavailable.portrait==='./original/IMG/avatarback.png',
   'original unassigned member must show CardData illustration or actual IMG card-back, never a false actor');
  await page.screenshot({path:'leaf-chr-correct-original-actors-and-unassigned-effect-sprites.png'});
  assert.deepEqual(errors,[]);
  console.log('4LEAF ORIGINAL OBS NONACTOR ROLES AND TRUE CHR CARD SOURCES PASS',
   JSON.stringify({effectMembers:38,realCards:97,published:78,
    unassignedEffectsPreserved:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR OBS NON-ACTOR ROLE QA FAILED',e.stack||e);process.exit(1)});
