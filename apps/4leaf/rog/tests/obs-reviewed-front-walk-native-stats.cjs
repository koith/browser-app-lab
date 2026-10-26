'use strict';
/* Actual original OBS.pak 1044/1046/1048 verified direction pairs, and
 * independently clickable original Dice/IMG.pak stats.png in a LIVE chessman
 * information dialog. 2002 original action labels/FPS remain unverified.
 * Screenshot compares BATTLE with BATTLE, not new game vs old battle.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const report=[];
  for(const id of ['0044','0046','0048']){
   const evidence=await page.evaluate(id=>{
    const m=window.__ROG_TEST__.getMatch();
    m.players[0].team=['c_'+id,'c_0042'];
    window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    if(!pawn)return {error:'missing actual game pawn',id};
    window.__LEAF_GENESIS_ACTORS__.pose(pawn,'walk',1300);
    const n=pawn.querySelector('img.leaf-chess-original-obs');
    return {id,rig:pawn.dataset.actorRig,
      audited:pawn.dataset.sourceFacingEvidence,
      frontWalk:pawn.dataset.sourceFrontWalkVerified,
      pose:pawn.dataset.actorPose,
      sequence:pawn.dataset.sourceFrameSequence,
      actionEvidence:pawn.dataset.sourceActionEvidence,
      src:n?.getAttribute('src'),
      sourceMember:pawn.dataset.actorSource};
   },id);
   assert.equal(evidence.error,undefined,JSON.stringify(evidence));
   assert.equal(evidence.rig,'original-obs-sprite',id);
   assert.ok(evidence.audited?.includes('visual-original-OBS-reviewed/front/'+id),JSON.stringify(evidence));
   assert.equal(evidence.frontWalk,'true','only inspected source front pair is allowed');
   assert.equal(evidence.sequence,'25,30,25,30','moving character must NEVER spin through source back 0..7');
   assert.equal(evidence.pose,'walk');
   assert.ok(evidence.src?.includes('/original/OBS/bulk/10'+id.slice(2)+'-25.png'),JSON.stringify(evidence));
   assert.ok(evidence.actionEvidence?.includes('WEB-movement-and-FPS-inferred'),
    'original native frame labels/FPS are NOT proven');
   report.push(evidence);
   const slot=page.locator('#dice-native-party button.dice-chessman-slot.occupied').first();
   await slot.click();
   await page.waitForSelector('#modal:not(.hidden) .dice-native-chessman-detail');
   await page.waitForFunction(()=>{const art=document.querySelector('#modal .dice-native-source-stats');return art?.complete&&art.naturalWidth===164&&art.naturalHeight===125;},null,{timeout:12000});
   const stats=await page.evaluate(()=>{
    const el=document.querySelector('#modal .dice-native-chessman-detail');
    const art=el.querySelector('img.dice-native-source-stats');
    const fields={};el.querySelectorAll('[data-field]').forEach(x=>{fields[x.dataset.field]=x.textContent;});
    return {source:el.dataset.originalSourceMember,verified:el.dataset.historicalLayoutVerified,
      selected:el.dataset.sourceCardId,
      original:art?.getAttribute('src'),actual:[art.naturalWidth,art.naturalHeight],
      visible:getComputedStyle(art).display,portrait:el.querySelector('img.dice-native-card-detail-portrait')?.getAttribute('src'),
      fields};
   });
   assert.equal(stats.source,'Dice/IMG.pak:stats.png');
   assert.equal(stats.verified,'false','do not claim recovered source stat text/placement');
   assert.equal(stats.selected,'c_'+id);
   assert.deepEqual(stats.actual,[164,125],'genuine original 164x125 stats bitmap');
   assert.equal(stats.original,'./original/IMG/stats.png');
   assert.ok(stats.portrait?.includes('/original/CardData/'));
   for(const key of ['role','move','attack','defense','intellect','ability','point'])
    assert.ok(stats.fields[key]?.length,JSON.stringify(stats));
   await page.locator('#modal-buttons button').first().click();
  }
  // Re-enter actual battle pipeline, with players' real CardData-equipped
  // game state, distinct original OBS fighters, native winBattle.spr podium,
  // score and real pip arrays. Do NOT paste historical BATTLE JPG into game.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team=['c_0044','c_0046','c_0048'];
   m.players[1].team=['c_0042','c_0043'];
   window.__ROG_TEST__.drawGame();
   void window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.nativeBattlePodium==='ready',
    null,{timeout:16000});
  const stage=await page.evaluate(()=>{
   const el=document.getElementById('battle-visual');
   return {podium:el.querySelector('.leaf-native-winbattle-podiums')?.getAttribute('src'),
    fighters:[...el.querySelectorAll('.leaf-battle-chessman')].map(a=>({
     id:a.dataset.id,rig:a.dataset.actorRig,
     frame:a.querySelector('img.leaf-chess-original-obs')?.getAttribute('src')})),
    scores:[...el.querySelectorAll('.battle-visual-total')].map(x=>x.textContent),
    dice:el.querySelectorAll('.battle-visual-die').length,
    statsArt:getComputedStyle(document.querySelector('#dice-client-sidebar')).backgroundImage};
  });
  assert.equal(stage.fighters.length,2);
  assert.ok(stage.fighters.every(a=>a.rig==='original-obs-sprite'&&a.frame?.includes('/original/OBS/')));
  assert.equal(stage.scores.length,2);
  assert.ok(stage.dice>=2);
  assert.ok(stage.podium?.includes('winBattle-01.png'));
  assert.ok(stage.statsArt.includes('selector.png'),'complete authentic right panel still used in battle');
  await page.screenshot({path:'leaf-real-battle-six-front-motion-'+engine.name()+(mobile?'-mobile':'')+'.png'});
  if(!mobile){
   const live=await page.locator('#app').screenshot();
   const original=fs.readFileSync(path.resolve(__dirname,'../../assets/battle.jpg'));
   const comp=await browser.newPage({viewport:{width:1640,height:650}});
   await comp.setContent('<style>body{margin:5px;background:#171e3a;color:#f9f9fb;font:13px Arial}.grid{display:flex;gap:10px}img{display:block;width:800px;height:600px}</style>'+
    '<div class="grid"><div>ORIGINAL 2004 BATTLE<img src="data:image/jpeg;base64,'+original.toString('base64')+'"></div>'+
    '<div>LIVE RECONSTRUCTION BATTLE / SAME UI STATE<img src="data:image/png;base64,'+live.toString('base64')+'"></div></div>');
   await comp.waitForFunction(()=>[...document.images].every(x=>x.complete&&x.naturalWidth===800));
   await comp.screenshot({path:'leaf-original-battle-vs-native-stats-obs-800x600.png'});
   await comp.close();
  }
  const ok=page.locator('#board-area .leaf-native-battle-actions #modal-buttons button').last();
  await ok.click();
  await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:7000});
  assert.deepEqual(errors,[],'source art cannot break real DMP battle/UI');
  console.log('ORIGINAL OBS 3 EXTRA FRONT WALKS + ORIGINAL STATS UI PASS',
   JSON.stringify({engine:engine.name(),mobile,report,stage}));
 }finally{await browser.close();}
})().catch(e=>{console.error('OBS FRONT + ORIGINAL STATS FAILED',e.stack||e);process.exit(1);});
