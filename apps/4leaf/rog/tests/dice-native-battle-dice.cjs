'use strict';
// Source screenshot board.jpg/battle.jpg has six-sided 3D dice with REAL
// dot configurations, black pips and pink central one; old revival used
// font-dependent Unicode symbols ⚀⚁⚂ instead. The meshes below remain
// honestly classified inferred CSS, not recovered original die sprites.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const cells={
 1:[5],2:[1,9],3:[1,5,9],4:[1,3,7,9],
 5:[1,3,5,7,9],6:[1,3,4,6,7,9]
};
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const readDice=()=>page.locator('#battle-visual').evaluate(stage=>({
  sides:[...stage.querySelectorAll('.battle-visual-side')].map(side=>({
   character:side.querySelector('.battle-visual-actor')?.dataset.chessmanId,
   source:side.querySelector('.battle-visual-actor .leaf-chess-original-obs:not([hidden])')?.getAttribute('src')||
     side.querySelector('.battle-visual-actor .leaf-chess-portrait')?.getAttribute('src'),
   total:side.querySelector('.battle-visual-total')?.textContent,
   values:[...side.querySelectorAll('.battle-visual-die')].map(el=>{
    const rect=el.getBoundingClientRect(),css=getComputedStyle(el);
    return {
     eye:Number(el.dataset.eye),
     source:el.dataset.source,
     label:el.getAttribute('aria-label'),
     role:el.getAttribute('role'),
     faceText:el.textContent,
     pips:[...el.querySelectorAll('.battle-die-pip')].map(p=>({
      cell:Number(p.dataset.cell),col:getComputedStyle(p).gridColumnStart,
      row:getComputedStyle(p).gridRowStart,
      background:getComputedStyle(p).backgroundColor
     })),
     original:el.querySelector('img.battle-die-original')?.getAttribute('src')||null,
     expected:(window.ORIGINAL_LEAF_UI_FRAMES?.['1171']?.frames||[]).find(f=>f.index===Number(el.dataset.eye)-1)?.url||'manifest-missing',
     originalVisible:(()=>{const i=el.querySelector('img.battle-die-original');return !!i&&getComputedStyle(i).display!=='none'&&i.complete&&i.naturalWidth===46&&i.naturalHeight===49})(),
     frame:el.dataset.originalFrame,
     pipsHidden:[...el.querySelectorAll('.battle-die-pip')].every(p=>getComputedStyle(p).visibility==='hidden'),
     layout:css.display,
     image:css.backgroundImage,
     size:[el.offsetWidth,el.offsetHeight],
     rotatedBounds:[Math.round(rect.width),Math.round(rect.height)]
    };
   })
  })),
  forest:getComputedStyle(document.getElementById('board-world')).backgroundImage,
  stageBG:getComputedStyle(stage).backgroundColor,
  sourcePads:stage.querySelectorAll('.battle-visual-pedestal').length
 }));
 const verify=(state,size)=>{
  assert.equal(state.sides.length,2,'real duel has exactly two independently rolled contestants');
  assert.equal(state.sourcePads,2,'real podiums and selected Genesis chessmen remain visible');
  assert.ok(state.forest.includes('/original/IMG/bgtile.png'),'true original forest remains under live dice');
  assert.equal(state.stageBG,'rgba(0, 0, 0, 0)','no static battle screenshot overlays the real game');
  let count=0;
  for(const side of state.sides){
   assert.ok(side.character?.length===4&&['original/CardData/','original/OBS/'].some(x=>(side.source||'').includes(x)),'selected Genesis chessman is rendered instead of a ChatTown avatar');
   assert.match(side.total,/^\d\d$/,'actual server-independent rolled battle score remains');
   assert.ok(side.values.length>=1,'real roll always has at least one independent die');
   for(const die of side.values){
    count++;
    assert.ok(Number.isInteger(die.eye)&&die.eye>=1&&die.eye<=6,'real rolled die has value 1..6');
    // 2026-11-01: the face is the ORIGINAL Dice/OBS.pak 1171.obs frame
    // (eye-1), colour-key corrected, same art as battle.jpg. CSS pips stay
    // in the DOM only as a hidden load-failure fallback.
    assert.equal(die.source,'original-OBS-1171-face/VERIFIED-by-pip-count');
    assert.equal(die.role,'img','every independent die face is accessible');
    assert.equal(die.label,'주사위 '+die.eye+'눈','accessible text matches actual roll');
    assert.equal(die.faceText,'','do not overlay system font Unicode die characters');
    assert.equal(die.frame,String(die.eye-1),'face frame index = pips - 1');
    assert.equal(die.original,die.expected,'face comes from the original 1171 UI manifest');
    assert.ok(die.originalVisible,'original 46x49 face is painted: '+JSON.stringify(die));
    assert.ok(die.pipsHidden,'fallback pips must not paint over the original face');
    assert.deepEqual(die.pips.map(x=>x.cell),cells[die.eye],'fallback keeps exact 3x3 pip arrangement');
    assert.deepEqual(die.size,size,'native 46x49 face (half size on phones)');

   }
  }
  assert.ok(count>=2,'both players display actual rolled dice');
 };
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_CHESSMEN?.length>50);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const originalPositions=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(x=>x.position));
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   // A GENUINE duel is resolved, rather than constructing fake screenshot
   // dice or injecting arbitrary result numbers into the UI.
   window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForSelector('#battle-visual');
  // R14: compare genuine original die sprites AFTER their fall and impact,
  // not a transient animation key. The geometric assertions are unchanged.
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice!=='rolling',null,{timeout:8000});
  const state=await readDice();
  verify(state,[46,49]);
  // DIE-04 acceptance: tie every VISIBLE original OBS face count and score
  // to the exact real party statistics used by combat(), not a screenshot,
  // fabricated test dice array, or a visual-only pixel assertion.
  const sourceOracle=await page.evaluate(()=>{
   const game=window.__ROG_TEST__,match=game.getMatch();
   const [attacker,defender]=match.players;
   const atk=game.teamStats(attacker.team),def=game.teamStats(defender.team);
   return {
    attackerDice:Math.max(1,atk.atk),
    defenderDice:Math.max(1,def.def),
    attackerBonus:(atk.int||0)+game.elementalModifier(attacker.team,'attack')+
     game.elementalModifier(attacker.team,'support'),
    defenderBonus:(def.int||0)+game.elementalModifier(defender.team,'defense')+
     game.elementalModifier(defender.team,'support'),
    effects:[attacker.effects,defender.effects]
   };
  });
  assert.equal(state.sides[0].values.length,sourceOracle.attackerDice,
   'attacker renders precisely the number of real original-rule attack dice');
  assert.equal(state.sides[1].values.length,sourceOracle.defenderDice,
   'defender renders precisely the number of real original-rule defense dice');
  for(let sideIndex=0;sideIndex<2;sideIndex++){
   const side=state.sides[sideIndex];
   const bonus=sideIndex===0?sourceOracle.attackerBonus:sourceOracle.defenderBonus;
   assert.equal(Number(side.total),side.values.reduce((sum,d)=>sum+d.eye,bonus),
    'original OBS score digits must equal the same actual dice eyes + party modifiers');
  }
  assert.deepEqual(await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(x=>x.position)),
   originalPositions,'displaying actual dice never moves real chessmen');
  await page.screenshot({path:'leaf-source-reference-physical-battle-dice.png'});
  await page.setViewportSize({width:390,height:844});
  const mobile=await readDice();
  verify(mobile,[23,25]);
  await page.screenshot({path:'leaf-source-reference-physical-battle-dice-mobile.png'});
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:8000});
  assert.ok(await page.locator('#game:not(.hidden)').isVisible(),
   'real game is still playable after closing the actual battle result');
  assert.deepEqual(errors,[],'native reconstructed die faces generate no browser errors');
  console.log('NATIVE INDEPENDENT BATTLE PIP DICE PASS',JSON.stringify({
   sourceOracle,desktop:state.sides.map(s=>({score:s.total,dice:s.values.map(x=>x.eye)})),
   mobile:mobile.sides.map(s=>({score:s.total,dice:s.values.map(x=>x.eye)}))
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE BATTLE DIE PIPS FAILED',e.stack||e);process.exit(1)});
