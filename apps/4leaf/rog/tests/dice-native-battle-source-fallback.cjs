'use strict';
/* 2002 original Dice/IMG.pak winBattle.spr is the primary battle stage.
 * If the source 355x113 PNG is unavailable (offline/cold iOS load),
 * the play engine and a clearly labeled CSS fallback must remain usable.
 * Never certify fallback geometry as historical 3D original art.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
async function scenario(browser,failSource){
 const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 if(failSource)await page.route('**/original/SourceSPRExtra/winBattle-01.png',route=>route.abort());
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const originalMatch=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),before=m.players.map(p=>p.position);
   window.__PENDING_REAL_BATTLE__=window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
   return {positions:before,players:m.players.length};
  });
  await page.waitForFunction(()=>{
   const stage=document.querySelector('#battle-visual');
   return stage&&['ready','fallback'].includes(stage.dataset.nativeBattlePodium)&&
    stage.dataset.nativeBattleHeading==='ready';
  },null,{timeout:16000});
  const result=await page.locator('#battle-visual').evaluate(stage=>{
   const png=stage.querySelector('.leaf-native-winbattle-podiums');
   const title=stage.querySelector('.leaf-native-winbattle-heading');
   const legs=[...stage.querySelectorAll('.leaf-battle-platform-leg')];
   const sides=[...stage.querySelectorAll('.battle-visual-side')];
   const dice=[...stage.querySelectorAll('.battle-visual-die')];
   const fake=stage.querySelector('.battle-visual-pedestal');
   return {status:stage.dataset.nativeBattlePodium,
    sourceName:png?.dataset.originalSourceMember,
    natural:[png?.naturalWidth,png?.naturalHeight],
    originalVisible:getComputedStyle(png).display!=='none',
    nativeHeadingReady:title?.naturalWidth===222&&title.naturalHeight===42,
    cssFallbackVisible:getComputedStyle(fake).display!=='none',
    physicalLegs:legs.length,
    fighters:sides.map(s=>({actor:!!s.querySelector('.battle-visual-actor'),
      source:s.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
      dieCount:s.querySelectorAll('.battle-visual-die').length})),
    realEyes:dice.map(d=>Number(d.dataset.eye))
   };
  });
  assert.equal(originalMatch.players,2);
  assert.equal(result.physicalLegs,8,'fallback support rig retained only for asset failure');
  assert.equal(result.sourceName,'Dice/IMG.pak:winBattle.spr');
  assert.ok(result.nativeHeadingReady,'original 222x42 BATTLE header stays authentic');
  assert.equal(result.fighters.length,2);
  assert.ok(result.fighters.every(f=>f.actor&&f.dieCount>0),'real independent chessmen and rolled dice remain usable');
  assert.ok(result.realEyes.length>=2&&result.realEyes.every(x=>x>=1&&x<=6));
  assert.equal(result.status,failSource?'fallback':'ready');
  assert.equal(result.originalVisible,!failSource,'native stage displayed only when its actual bytes loaded');
  assert.equal(result.cssFallbackVisible,failSource,'inferred platforms must never cover loaded original');
  if(!failSource)assert.deepEqual(result.natural,[355,113]);
  const button=page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).first();
  await button.click();
  await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:10000});
  const ended=await page.evaluate(()=>({
   busy:!!document.querySelector('#battle-visual'),
   match:window.__ROG_TEST__.getMatch().players.map(p=>p.position)
  }));
  assert.equal(ended.busy,false,'real battle can be confirmed with or without image');
  assert.deepEqual(errors,[],'fallback source failures cannot produce unhandled browser exceptions');
  await page.screenshot({path:'leaf-original-source-battle-'+(failSource?'missing-png':'ready-png')+'.png'});
  return {mode:result.status,frames:result.natural,source:result.sourceName,
   dice:result.realEyes,positions:ended.match};
 }finally{await page.close()}
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const native=await scenario(browser,false);
  const fallback=await scenario(browser,true);
  console.log('4LEAF ORIGINAL 2002 PODIUM + OFFLINE FALLBACK BOTH PASS',
   JSON.stringify({native,fallback}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE BATTLE DUAL ACCEPTANCE FAILED',e.stack||e);process.exit(1)});
