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
  // Original 363x133 Dead or Alive image must appear ONLY after the
  // REAL source DMP DOA random decision; do not replace the real dice
  // values / teleport / backward movement with image-only screen state.
  await page.evaluate(async()=>{
   const match=window.__ROG_TEST__.getMatch(),player=match.players[0];
   match.players[1].position=20;player.position=11;
   match.tiles[11]='doa';
   await window.__ROG_TEST__.resolveTile(player);
  });
  await page.waitForFunction(()=>document.querySelector(
   '#leaf-source-effect-overlay')?.dataset.nativeSourceReady==='ready'&&
   document.querySelector('#leaf-source-effect-overlay')?.dataset.sourceKind==='doa',
    null,{timeout:10000});
  const doa=await page.evaluate(()=>{
   const stage=document.querySelector('#leaf-source-effect-overlay');
   const image=stage.querySelector('.leaf-source-event-primary');
   return {member:stage.dataset.originalMember,
    size:[image.naturalWidth,image.naturalHeight],
    src:image.getAttribute('src'),
    source:stage.dataset.sourceLayout,
    pos:window.__ROG_TEST__.getMatch().players[0].position,
    totalDmpCells:window.__ROG_TEST__.getMatch().tiles.length,
    passThrough:getComputedStyle(stage).pointerEvents};
  });
  assert.equal(doa.member,'Dice/IMG.pak:winDoa.spr');
  assert.deepEqual(doa.size,[363,133]);
  assert.deepEqual([source.sprites['winDoa.spr'].frames[0].width,
   source.sprites['winDoa.spr'].frames[0].height],doa.size);
  assert.ok(doa.pos>=0&&doa.pos<=11,'real source DOA random setback still controls gameplay');
  assert.equal(doa.totalDmpCells,104);
  assert.equal(doa.passThrough,'none','original DOA art never blocks the ROLL UI');
  await page.screenshot({path:'leaf-native-source-dead-or-alive-live.png'});
  // A real completed original DMP match must use genuine winResult.spr
  // 452x88 header and *actual* reward/percentage/player rows, not a
  // photographic overlay or manufactured CL / lifetime win-rate numbers.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].position=m.tiles.length-1;
   m.startedAt=Date.now()-200000;
   window.__ROG_TEST__.finishGame(m.players[0]);
  });
  await page.waitForFunction(()=>{
   const panel=document.querySelector('#leaf-original-match-result');
   return panel?.dataset.nativeResult==='ready';
  },null,{timeout:10000});
  const finished=await page.evaluate(()=>{
   const panel=document.querySelector('#leaf-original-match-result');
   const image=panel.querySelector('.leaf-original-result-heading');
   const m=window.__ROG_TEST__.getMatch();
   const rows=[...panel.querySelectorAll('tbody tr')];
   return {member:panel.dataset.originalMember,frame:panel.dataset.originalFrame,
    size:[image.naturalWidth,image.naturalHeight],
    winner:m.winner,finished:m.finished,
    rows:rows.map(row=>({
     playerId:Number(row.dataset.playerId),
     name:row.querySelector('[data-col="player"]')?.textContent,
     cl:row.querySelector('[data-col="cl"]')?.textContent,
     complete:row.querySelector('[data-col="complete"]')?.textContent,
     gp:row.querySelector('[data-col="gp"]')?.textContent,
     rate:row.querySelector('[data-col="win-rate"]')?.textContent,
     winner:row.classList.contains('leaf-original-result-winner')
    })),
    buttons:[...document.querySelectorAll('#modal-buttons button')].map(b=>b.textContent)
   };
  });
  assert.equal(finished.member,'Dice/IMG.pak:winResult.spr');
  assert.equal(finished.frame,'0');
  assert.deepEqual(finished.size,[452,88]);
  assert.deepEqual([source.sprites['winResult.spr'].frames[0].width,
   source.sprites['winResult.spr'].frames[0].height],finished.size);
  assert.equal(finished.finished,true);
  assert.equal(finished.winner,0);
  assert.equal(finished.rows.length,2);
  assert.equal(finished.rows[0].winner,true);
  assert.equal(finished.rows[0].complete,'100%');
  assert.ok(Number(finished.rows[0].gp)>0,'source result uses actual earned GP, not a fixed original-looking fake');
  assert.ok(finished.rows.every(r=>r.cl==='—'&&r.rate==='—'),
   'historic CL and lifetime win-rate remain explicitly unavailable rather than invented');
  assert.ok(finished.buttons.includes('다시 시작'),'real match post-game UI stays interactive');
  await page.screenshot({path:'leaf-native-source-match-result-live.png'});
  assert.deepEqual(errors,[]);
  console.log('4LEAF REAL SOURCE IMG JAIL/ABILITY/DOA/RESULT EFFECTS PASS',
   JSON.stringify({jail,ability,doa,result:finished}));
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE IMG EVENT E2E FAILED',e.stack||e);process.exit(1)});
