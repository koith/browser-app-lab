'use strict';
/* Exercise REAL player movement landing logic and source 2002 original
 * winJail.spr / winAbility.spr PNG art. Do not claim original timing or MVE.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block'});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__?.resolveTile&&window.__LEAF_NATIVE_EVENTS__&&
   window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const source=await page.evaluate(async()=>await (await fetch('./original/SourceSPRExtra/manifest.json')).json());
  assert.equal(source.classifiedNative2DOnly,true,'source is 2D original IMG GUI, not a false MVE model');
  const activation=async(type,ability)=>{
   await page.evaluate(async({type,ability})=>{
    const m=window.__ROG_TEST__.getMatch(),player=m.players[0];
    // A deterministic real source DMP tile landing, not a fake
    // standalone render call: the game engine must change player state.
    player.position=5;player.ability=ability;
    m.tiles[5]=type;
    await window.__ROG_TEST__.resolveTile(player);
   },{type,ability});
   await page.waitForFunction(()=>{
    const node=document.querySelector('#leaf-source-effect-overlay');
    if(node?.dataset.nativeSourceReady!=='ready')return false;
    const parts=[...node.querySelectorAll('.leaf-source-ability-token')];
    return parts.every(img=>img.complete&&img.naturalWidth===41&&img.naturalHeight===29);
   },null,{timeout:10000});
   return page.evaluate(()=>{
    const stage=document.querySelector('#leaf-source-effect-overlay'),
     img=stage.querySelector('.leaf-source-event-primary');
    const badges=[...stage.querySelectorAll('.leaf-source-ability-token')];
    const m=window.__ROG_TEST__.getMatch();
    const style=getComputedStyle(stage);
    return {kind:stage.dataset.sourceKind,
     name:stage.dataset.originalMember,
     layout:stage.dataset.sourceLayout,
     ready:stage.dataset.nativeSourceReady,
     size:[img.naturalWidth,img.naturalHeight],
     src:img.getAttribute('src'),
     badgeSizes:badges.map(e=>[e.naturalWidth,e.naturalHeight]),
     badgePositions:badges.map(e=>[Number.parseInt(e.style.left),Number.parseInt(e.style.top)]),
     passThrough:style.pointerEvents,
     player:{jail:m.players[0].jail,ability:m.players[0].ability,position:m.players[0].position}
    };
   });
  };
  const jail=await activation('prison',0);
  assert.equal(jail.kind,'jail');
  assert.equal(jail.name,'Dice/IMG.pak:winJail.spr');
  assert.deepEqual(jail.size,[136,219]);
  assert.equal(jail.badgeSizes.length,0);
  assert.equal(jail.player.jail,3,'game engine real jail sentence remains 3');
  assert.equal(jail.passThrough,'none','source event pixels cannot steal source roll and pawn clicks');
  assert.equal(jail.ready,'ready');
  await page.screenshot({path:'leaf-native-source-jail-live.png'});
  const ability=await activation('ability',75);
  assert.equal(ability.kind,'ability');
  assert.equal(ability.name,'Dice/IMG.pak:winAbility.spr');
  assert.deepEqual(ability.size,[330,284]);
  assert.equal(ability.player.ability,100,'only a REAL 75->100 ability gauge event triggers this');
  assert.equal(ability.player.position,5);
  assert.deepEqual(ability.badgeSizes,Array.from({length:5},()=>[41,29]));
  assert.deepEqual(ability.badgePositions,[[35,287],[65,326],[146,340],[226,326],[256,287]],
   'frame positions are determined by genuine signed IMG SPR x/y origins');
  assert.match(ability.layout,/inferred-signed-SPR-origin/);
  assert.equal(ability.passThrough,'none');
  assert.deepEqual([source.sprites['winAbility.spr'].frames[0].width,
   source.sprites['winAbility.spr'].frames[0].height],ability.size);
  assert.deepEqual([source.sprites['winJail.spr'].frames[0].width,
   source.sprites['winJail.spr'].frames[0].height],jail.size);
  await page.screenshot({path:'leaf-native-source-ability-live.png'});
  await page.evaluate(()=>window.__LEAF_NATIVE_EVENTS__.show('jail','test'));
  await page.waitForTimeout(2450);
  assert.equal(await page.locator('#leaf-source-effect-overlay').count(),0,
   'original pixel overlay is temporary; never replace actual playable game viewport');
  assert.deepEqual(errors,[]);
  console.log('4LEAF REAL SOURCE IMG JAIL/ABILITY EFFECTS PASS',
   JSON.stringify({jail,ability}));
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE IMG EVENT E2E FAILED',e.stack||e);process.exit(1)});
