'use strict';
/* Direct historical screenshot-grounded combat replay:
 * "주사위의 잔영 - 철가면 vs 데미안 이벤트", 4LEAF Memorial,
 * https://4leafmemorial.tistory.com/category/스크린샷/주사위의 잔영
 * Both forced values = 24; the original CANCELS those powers instead of
 * re-rolling the same deterministic tie ~100 times and showing a draw.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1150,height:860},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_CHESSMEN);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const prior=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();
   const [attacker,defender]=match.players;
   attacker.effects.destroy=2;defender.effects.block=2;
   // Disable arbitrary attack exceptions, leave all ordinary rolls real.
   attacker.effects.ultimate=0;defender.effects.ultimate=0;
   attacker.effects.scar=0;defender.effects.scar=0;
   window.__ROG_TEST__.drawGame();
   window.__LEAF_REPLAY_PROMISE__=window.__ROG_TEST__.resolveBattle(attacker,defender,false);
   return {ids:[attacker.id,defender.id],tileCount:document.querySelectorAll('#board-nodes .tile').length};
  });
  assert.equal(prior.tileCount,104,'104 recovered DMP cells remain live');
  await page.waitForFunction(()=>document.querySelector('#modal:not(.hidden)')&&
    document.querySelector('#modal-content')?.textContent.includes('DESTROY/BLOCK 24:24'),null,{timeout:10000});
  const clash=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {attack:m.players[0].effects.destroy,defense:m.players[1].effects.block,
    text:document.querySelector('#modal-content')?.textContent,
    dice:[...document.querySelectorAll('#battle-visual .battle-visual-die')].map(x=>x.dataset.eye)};
  });
  assert.equal(clash.attack,0,'original forced Destroy power was neutralized');
  assert.equal(clash.defense,0,'original forced Block power was neutralized');
  assert.match(clash.text,/강제 능력 무효화/);
  assert.ok(clash.dice.length>0&&clash.dice.every(n=>Number(n)>=1&&Number(n)<=6),
   'real fight rolls with physical dice are still presented');
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.evaluate(()=>window.__LEAF_REPLAY_PROMISE__);
  const end=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {players:m.players.map(x=>({position:x.position,effects:x.effects})),
    history:m.history.slice(-8),stage:!!document.getElementById('battle-visual'),
    actorCount:document.querySelectorAll('#board-pawns .board-pawn').length};
  });
  assert.ok(end.history.some(line=>line.includes('능력 충돌 무효화')),
   'historic simultaneous 24:24 clash is recorded instead of a silent hundred-roll loop');
  assert.equal(end.stage,false,'battle presentation exits cleanly');
  assert.equal(end.actorCount,2,'two genuine chessmen remain in the match');
  assert.deepEqual(errors,[],'no runtime errors after historical clash');
  await page.screenshot({path:'leaf-historical-ironmask-damian-clash.png'});
  console.log('ORIGINAL 2004 IRONMASK DESTROY x DAMIAN BLOCK AUTO-NEUTRALIZATION PASS',
   JSON.stringify({clash,history:end.history}));
 }finally{await browser.close()}
})().catch(error=>{console.error('SOURCE 24-24 ABILITY CLASH FAILED',error.stack||error);process.exit(1)});
