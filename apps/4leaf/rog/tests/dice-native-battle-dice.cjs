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
   character:side.querySelector('.battle-visual-actor')?.src,
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
     layout:css.display,
     image:css.backgroundImage,
     size:[Math.round(rect.width),Math.round(rect.height)]
    };
   })
  })),
  forest:getComputedStyle(document.getElementById('board-world')).backgroundImage,
  stageBG:getComputedStyle(stage).backgroundColor,
  sourcePads:stage.querySelectorAll('.battle-visual-pedestal').length
 }));
 const verify=(state,size)=>{
  assert.equal(state.sides.length,2,'real duel has exactly two independently rolled contestants');
  assert.equal(state.sourcePads,2,'real podiums and source Registry actors remain visible');
  assert.ok(state.forest.includes('/original/IMG/bgtile.png'),'true original forest remains under live dice');
  assert.equal(state.stageBG,'rgba(0, 0, 0, 0)','no static battle screenshot overlays the real game');
  let count=0;
  for(const side of state.sides){
   assert.ok(side.character?.includes('/original/Registry/sava'),'original Registry character still stands on the podium');
   assert.match(side.total,/^\d\d$/,'actual server-independent rolled battle score remains');
   assert.ok(side.values.length>=1,'real roll always has at least one independent die');
   for(const die of side.values){
    count++;
    assert.ok(Number.isInteger(die.eye)&&die.eye>=1&&die.eye<=6,'real rolled die has value 1..6');
    assert.equal(die.source,'archived-battle-photo-inferred-3d-pips','do not mislabel CSS as historical binary mesh');
    assert.equal(die.role,'img','every independent die face is accessible');
    assert.equal(die.label,'주사위 '+die.eye+'눈','accessible text matches actual roll');
    assert.equal(die.faceText,'','do not overlay system font Unicode die characters');
    assert.deepEqual(die.pips.map(x=>x.cell),cells[die.eye],'exact 3x3 physical die pip arrangement');
    for(const pip of die.pips){
     assert.equal(Number(pip.col),(pip.cell-1)%3+1,'pip is placed in correct 3D-die grid column');
     assert.equal(Number(pip.row),Math.floor((pip.cell-1)/3)+1,'pip is placed in correct physical row');
    }
    assert.equal(die.layout,'grid','independent pip geometry paints, not a text glyph');
    assert.deepEqual(die.size,[size,size],'rolled face has screenshot-sized white 3D box');
    assert.ok(die.image.includes('linear-gradient'),'real DOM shading supplies a material face, not a screenshot');
    if(die.eye===1)assert.equal(die.pips[0].background,'rgb(222, 28, 101)',
     'historic single-eye pink centre dot is visually distinct');
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
  const state=await readDice();
  verify(state,42);
  assert.deepEqual(await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(x=>x.position)),
   originalPositions,'displaying actual dice never moves real chessmen');
  await page.screenshot({path:'leaf-source-reference-physical-battle-dice.png'});
  await page.setViewportSize({width:390,height:844});
  const mobile=await readDice();
  verify(mobile,26);
  await page.screenshot({path:'leaf-source-reference-physical-battle-dice-mobile.png'});
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:8000});
  assert.ok(await page.locator('#game:not(.hidden)').isVisible(),
   'real game is still playable after closing the actual battle result');
  assert.deepEqual(errors,[],'native reconstructed die faces generate no browser errors');
  console.log('NATIVE INDEPENDENT BATTLE PIP DICE PASS',JSON.stringify({
   desktop:state.sides.map(s=>({score:s.total,dice:s.values.map(x=>x.eye)})),
   mobile:mobile.sides.map(s=>({score:s.total,dice:s.values.map(x=>x.eye)}))
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE BATTLE DIE PIPS FAILED',e.stack||e);process.exit(1)});
