'use strict';
/* Genuine 2002-era documented item and keeper rules in the REAL game.
 * Source: https://seore.org/raw/문서:주사위의%20잔영
 * Archive: https://4leafmemorial.geld.kr/1598 (item photo),
 *          https://4leafmemorial.geld.kr/1599 (tile photo).
 * All historical EXE random weights and animations remain UNVERIFIED. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const mode=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (mode==='webkit'?webkit:chromium).launch({headless:true,args:mode==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{
   window.LEAF_CENTRAL_API_URL='';
   Math.random=()=>0.4; // stable test dice, NOT production dice changes
  });
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  // Item 1: Armageddon must affect all current real players, with the
  // documented longer user window (3 user turns vs 2 opponent turns).
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.active=0;m.players[0].team=['c_0170'];m.players[0].items=['armageddon'];
   m.players[0].usedItem=false;m.players[1].items=[];m.players[1].usedItem=false;
   m.players.forEach(p=>{p.effects.armageddon=0});
   T.setMatch(m);
  });
  const before=await page.evaluate(()=>{
   const T=window.__ROG_TEST__,p=T.getMatch().players[0];
   return {move:T.teamStats(p.team).move,
    vals:T.moveValues(p).length};
  });
  assert.equal(before.move,2,'original full-move chessman required');
  assert.equal(before.vals,2,'two genuine D4 prior to Armageddon');
  await page.locator('#my-items .item-card').first().click();
  await page.locator('#modal-buttons button').filter({hasText:'사용'}).first().click();
  const armageddon=await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   return {user:m.players[0].effects.armageddon,opponent:m.players[1].effects.armageddon,
    now:T.moveValues(m.players[0])};
  });
  assert.equal(armageddon.user,3);
  assert.equal(armageddon.opponent,2);
  const storedEffects=await page.evaluate(()=>{
   const stored=JSON.parse(localStorage.getItem('rog_match'));
   return stored.players.map(p=>p.effects.armageddon);
  });
  assert.deepEqual(storedEffects,[3,2],
   'real item consumption must persist global Armageddon effects BEFORE user reload');

  assert.equal(armageddon.now.length,1,'a movement-2 source chessman has one D4 during Armageddon');
  assert.equal(armageddon.now[0],2,'original D4 side maintained');
  // Item 2: Flipper may only cancel a LOSS, never a winning/tied battle.
  const playBattle=async(p0,p1)=>{
   await page.evaluate(({p0,p1})=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.active=0;m.mode='hotseat';
    m.players[0].team=[p0];m.players[1].team=[p1];
    m.players[0].items=['flipper'];m.players[1].items=[];
    m.players.forEach(p=>{p.usedItem=false;p.effects.armageddon=0;p.effects.destroy=0;p.effects.block=0});
    m.players[0].position=12;m.players[1].position=12;
    T.setMatch(m);window.__R27_BATTLE__=T.resolveBattle(m.players[0],m.players[1],false);
   },{p0,p1});
   await page.waitForSelector('#modal:not(.hidden) #modal-buttons button');
   const values=await page.locator('#modal-content .battle-dice b').allTextContents();
   const nums=values.map(Number);
   const has=await page.locator('#modal-buttons button').filter({hasText:'오리발 카드'}).count()>0;
   return {attacker:nums[0],defender:nums[1],flipper:has};
  };
  const winning=await playBattle('c_0170','c_0096');
  assert.ok(winning.attacker>winning.defender,JSON.stringify(winning));
  assert.equal(winning.flipper,false,'original flipper cannot cancel own winning fight');
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.evaluate(()=>window.__R27_BATTLE__);
  const losing=await playBattle('c_0096','c_0127');
  assert.ok(losing.attacker<losing.defender,JSON.stringify(losing));
  assert.equal(losing.flipper,true,'real losing player has original flipper escape');
  await page.locator('#modal-buttons button').filter({hasText:'오리발 카드'}).click();
  await page.evaluate(()=>window.__R27_BATTLE__);
  const flipperAfter=await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   return {items:m.players[0].items,used:m.players[0].usedItem,positions:m.players.map(p=>p.position)};
  });
  assert.equal(flipperAfter.used,true);
  assert.ok(!flipperAfter.items.includes('flipper'));
  assert.deepEqual(flipperAfter.positions,[12,12],'cancelled battle must not move either player');
  // Item 3: Real source-keeper tile battles must use the native tier:
  // C 1-2, B 3, A 4-6 (not inverted C=5/A=1).
  const verifiedTiers={keeperC:[1,2],keeperB:[3,3],keeperA:[4,6]};
  const tierResults=[];
  for(const [tier,[min,max]] of Object.entries(verifiedTiers)){
   await page.evaluate(tier=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.active=0;m.players[0].position=14;m.players[1].position=0;
    m.players[0].items=[];m.players[0].usedItem=false;
    m.tiles[14]=tier;T.setMatch(m);
    window.__R27_TILE__=T.resolveTile(m.players[0]);
   },tier);
   await page.waitForSelector('#modal:not(.hidden) #modal-content .battle-dice');
   const result=await page.evaluate(()=>{
    const dice=document.querySelectorAll('#modal-content .battle-dice .nums');
    const values=(dice[1]?.textContent||'').split('·').filter(Boolean);
    return {count:values.length,summary:document.querySelector('#modal-content')?.textContent||''};
   });
   assert.ok(result.count>=min&&result.count<=max,
    'original '+tier+' must use '+min+'..'+max+' defense dice: '+JSON.stringify(result));
   tierResults.push([tier,result.count]);
   await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
   await page.evaluate(()=>window.__R27_TILE__);
  }
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-r27-historical-item-keeper-rule-'+mode+'.png'});
  console.log('R27_REAL_SOURCE_ITEMS_KEEPER_TIER_PASS',JSON.stringify({
   mode,armageddon,winning,losing,flipperAfter,tierResults,
   nativeOriginalEXERandomWeights:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R27_SOURCE_RULE_FIX_FAIL',e.stack||e);process.exit(1)});
