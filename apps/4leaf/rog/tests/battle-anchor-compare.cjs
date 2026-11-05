'use strict';
/* Battle layout vs the archived 800x600 battle.jpg, in ORIGINAL SOURCE PIXELS
 * relative to the original winBattle-01 podium sprite (355x113).
 *
 * Reference (measured once on apps/4leaf/assets/battle.jpg):
 *   podium sprite drawn at (220,265) - template match, median |diff| 21
 *   white-pixel anchors relative to the sprite's left / top edge:
 *     left dice pair centre 24.0, right dice pair centre 273.5, dice top 75
 *     left score centre 62.0, right score centre 285.0, score top -153
 * The live DOM boxes include a 4 px outline/shadow band above the white
 * pixels, so vertical expectations are the white-pixel values minus 4.
 * This compares geometry of REAL game elements; nothing is pasted from the
 * screenshot. Desktop 800x600 only (phones use a compact layout). */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const ORIGINAL={leftDice:24.0,rightDice:273.5,diceTop:75-4,leftScore:62.0,rightScore:285.0,scoreTop:-153-4};
const TOLERANCE=3;
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,
  args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_FALL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('3');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  // Same dice as battle.jpg on the left (4 and 1), two dice on the right.
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   const teams=[['c_0046','c_0043'],['c_0078','c_0072'],['c_0050'],['c_0081']];
   m.players.forEach((p,i)=>{p.team=teams[i];p.position=5;});T.setMatch(m);
   const seq=[.55,0,.99,.99,.4,.4,.4,.4];let k=0;const R=Math.random;
   Math.random=()=>k<seq.length?seq[k++]:R();
   T.resolveBattle(m.players[0],m.players[1]);setTimeout(()=>{Math.random=R;},2000);
  });
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.nativeBattlePodium==='ready'
   &&document.querySelectorAll('#battle-visual .battle-visual-die').length>=4
   &&[...document.querySelectorAll('#battle-visual .battle-die-original')].every(i=>i.complete&&i.naturalWidth>0),
   null,{timeout:8000});
  // R14: compare genuine original die sprites AFTER their fall and impact,
  // not a transient animation key. The geometric assertions are unchanged.
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice!=='rolling',null,{timeout:8000});
  await page.waitForTimeout(400);
  const live=await page.evaluate(()=>{
   const box=e=>e.getBoundingClientRect();
   const pod=box(document.querySelector('#battle-visual .leaf-native-winbattle-podiums'));
   const scale=Math.min(pod.width,pod.height*355/113)/355;
   const left=pod.left+(pod.width-355*scale)/2,top=pod.bottom-113*scale;
   const rx=x=>(x-left)/scale,ry=y=>(y-top)/scale;
   const side=cls=>document.querySelector('#battle-visual .battle-visual-side.'+cls);
   const pair=cls=>{const d=[...side(cls).querySelectorAll('.battle-visual-die')].map(box);
    return {centre:rx((d[0].left+d.at(-1).right)/2),top:ry(d[0].top),eyes:[...side(cls).querySelectorAll('.battle-visual-die')].map(e=>Number(e.dataset.eye))};};
   const score=cls=>{const d=[...side(cls).querySelectorAll('.battle-total-digit')].map(box);
    return {centre:rx((d[0].left+d.at(-1).right)/2),top:ry(d[0].top),text:side(cls).querySelector('.battle-visual-total').textContent};};
   return {scale,podium:[pod.left,pod.top,pod.width,pod.height],
    leftDice:pair('attacker'),rightDice:pair('defender'),leftScore:score('attacker'),rightScore:score('defender'),
    scaleVar:getComputedStyle(document.getElementById('battle-visual')).getPropertyValue('--leaf-native-podium-scale').trim()};
  });
  assert.ok(Number(live.scaleVar)>0,'podium scale variable is published');
  assert.deepEqual(live.leftDice.eyes,[4,1],'left dice reproduce battle.jpg (4, 1)');
  const measured={leftDice:live.leftDice.centre,rightDice:live.rightDice.centre,diceTop:live.leftDice.top,
   leftScore:live.leftScore.centre,rightScore:live.rightScore.centre,scoreTop:live.leftScore.top};
  const rows=Object.keys(ORIGINAL).map(k=>({anchor:k,original:ORIGINAL[k],live:+measured[k].toFixed(1),
   delta:+(measured[k]-ORIGINAL[k]).toFixed(1)}));
  console.table(rows);
  for(const r of rows)assert.ok(Math.abs(r.delta)<=TOLERANCE,
   'battle anchor '+r.anchor+' must be within '+TOLERANCE+' source px of battle.jpg: '+JSON.stringify(r));
  assert.deepEqual(errors,[]);
  console.log('BATTLE ANCHORS MATCH battle.jpg',JSON.stringify({engine,rows}));
 }finally{await browser.close();}
})().catch(e=>{console.error('BATTLE ANCHOR COMPARE FAILED',e.stack||e);process.exit(1);});
