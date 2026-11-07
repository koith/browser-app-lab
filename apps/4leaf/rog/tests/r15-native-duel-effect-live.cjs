'use strict';
/* R15 release gate: check that a REAL source-native duel uses the actor's
 * OWN recovered CHR event tuple and renders ORIGINAL effect member pixels.
 * This is a live Playwright game, not a mock DOM or fabricated animation.
 * Original event/source VERIFIED; relative 2D WEB timing/offset INFERRED.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await browserType.launch(browserType===chromium?{args:['--no-sandbox']}:{});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_NATIVE_DUEL_FX__&&
   window.__LEAF_BATTLE_DICE_ROLL__&&window.ORIGINAL_LEAF_DUEL_EFFECTS,null,{timeout:30000});
  const inventory=await page.evaluate(()=>{
   const manifest=window.ORIGINAL_LEAF_DUEL_EFFECTS,api=window.__LEAF_NATIVE_DUEL_FX__;
   return {members:Object.keys(manifest).length,
    frames:Object.values(manifest).reduce((s,m)=>s+m.frames.length,0),
    attacker:api.eventsFor('0042').map(e=>({member:e.member,tick:e.tick,type:e.type})),
    defender:api.eventsFor('0045').map(e=>({member:e.member,tick:e.tick,type:e.type})),
    missing:api.eventsFor('0156').length};
  });
  assert.ok(inventory.members>=36&&inventory.frames>=512,
   'live browser must serve all source-verified effect members, not just R15 round 1');
  assert.ok(inventory.attacker.some(e=>e.member.endsWith('/1097.obs')),
   'source CHR 0042 owns original 1097 effect event');
  assert.equal(inventory.missing,0,'0156 must not borrow another body or fabricated effects');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   window.__r15NativeTrace=[];
   const observer=new MutationObserver(()=>{
    const stage=document.getElementById('battle-visual');
    if(!stage)return;
    for(const n of stage.querySelectorAll('.leaf-native-duel-effect')){
     const url=n.querySelector('img')?.getAttribute('src');
     const row={member:n.dataset.nativeMember,frame:n.dataset.sourceFrame,
      tick:n.dataset.nativeEventTick,type:n.dataset.nativeEventType,url};
     if(url&&!window.__r15NativeTrace.some(x=>JSON.stringify(x)===JSON.stringify(row)))
      window.__r15NativeTrace.push(row);
    }
   });
   observer.observe(document.body,{subtree:true,childList:true,attributes:true,
    attributeFilter:['data-source-frame','src']});
   window.__r15NativeObserver=observer;
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=['c_0042'];m.players[1].team=['c_0045'];
   T.setMatch(m);T.drawGame();T.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>{
   const s=document.getElementById('battle-visual');
   return s?.dataset.duelNativeFxStarted==='true'&&
    Number(s.dataset.duelSourceEffectFrames)>0;
  },null,{timeout:30000});
  await page.waitForFunction(()=>document.getElementById('battle-visual')?.dataset.battlePhase==='outcome',
   null,{timeout:25000});
  const rec=await page.evaluate(()=>{
   const stage=document.getElementById('battle-visual');
   const trace=window.__r15NativeTrace||[];
   window.__r15NativeObserver?.disconnect();
   return {effects:Number(stage.dataset.duelSourceEffects)||0,
    rendered:Number(stage.dataset.duelSourceEffectFrames)||0,
    evidence:stage.dataset.duelSourceEffectEvidence,
    attackEvent:stage.dataset.duelNativeFxStarted,
    actors:[...stage.querySelectorAll('.leaf-battle-chessman')].map(a=>({
     card:a.dataset.chessmanId,rig:a.dataset.actorRig,side:a.dataset.duelSide,
     result:a.dataset.duelResult,slot:a.dataset.sourceNativeSlot,
     duration:Number(a.dataset.sourceNativeDurationMs)||0,
     source:a.dataset.sourceFrameSequenceProvenance,
     action:a.dataset.sourceActionTable})),
    trace};
  });
  assert.equal(rec.attackEvent,'true');
  assert.ok(rec.effects>0&&rec.rendered>0&&rec.trace.length>0,
   'must show actual original OBS effect frames during attack');
  assert.ok(rec.trace.every(x=>x.member==='obs.pak/1097.obs'&&
    /^\.\/original\/OBS\/duel-effects\/obs-1097-\d{3}\.png$/.test(x.url)&&
    Number.isInteger(Number(x.frame))),
   'attacker must draw its OWN original effect 1097 (no CSS substituting another card)');
  assert.deepEqual(rec.actors.map(x=>x.card),['0042','0045']);
  assert.ok(rec.actors.every(x=>x.rig==='original-obs-sprite'));
  // R17: real WebKit/Chromium outcome must use each CHR's own original
  // post-lunge native slot, not arbitrary poses or synthetic sprite frames.
  // Source index/tick VERIFIED; slot 13=hurt / 14=victory WEB-INFERRED.
  assert.deepEqual(rec.actors.map(x=>x.slot).sort(),['13','14'],
   'both original source outcome slots must be active');
  for(const actor of rec.actors){
   assert.equal(actor.slot,actor.result==='win'?'14':'13',
    'WEB-inferred win/hurt role must use a source-verifiable slot');
   assert.ok(actor.duration>=960,'source slot tick duration retained');
   assert.match(actor.source||'',/VERIFIED.*INFERRED/,
    'original source provenance and semantic uncertainty visible');
   assert.match(actor.action||'',/native-CHR-duel-(hurt|victory)-candidate-slot(13|14)/,
    'actual gameplay pose must draw indexed original source frames');
  }
  assert.deepEqual(errors,[]);
  console.log('R15_NATIVE_DUEL_EFFECTS_LIVE_PASS',JSON.stringify({
   browser:browserType.name(),members:inventory.members,frames:inventory.frames,
   effects:rec.effects,rendered:rec.rendered,observed:rec.trace.length,
   sourceMember:rec.trace[0].member}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R15_NATIVE_DUEL_EFFECTS_LIVE_FAIL',e.stack||e);process.exitCode=1});
