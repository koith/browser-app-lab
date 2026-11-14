'use strict';
/* R23 true client, not a mock reward function. Historical GP is only
 * attributed where the 2003 source snapshot exists. The match idempotency
 * gate itself is a web-side safety guarantee. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const mobile=process.env.FOURLEAF_BROWSER==='webkit';
 const browser=await (mobile?webkit:chromium).launch({
  headless:true,args:mobile?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('ai');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const out=await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   const one=m.players[0];
   m.startedAt=Date.now()-(m.players.length*90000+1000);
   const before=JSON.parse(localStorage.getItem('rog_profile'));
   const staleWinner={...one},ignored=T.finishGame(staleWinner);
   const afterIgnored=JSON.parse(localStorage.getItem('rog_profile'));
   const gpDue=T.calculateMatchReward(one,m);
   const first=T.finishGame(one);
   const afterFirst=JSON.parse(localStorage.getItem('rog_profile'));
   const firstMatch=localStorage.getItem('rog_match');
   const second=T.finishGame(one),third=T.finishGame(m.players[1]);
   const afterRepeat=JSON.parse(localStorage.getItem('rog_profile'));
   const repeatMatch=localStorage.getItem('rog_match');
   const warp=T.calculateMatchReward(one,{...m,map:'워프게이트'});
   const warpSpaced=T.calculateMatchReward(one,{...m,map:'워프 게이트'});
   const unknown=T.calculateMatchReward(one,{...m,map:'UNKNOWN'});
   return {players:m.players.length,ignored,first,second,third,before,afterIgnored,
    afterFirst,afterRepeat,firstMatch,repeatMatch,gpDue,warp,warpSpaced,unknown,
    finish:m.finished,winner:m.winner,modal:document.querySelector('#modal-content')?.textContent||''};
  });
  assert.equal(out.ignored,false,'stale/foreign winner must not complete current match');
  assert.deepEqual(out.afterIgnored,out.before,'foreign match completion has no side effects');
  assert.equal(out.first,true,'real current player completes match once');
  assert.equal(out.second,false,'same GOAL cannot claim GP twice');
  assert.equal(out.third,false,'different player cannot overwrite first winner');
  assert.equal(out.afterFirst.gp-out.before.gp,out.gpDue.gp);
  assert.equal(out.afterFirst.wins-out.before.wins,1);
  assert.deepEqual(out.afterRepeat,out.afterFirst,'duplicate GOAL leaves profile byte-identical');
  assert.equal(out.repeatMatch,out.firstMatch,'duplicate GOAL cannot mutate saved match');
  assert.equal(out.finish,true);assert.equal(out.winner,0);
  assert.ok(out.modal.includes('게임을 다시 시작할 수 있습니다'));
  assert.equal(out.warp.estimated,false,'real UI uses unspaced canonical map ID');
  assert.equal(out.warp.fullReward,29+(out.players-2)*10);
  assert.equal(out.warpSpaced.estimated,false,'older space variant remains compatible');
  assert.equal(out.unknown.estimated,true,'missing original prices remain inferred');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-r23-one-claim-original-result.png'});
  console.log('R23_REAL_GOAL_IDEMPOTENCE_AND_WARP_MAP_PASS',
    JSON.stringify({browser:mobile?'webkit':'chromium',players:out.players,credited:out.gpDue.gp,
     ignoredOldWinner:true,blockedDuplicateAwards:2,storedMatchStable:true,warpSource:29}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R23_REAL_GOAL_IDEMPOTENCE_FAIL',e.stack||e);process.exit(1)});
