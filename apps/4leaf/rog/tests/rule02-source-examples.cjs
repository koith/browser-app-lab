'use strict';
/* RULE-02 source-scoped historical examples: actual game/modal and real saved state.
 * https://seore.org/w/주사위의%20잔영?rev=50 (secondary historical)
 * https://4leafmemorial.geld.kr/1577 (original 2004 Destroy/Block capture)
 * Historical server RNG, complete ability table and all online card chains are not claimed. */
const assert=require('node:assert/strict'),{chromium,webkit}=require('playwright');
(async()=>{
 const mode=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const engine=mode==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,args:mode==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
 await page.waitForFunction(()=>window.__ROG_TEST__);
 await page.locator('[data-route="lobby"]').first().click();
 await page.locator('#lobby-create').click();await page.locator('#game-mode').selectOption('hotseat');
 await page.locator('#bot-count').selectOption('1');await page.locator('#map-select').selectOption('4LEAF');
 await page.locator('#start-game').click();await page.waitForSelector('#game:not(.hidden)');
 const proof={};
 await page.evaluate(()=>{
  const T=window.__ROG_TEST__,m=T.getMatch();
  m.active=0;m.attribute='NONE';m.players[0].team=['c_0043'];m.players[0].items=['armageddon'];m.players[0].usedItem=false;m.players[0].effects.shoe=0;
  m.players[1].items=[];T.setMatch(m);Math.random=()=>.4;
 });
 const before=await page.evaluate(()=>window.__ROG_TEST__.moveValues(window.__ROG_TEST__.getMatch().players[0]));
 assert.deepEqual(before,[2,2]);
 const toggle=page.locator('#dice-items-toggle');
 if(await toggle.getAttribute('aria-expanded')==='false')await toggle.click();
 await page.locator('#my-items .item-card').first().click();
 await page.locator('#modal-buttons button').filter({hasText:'사용'}).first().click();
 proof.armageddon=await page.evaluate(()=>{
  const T=window.__ROG_TEST__,m=T.getMatch();
  return {live:m.players.map(q=>q.effects.armageddon),stored:JSON.parse(localStorage.getItem('rog_match')).players.map(q=>q.effects.armageddon),dice:T.moveValues(m.players[0]),items:m.players[0].items};
 });
 assert.deepEqual(proof.armageddon,{live:[3,2],stored:[3,2],dice:[2],items:[]});
 // Real two-party combat fixture. Captures the actual dice DOM synchronously
 // before asynchronous presentation; uses existing real clickable result tray.
 async function battle(a,b,item,seed=.4){
  return page.evaluate(({a,b,item,seed})=>{
   const T=window.__ROG_TEST__,m=T.getMatch();m.active=0;m.attribute='NONE';m.finished=false;
   m.players.forEach((p,i)=>{p.team=[i?b:a];p.position=14;p.usedItem=false;p.items=i?[]:(item?[item]:[]);p.effects={};});
   T.setMatch(m);let values=Array.isArray(seed)?seed.slice():null;
   Math.random=()=>values&&values.length?values.shift():Array.isArray(seed)?.4:seed;
   window.__rule02Battle=T.resolveBattle(m.players[0],m.players[1],false);
   return {totals:[...document.querySelectorAll('#modal-content .battle-dice b')].map(x=>Number(x.textContent)),buttons:[...document.querySelectorAll('#modal-buttons button')].map(x=>x.textContent),text:document.querySelector('#modal-content').textContent};
  },{a,b,item,seed});
 }
 async function finish(label){
  await page.locator('#modal-buttons button').filter({hasText:label}).first().click();
  await page.evaluate(()=>window.__rule02Battle);
  return page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();return {positions:m.players.map(p=>p.position),items:m.players[0].items.slice(),used:m.players[0].usedItem,stored:JSON.parse(localStorage.getItem('rog_match')).players.map(p=>p.position)};});
 }
 let win=await battle('c_0170','c_0096','flipper');assert.deepEqual(win.totals,[15,3]);assert.ok(!win.buttons.includes('오리발 카드'));
 let w=await finish('결과 확인');assert.deepEqual(w.positions,[14,0]);
 let lose=await battle('c_0096','c_0127','flipper');assert.deepEqual(lose.totals,[6,12]);assert.ok(lose.buttons.includes('오리발 카드'));
 let l=await finish('오리발 카드');assert.deepEqual(l.positions,[14,14]);assert.deepEqual(l.items,[]);assert.equal(l.used,true);
 let retreat=await battle('c_0096','c_0127',null);assert.deepEqual(retreat.totals,[6,12]);assert.deepEqual((await finish('결과 확인')).positions,[8,14]);
 let change=await battle('c_0096','c_0127','change');assert.deepEqual(change.totals,[6,12]);let ch=await finish('체인지 카드');assert.deepEqual(ch.positions,[14,8]);assert.deepEqual(ch.items,[]);
 await battle('c_0096','c_0127','bomb');let bm=await finish('자폭');assert.deepEqual(bm.positions,[0,0]);assert.deepEqual(bm.stored,[0,0]);assert.deepEqual(bm.items,[]);
 // Identical two-die teams: tie (3+3 vs 3+3), then 1+1 vs 6+6.
 let tied=await battle('c_0043','c_0043',null,[.4,.4,.4,.4,0,0,.99,.99]);assert.match(tied.text,/무승부 1회/);assert.deepEqual(tied.totals,[2,12]);assert.deepEqual((await finish('결과 확인')).positions,[0,14]);
 proof.combat={win:win.totals,loss:lose.totals,retreat:6,flipper:l.positions,change:ch.positions,bomb:bm.positions,tieReroll:tied.totals};
 // Actual keeper card landing, with original card-specific defense counts.
 proof.keepers=[];
 for(const [tile,expected] of [['keeperA',[4,6]],['keeperB',[3]],['keeperC',[2]]]){
  const k=await page.evaluate(tile=>{
   const T=window.__ROG_TEST__,m=T.getMatch();m.active=0;m.attribute='NONE';m.finished=false;
   m.players[0].team=['c_0096'];m.players[0].position=15;m.players[0].effects={};m.players[0].items=[];m.players[1].position=0;
   m.tiles[15]=tile;T.setMatch(m);Math.random=()=>.4;window.__rule02Keeper=T.resolveTile(m.players[0]);
   const el=document.querySelectorAll('#modal-content .battle-dice .nums')[1];
   return {count:(el?.textContent||'').split('·').filter(Boolean).length,description:document.querySelector('#modal-content').textContent};
  },tile);
  assert.ok(expected.includes(k.count),JSON.stringify({tile,k,expected}));
  await page.evaluate(()=>window.__rule02Keeper);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch().tiles[15]),'normal');
  proof.keepers.push([tile,k.count]);
 }
 // Real prison double and non-double turns, with actual ROLL click.
 async function jail(doubles){
  await page.evaluate(doubles=>{
   const T=window.__ROG_TEST__,m=T.getMatch();m.active=0;m.attribute='NONE';m.finished=false;m.players[0].position=12;m.players[1].position=0;
   m.players[0].team=['c_0096'];m.players[0].jail=3;m.players[0].usedItem=false;m.players[0].items=[];m.players[0].effects={armageddon:2,dove:2};
   m.tiles.fill('normal');m.tiles[0]='start';m.tiles[m.tiles.length-1]='goal';T.setMatch(m);
   let seed=doubles?[.4,.4]:[0,.99];Math.random=()=>seed.length?seed.shift():.4;
  },doubles);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().active===1,null,{timeout:30000});
  return page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch(),p=m.players[0];return {position:p.position,jail:p.jail,armageddon:p.effects.armageddon,dove:p.effects.dove};});
 }
 proof.prison=[await jail(false),await jail(true)];
 assert.deepEqual(proof.prison[0],{position:12,jail:2,armageddon:1,dove:1});
 assert.deepEqual(proof.prison[1],{position:15,jail:0,armageddon:1,dove:1});
 assert.deepEqual(errors,[]);
 console.log('RULE02 HISTORICAL EXAMPLES REAL GAME PASS '+JSON.stringify({mode,...proof}));
 }finally{await browser.close()}
})().catch(e=>{console.error('RULE02 FAIL',e.stack||e);process.exit(1)});
