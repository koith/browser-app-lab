'use strict';
// Four genuine playable duels: native podium outcome, no premature
// defender hurt, winner/loser state, retreat by score and turn preserved.
// Source slot 13/14 source keys/ticks VERIFIED, roles hurt/victory WEB-INFERRED.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const evidence=[];
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   Object.keys(window.ORIGINAL_LEAF_FULL_ACTION_FRAMES||{}).length===45);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  for(const pair of [['0056','0063'],['0078','0088'],['0091','0087'],['0060','0081']]){
   const before=await page.evaluate(([a,b])=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+a];m.players[1].team=['c_'+b];
    m.players.forEach(p=>{p.position=20;p.effects={};p.items=[]});
    T.setMatch(m);
    window.__round4Battle=T.resolveBattle(m.players[0],m.players[1],false);
    return {turn:m.active};
   },pair);
   await page.waitForSelector('#battle-visual .leaf-battle-chessman');
   const initial=await page.evaluate(()=>{
    const stage=document.getElementById('battle-visual');
    return {def:stage.querySelector('.battle-visual-side.defender .leaf-battle-chessman')?.dataset.actorPose,
     totals:[...stage.querySelectorAll('.battle-visual-total')].map(x=>Number(x.textContent)),
     stage:stage.dataset.duelOutcome};
   });
   assert.equal(initial.def,'idle','defender must not get hurt before result');
   assert.equal(initial.totals.length,2);
   const win=initial.totals[0]>initial.totals[1];
   assert.equal(initial.stage,win?'attacker-wins':'defender-wins');
   await page.waitForFunction(()=>[...document.querySelectorAll('#battle-visual .leaf-battle-chessman')]
    .some(x=>x.dataset.duelResult),null,{timeout:8000});
   const actors=await page.evaluate(()=>[...document.querySelectorAll('#battle-visual .leaf-battle-chessman')]
    .map(x=>({side:x.dataset.duelSide,result:x.dataset.duelResult,pose:x.dataset.actorPose,
     source:x.dataset.sourceOutcomeEvidence})));
   assert.equal(actors.length,2);
   for(const a of actors){
    const w=(a.side==='attacker')===win;
    assert.equal(a.result,w?'win':'lose');
    assert.equal(a.pose,w?'victory':'hurt');
    assert.ok(a.source===undefined||
      /(?:original-OBS-anim(?:13|14)-keys-and-ticks-VERIFIED\/outcome-role-and-WEB-tick-ms-INFERRED|no-original-.*-UNVERIFIED)$/.test(a.source),
      'original frame/tick source is VERIFIED, but inferred EXE outcome role must never be presented as verified');
   }
   await page.locator('.leaf-native-battle-actions button, #modal-buttons button',
    {hasText:'결과 확인'}).first().click();
   const end=await page.evaluate(()=>{
    const m=window.__ROG_TEST__.getMatch();
    return {stage:!!document.getElementById('battle-visual'),
     tray:!!document.querySelector('.leaf-native-battle-actions'),
     active:m.active,position:m.players.map(p=>p.position),
     poses:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>p.dataset.actorPose)};
   });
   assert.equal(end.stage,false);
   assert.equal(end.tray,false);
   const diff=Math.abs(initial.totals[0]-initial.totals[1]);
   assert.equal(end.position[win?1:0],diff>=7?0:Math.max(0,20-diff));
   assert.equal(end.position[win?0:1],20);
   assert.equal(end.active,before.turn);
   assert.ok(end.poses.includes('victory')&&end.poses.includes('hurt'));
   await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .board-pawn')]
    .every(p=>p.dataset.actorPose==='idle'),null,{timeout:5000});
   evidence.push({pair,totals:initial.totals,stage:initial.stage,after:end.position});
  }
  assert.deepEqual(errors,[]);
  console.log('ROUND4 ORIGINAL BATTLE OUTCOME RETURN PASS',JSON.stringify(evidence));
 }finally{await browser.close();}
})().catch(e=>{console.error('ROUND4 BATTLE FAILED',e.stack||e);process.exit(1)});
