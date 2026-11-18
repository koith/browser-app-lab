'use strict';
/* Original 2004 rule fixture. 4leafmemorial.geld.kr/1577 captured
 * Ironmask Destroy 6x4=24 vs Damian Block 6x4=24: BOTH fixed abilities
 * must be canceled before a fair actual attack, rather than endlessly
 * replaying a deterministic draw. Item details without source documents
 * are labeled WEB, even when transaction tests pass. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 try{
  await page.addInitScript(()=>{
   window.LEAF_CENTRAL_API_URL='';
   // A deterministic game fixture, not the production RNG. All test
   // participants receive exactly the same original-model dice series.
   let seed=0x4ae71;
   Math.random=()=>{
    seed=(Math.imul(1664525,seed)+1013904223)>>>0;
    return seed/4294967296;
   };
  });
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   if(m.players.length!==2)throw Error('two real source players required');
   m.players[0].name='철가면',m.players[1].name='데미안';
   m.players[0].team=['c_0091'];m.players[1].team=['c_0127'];
   m.players[0].position=m.players[1].position=12;
   m.players[0].effects.destroy=2;m.players[1].effects.block=2;
   m.players[0].items=[];m.players[1].items=[];
   m.players[0].usedItem=false;m.players[1].usedItem=false;
   T.setMatch(m);T.drawGame();
   window.__R21_BATTLE_PROMISE__=T.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>document.querySelector('#modal-content')?.textContent.includes('DESTROY/BLOCK 24:24'),null,{timeout:15000});
  const clash=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {effectA:m.players[0].effects.destroy,effectB:m.players[1].effects.block,
    panel:document.querySelector('#modal-content')?.textContent,
    buttons:[...document.querySelectorAll('#modal-buttons button')].map(b=>b.textContent),
    shown:!document.querySelector('#battle-visual')?.hidden};
  });
  assert.equal(clash.effectA,0,'original 24 vs 24 Destroy canceled');
  assert.equal(clash.effectB,0,'original 24 vs 24 Block canceled');
  assert.ok(clash.panel.includes('강제 능력 무효화'));
  assert.ok(clash.buttons.includes('결과 확인'));
  await page.screenshot({path:'leaf-r21-historical-destroy-block-clash.png'});
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.waitForFunction(()=>document.querySelector('#battle-visual')===null,{timeout:16000});
  await page.evaluate(()=>window.__R21_BATTLE_PROMISE__);
  const first=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {positions:m.players.map(p=>p.position),
    effects:m.players.map(p=>({destroy:p.effects.destroy,block:p.effects.block})),
    history:m.history.map(x=>typeof x==='string'?x:JSON.stringify(x))};
  });
  assert.ok(first.positions.some(x=>x<12),'real rerolled battle outcome must retreat one opponent');
  assert.ok(first.history.some(x=>x.includes('DESTROY 24')&&x.includes('BLOCK 24')),'historical special event is logged');
  // Real user-visible battle-card transactions. Historical exact bomb and
  // flipper secondary effects are not inferred as source-verified rules.
  for(const [id,action,expected] of [['bomb','자폭',true],['flipper','오리발',false]]){
   await page.evaluate(id=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    // Original flipper cancels ONLY a losing combat. The old fixture
    // assumed the item appeared even when the real attacker had won.
    if(id==='flipper')Math.random=()=>0.4;
    m.players[0].team=[id==='flipper'?'c_0096':'c_0091'];
    m.players[1].team=['c_0127'];
    m.players[0].position=14;m.players[1].position=14;
    m.players[0].items=[id];m.players[0].usedItem=false;
    m.players[0].effects.destroy=0;m.players[1].effects.block=0;
    T.setMatch(m);T.drawGame();
    window.__R21_BATTLE_PROMISE__=T.resolveBattle(m.players[0],m.players[1],false);
   },id);
   await page.waitForFunction(text=>[...document.querySelectorAll('#modal-buttons button')].some(b=>b.textContent.includes(text)),action,{timeout:15000});
   await page.locator('#modal-buttons button').filter({hasText:action}).first().click();
   await page.waitForFunction(()=>document.querySelector('#battle-visual')===null,{timeout:15000});
   await page.evaluate(()=>window.__R21_BATTLE_PROMISE__);
   const after=await page.evaluate(()=>{
    const m=window.__ROG_TEST__.getMatch();
    return {positions:m.players.map(p=>p.position),items:m.players[0].items.slice(),
     used:m.players[0].usedItem,history:m.history.slice(-5)};
   });
   assert.equal(after.items.includes(id),false,'single-use card consumed exactly once: '+id);
   assert.equal(after.used,true,'player used this item during the one combat');
   if(expected)assert.deepEqual(after.positions,[0,0],'self destruct sends both actual players to START');
   else assert.deepEqual(after.positions,[14,14],'flipper negates retreat but must not teleport either player');
  }
  assert.deepEqual(errors,[]);
  console.log('R21_HISTORICAL_2004_DESTROY_BLOCK_REAL_BATTLE_PASS',JSON.stringify({
   engine,historical:'https://4leafmemorial.geld.kr/1577',
   originalSourceRule:'Destroy 24 versus Block 24 => both abilities cancel',
   afterClash:first.positions,items:['bomb','flipper'],otherItemEffects:'WEB-PROVISIONAL'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R21_HISTORICAL_RULE_QA_FAILED',e.stack||e);process.exit(1)});
