'use strict';
/* A real battle scene, NOT a fresh board, against archived 2004 battle.jpg.
 * The 2002 original Dice/IMG.pak selector.png (222x152) is a complete
 * backing plus four glyphs: the original pixels are drawn once; EXISTING
 * selectors are functional, transparent hitboxes on actual original glyphs.
 * Period names, actors, dice rolls, and exact positions still differ from
 * the historic screenshot: no fraudulent pixel similarity threshold.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const sourceRoot=path.resolve(__dirname,'../original/SourceSPRExtra');
 const manifest=JSON.parse(fs.readFileSync(path.join(sourceRoot,'manifest.json')));
 for(const index of [0,1,6]){
  const frame=manifest.sprites['selector.spr'].frames[index];
  const png=fs.readFileSync(path.join(sourceRoot,'selector-'+String(index).padStart(2,'0')+'.png'));
  assert.equal(require('node:crypto').createHash('sha256').update(png).digest('hex'),frame.sha256);
  assert.deepEqual([frame.width,frame.height],[92,72]);
 }
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await browserType.launch({headless:true,args:browserType===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 // Optional repeatable WEB fixture, still running the actual combat rules.
 // The archive's actors, camera, rolls and scores remain different.
 await page.addInitScript(seed=>{
  window.LEAF_CENTRAL_API_URL='';
  if(Number.isInteger(seed)){
   let state=seed>>>0;
   Math.random=()=>((state=(Math.imul(1664525,state)+1013904223)>>>0)/4294967296);
  }
 },process.env.FOURLEAF_BATTLE_SEED?Number(process.env.FOURLEAF_BATTLE_SEED):null);
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();
   match.players[0].team=['c_0042','c_0043','c_0040'];
   match.players[1].team=['c_0045','c_0046','c_0048'];
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>document.querySelectorAll('#dice-native-party .dice-chessman-slot.occupied').length>=3);
  // The original 2004 right 2x2 ABILITY slots show FULL-BODY
  // chessmen, not three unrelated CardData facial preview posters.
  // This QA requires the visually audited real 2002 OBS packets for our
  // three specifically chosen sample actors, with actual native IMG load.
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#dice-native-party .dice-chessman-slot.occupied img')]
   .length===3&&[...document.querySelectorAll(
   '#dice-native-party .dice-chessman-slot.occupied img')]
   .every(img=>img.complete&&img.naturalWidth>0),null,{timeout:16000});
  const rightBodies=await page.evaluate(()=>[...document.querySelectorAll(
   '#dice-native-party .dice-chessman-slot.occupied')].map(slot=>{
    const img=slot.querySelector('img');
    return {id:slot.dataset.cardId,role:slot.dataset.teamIndex,
     atlas:slot.dataset.rightPortraitSource,
     proof:slot.dataset.rightPortraitFacingEvidence,
     source:img.getAttribute('src'),sourceFrame:img.dataset.nativeFrontFrame,
     image:[img.naturalWidth,img.naturalHeight],
     flipped:getComputedStyle(img).transform,
     tooltip:slot.title};
   }));
  assert.equal(rightBodies.length,3);
  for(const actor of rightBodies){
   assert.equal(actor.atlas,'OBS.pak/verified-front',
    'right actual chessman uses reviewed full-body source not face card: '+JSON.stringify(actor));
   assert.equal(actor.proof,'visually-reviewed');
   assert.equal(actor.sourceFrame,'25');
   assert.ok(/104[023]-25/.test(actor.source)&&actor.source.endsWith('-25.png'),
    'genuine 2002 OBS source frame 25 for audited 0040/0042/0043 only');
   assert.ok(actor.image[0]>10&&actor.image[1]>20,
    'full-body original OBS bitmap has real native pixel geometry');
   assert.ok(actor.flipped.startsWith('matrix('),
    'source 640-stride original upside-down pixels must display with native inverse Y');
  }
  const data=await page.evaluate(async()=>{
   const img=new Image();img.src='./original/IMG/selector.png';await img.decode();
   const source=document.querySelector('#dice-client-sidebar'),rail=document.querySelector('#dice-original-selector');
   const buttons=[...rail.querySelectorAll('button')];
   const box=(el)=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};
   return {atlas:[img.naturalWidth,img.naturalHeight],root:box(source),tools:box(rail),
    background:getComputedStyle(source).backgroundImage,backgroundSize:getComputedStyle(source).backgroundSize,
    atlasFrame:buttons.map(b=>({id:b.id,rect:box(b),bg:getComputedStyle(b).backgroundImage,
     enabled:!b.disabled,sourceControls:!!b.onclick||b.hasAttribute('onclick')})),
    party:document.querySelectorAll('#dice-native-party .dice-chessman-slot.occupied').length,
    cards:[...document.querySelectorAll('#dice-native-party .dice-chessman-slot')].map(slot=>({
     rect:box(slot),base:getComputedStyle(slot).backgroundImage,
     strip:getComputedStyle(slot,'::before').backgroundImage,
     label:getComputedStyle(slot.querySelector('b')||slot.querySelector('.dice-chessman-empty')).display,
     badge:slot.querySelector('.dice-chessman-moon')?getComputedStyle(slot.querySelector('.dice-chessman-moon')).display:null
    }))};
  });
  assert.deepEqual(data.atlas,[222,152],'true source selector IMG, not WEB mock');
  assert.ok(data.party>=3,'right source panel is LIVE selected team');
  if(!mobile){
   assert.ok(data.background.includes('/original/IMG/selector.png'),
    'entire recovered source bitmap is the functional right panel BASE (not four isolated icons)');
   assert.equal(data.backgroundSize,'222px 152px');
   assert.equal(data.root.width,222);
   assert.equal(data.root.height,152);
   for(let i=0;i<data.cards.length;i++){
    const card=data.cards[i];
    assert.equal(card.rect.width,92,'native selector.spr card width');
    assert.equal(card.rect.height,72,'native selector.spr card height');
    assert.equal(card.rect.x-data.root.x,30+(i%2)*96,'source 2x2 card columns');
    assert.equal(card.rect.y-data.root.y,Math.floor(i/2)*76,'source 2x2 card rows');
    assert.ok(card.base.includes('/SourceSPRExtra/selector-06.png'));
    assert.equal(card.label,'none','no WEB name/empty band covers original card chrome');
    if(i<3){
     assert.ok(card.strip.includes(i===0?'selector-01.png':'selector-00.png'),
      'normal/selected card surface and ABILITY strip come from source SPR');
     assert.equal(card.badge,'none','unverified CSS moon is not a native S/P/C assignment');
    }
   }
   const y=[24,55,86,117];
   assert.deepEqual(data.atlasFrame.map(x=>x.id),[
    'dice-inspect-tool','dice-next-tool','dice-items-toggle','dice-ability-tool']);
   for(let i=0;i<4;i++){
    const item=data.atlasFrame[i];
    assert.ok(Math.abs(item.rect.y-data.root.y-y[i])<=2,
      'real hit target must be aligned to original glyph '+i+': '+JSON.stringify(data));
    assert.ok(item.rect.x-data.root.x<2,'original button x origin');
    assert.equal(item.bg,'none','do not paint duplicate 222x152 sprites onto source glyph');
   }
   await page.locator('#dice-next-tool').click();
   const selected=await page.locator('#dice-native-party').getAttribute('data-selected-index');
   assert.equal(selected,'1','the original sprite button still changes LIVE chessman');
   assert.ok(await page.locator('#dice-native-party .dice-chessman-slot.selected').evaluate(
    e=>getComputedStyle(e,'::before').backgroundImage.includes('selector-01.png')),
    'changing actual selection also changes the native highlighted surface');
   await page.locator('#dice-inspect-tool').click();
   await page.waitForSelector('#modal:not(.hidden)');
   await page.locator('#modal-buttons button').first().click();
   await page.locator('#dice-items-toggle').click();
   assert.equal(await page.locator('#dice-items-toggle').getAttribute('aria-expanded'),'true',
    'source glyph still opens actual item inventory');
   await page.locator('#dice-items-toggle').click();
  }
  const duel=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   // Real combat pipeline, random genuine rules and results. This is a
   // matching BATTLE-state comparison; force neither historic scores
   // nor unrelated screenshot-only decorations into the game.
   void window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
   return m.players.slice(0,2).map(p=>({id:p.id,team:p.team}));
  });
  await page.waitForSelector('#battle-visual');
  await page.waitForFunction(()=>document.querySelector('#battle-visual')
   ?.dataset.nativeBattlePodium==='ready',null,{timeout:16000});
  // Compare the settled front pose rather than a timing-dependent attack
  // packet. This remains the game's own action timer, not a forced pose.
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#battle-visual .leaf-battle-chessman')].every(n=>n.dataset.actorPose==='idle'));
  const battle=await page.evaluate(()=>{
   const stage=document.querySelector('#battle-visual');
   return {stage:stage.dataset.nativeBattlePodium,
    sprite:stage.querySelector('.leaf-native-winbattle-podiums')?.getAttribute('src'),
    actors:[...stage.querySelectorAll('.leaf-battle-chessman')].map(n=>({
     rig:n.dataset.actorRig,chessman:n.dataset.chessmanId,
     source:n.querySelector('img.leaf-chess-original-obs')?.getAttribute('src')})),
    dice:stage.querySelectorAll('.battle-visual-die').length,
    scores:[...stage.querySelectorAll('.battle-visual-total')].map(n=>n.textContent),
    heading:(()=>{
     const h=stage.querySelector('.leaf-native-winbattle-heading').getBoundingClientRect();
     const p=stage.querySelector('.leaf-native-winbattle-podiums').getBoundingClientRect();
     const scale=Math.min(p.width/355,p.height/113);
     return {left:h.left,top:h.top,width:h.width,height:h.height,
      expectedLeft:p.left+(p.width-355*scale)/2+68*scale,
      expectedTop:Math.max(stage.getBoundingClientRect().top,p.bottom-113*scale-201*scale),scale};
    })(),
    atlas:getComputedStyle(document.querySelector('#dice-client-sidebar')).backgroundImage};
  });
  assert.equal(battle.stage,'ready');
  if(!mobile){
   assert.ok(Math.abs(battle.heading.left-battle.heading.expectedLeft)<1,'native shared SPR pivot X');
   assert.ok(Math.abs(battle.heading.top-battle.heading.expectedTop)<1,'native shared SPR pivot Y');
   assert.ok(Math.abs(battle.heading.width-222*battle.heading.scale)<1,'heading follows drawn podium bitmap');
  }else{
   assert.ok(await page.locator('.leaf-native-winbattle-heading').evaluate(h=>
    h.getBoundingClientRect().bottom<=document.querySelector('.battle-visual-total').getBoundingClientRect().top),
    'mobile retains responsive title above live scores rather than separating them across tall terrain');
  }
  assert.ok(battle.sprite?.endsWith('/winBattle-01.png'));
  assert.equal(battle.actors.length,2);
  assert.ok(battle.actors.every(n=>n.rig==='original-obs-sprite'&&n.source?.includes('/original/OBS/')),
   'real 2002 source chessmen appear IN battle, no Registry standees');
  assert.equal(battle.scores.length,2);
  assert.ok(battle.dice>=2,'real thrown dice values appear on genuine podium');
  await page.screenshot({path:'leaf-2004-actual-battle-'+browserType.name()+(mobile?'-mobile':'')+'.png'});
  if(!mobile){
   const current=await page.locator('#app').screenshot();
   const original=fs.readFileSync(path.resolve(__dirname,'../../assets/battle.jpg'));
   const comparison=await browser.newPage({viewport:{width:1640,height:640}});
   await comparison.setContent('<style>body{background:#162045;color:#f1f4ff;font:14px Arial;margin:6px}.compare{display:flex;gap:10px}.compare img{width:800px;height:600px;display:block}</style>'+
    '<div class="compare"><div>ARCHIVED 2004 — REAL BATTLE<img src="data:image/jpeg;base64,'+original.toString('base64')+'"></div>'+
    '<div>RESTORED — LIVE DICE RESOLVE BATTLE<img src="data:image/png;base64,'+current.toString('base64')+'"></div></div>');
   await comparison.waitForFunction(()=>[...document.images].every(n=>n.complete&&n.naturalWidth===800));
   await comparison.screenshot({path:'leaf-2004-actual-battle-source-vs-live-800x600.png'});
   await comparison.close();
  }
  // Confirm actual result controls remain clickable (no inert screenshot).
  const confirm=page.locator('#board-area .leaf-native-battle-actions #modal-buttons button').last();
  if(await confirm.isVisible())await confirm.click();
  await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:7000});
  assert.deepEqual(errors,[],'changing source panel must never break combat, menu or IMGs');
  console.log('REAL BATTLE + SOURCE FULL SELECTOR ATLAS '+JSON.stringify({browser:browserType.name(),mobile,duel,data,battle}));
 }finally{await browser.close();}
})().catch(e=>{console.error('BATTLE/SOURCE RIGHT-HUD FAILED',e.stack||e);process.exit(1);});
