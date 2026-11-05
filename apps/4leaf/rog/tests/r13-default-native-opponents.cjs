'use strict';
// R13 follow-up: PR #727's CHR source resolve must really render BOTH
// default opponents (0042->1026, 0045->1029) on the battle podium.
// This is a live match test, not a standalone DOM mount or an alias guess.
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(
  engine==='webkit'?{headless:true}:{headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__);
  const owner=await page.evaluate(()=>['0042','0045'].map(card=>{
   const map=window.__LEAF_CHR_BODY_MAP__;
   const identity=map.lookup(card),frames=map.resolve(card);
   return {card,member:identity?.member,source:frames?.originalMember,
    prefix:frames?.frames?.[0]?.url?.replace(/-\d{3}\.png$/,'-'),length:frames?.frames?.length};
  }));
  assert.deepEqual(owner.map(o=>o.member),['1026','1029'],
   'native CHR byte +260 must map each default opponent to its own original member');
  assert.ok(owner.every(o=>o.source&&o.length>0&&o.prefix),
   'each real default original CHR body must resolve to SHA-verified original frames');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=['c_0042'];m.players[1].team=['c_0045'];
   T.setMatch(m);T.drawGame();T.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>{
   const stage=document.getElementById('battle-visual');
   return stage?.dataset.nativeBattlePodium==='ready'&&
    stage.querySelectorAll('.leaf-battle-chessman').length===2;
  },null,{timeout:15000});
  await page.waitForFunction(()=>{
   return [...document.querySelectorAll('#battle-visual .leaf-battle-chessman')]
    .every(n=>n.dataset.actorSourceLoad==='ready'&&
     n.querySelector('img.leaf-chess-original-obs')?.naturalWidth>0);
  },null,{timeout:15000});
  const snapshot=await page.evaluate(()=>[...document.querySelectorAll(
   '#battle-visual .leaf-battle-chessman')].map(n=>({
    player:n.dataset.id,card:String(n.dataset.chessmanId||'').replace(/^c_/, ''),
    rig:n.dataset.actorRig,source:n.dataset.actorSource,
    ready:n.dataset.actorSourceLoad,
    img:n.querySelector('img.leaf-chess-original-obs')?.getAttribute('src'),
    fallback:!!n.querySelector('.leaf-chess-portrait:not([hidden])')
  })));
  assert.deepEqual(snapshot.map(a=>a.card),['0042','0045'],
   'two sides must show their independently selected original cards');
  for(let i=0;i<snapshot.length;i++){
   const a=snapshot[i],o=owner[i];
   assert.equal(a.rig,'original-obs-sprite','must not use portrait fallback');
   assert.equal(a.source,o.source,'must retain exact CHR source member');
   assert.equal(a.ready,'ready','native PNG must be decoded');
   assert.ok(a.img?.startsWith(o.prefix),
    'must show the card-owned original OBS PNG: '+JSON.stringify({a,o}));
  }
  // Repeat the actual result button hit test in phone landscape.
  await page.setViewportSize({width:750,height:342});
  const button=page.locator('.leaf-native-battle-actions button, #modal-buttons button',
   {hasText:'결과 확인'}).first();
  await button.waitFor({state:'visible'});
  const hit=await button.evaluate(b=>{
   const r=b.getBoundingClientRect(),p=document.elementFromPoint(
    r.left+r.width/2,r.top+r.height/2);
   return {top:r.top,bottom:r.bottom,height:innerHeight,
    hit:b===p||b.contains(p)};
  });
  assert.ok(hit.top>=0&&hit.bottom<=hit.height&&hit.hit,
   'landscape result button must be fully onscreen and clickable');
  await button.click();
  await page.waitForFunction(()=>!document.getElementById('battle-visual'));
  assert.deepEqual(errors,[],'no game runtime exceptions');
  console.log('R13 DEFAULT NATIVE OPPONENTS PASS',JSON.stringify({engine,owner,snapshot,hit}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R13 DEFAULT NATIVE OPPONENTS FAILED',e.stack||e);process.exit(1)});
