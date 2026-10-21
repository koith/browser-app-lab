const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_CHESSMEN?.length>50);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForSelector('#battle-visual');
  await page.waitForFunction(()=>{
   const stage=document.querySelector('#battle-visual');
   return stage?.dataset.nativeBattlePodium==='ready'&&
     stage?.dataset.nativeBattleHeading==='ready';
  },null,{timeout:15000});
  // Regression: the same genuine Genesis chessman lives in the board and
  // native 2002 duel podium. Live events must update BOTH mounted OBS actors,
  // not just the board; the opposing player's pose stays independently owned.
  const synced=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),ids=m.players.slice(0,2).map(p=>String(p.id));
   const find=(selector,id)=>document.querySelector(selector+'[data-id="'+id+'"]');
   const board=ids.map(id=>find('#board-pawns .board-pawn',id));
   const duel=ids.map(id=>find('#battle-visual .leaf-battle-chessman',id));
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(ids[0],'walk',1200);
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(ids[1],'hurt',1200);
   return {ids,board:board.map(el=>({id:el?.dataset.id,pose:el?.dataset.actorPose,
    chessman:el?.dataset.chessmanId,frames:el?.dataset.sourceFrameSequence,
    source:el?.dataset.actorRig})),
    duel:duel.map(el=>({id:el?.dataset.id,pose:el?.dataset.actorPose,
    chessman:el?.dataset.chessmanId,frames:el?.dataset.sourceFrameSequence,
    source:el?.dataset.actorRig}))};
  });
  assert.equal(new Set(synced.ids).size,2,'each live duel side is a distinct match player');
  assert.deepEqual(synced.board.map(x=>x.pose),['walk','hurt']);
  assert.deepEqual(synced.duel.map(x=>x.pose),['walk','hurt'],
   'original OBS action events must also reach duel-podium actors');
  assert.deepEqual(synced.duel.map(x=>x.id),synced.ids,
   'duel actors must preserve the real match-player IDs');
  assert.deepEqual(synced.duel.map(x=>x.chessman),synced.board.map(x=>x.chessman),
   'duel and board must play each same real selected Genesis chessman');
  assert.deepEqual(synced.duel.map(x=>x.frames),synced.board.map(x=>x.frames),
   'board/podium may not substitute different inferred frame indexes');
  assert.ok(synced.duel.every(x=>x.source==='original-obs-sprite'),
   'already recovered true OBS full bodies must be rendered on both podiums');
  const state=await page.locator('#battle-visual').evaluate(stage=>{
   const style=getComputedStyle(stage);
   const sides=[...stage.querySelectorAll('.battle-visual-side')];
   return {
    stageBG:style.backgroundColor,stageBackgroundImage:style.backgroundImage,stageBorder:style.borderTopStyle,
    world:getComputedStyle(document.getElementById('board-world')).backgroundImage,
    sides:sides.map(side=>{
     const podium=side.querySelector('.battle-visual-pedestal'),actor=side.querySelector('.battle-visual-actor');
     const body=getComputedStyle(podium),top=getComputedStyle(podium,'::before'),leg=getComputedStyle(podium,'::after');
     const pr=podium.getBoundingClientRect(),ar=actor.getBoundingClientRect();
     const podiumSource=stage.querySelector('.leaf-native-winbattle-podiums');
     const headingSource=stage.querySelector('.leaf-native-winbattle-heading');
     const sourceRect=podiumSource?.getBoundingClientRect();
     const actorView=actor.getBoundingClientRect();
     const dice=[...side.querySelectorAll('.battle-visual-die')].map(x=>x.textContent);
     const name=side.querySelector('strong')?.textContent;
     const score=side.querySelector('.battle-visual-total')?.textContent;
     return {name,score,dice,sourceReady:stage.dataset.nativeBattlePodium,
      nativeTitleReady:stage.dataset.nativeBattleHeading,
      originalBattleScene:podiumSource?.getAttribute('src'),
      originalTitle:headingSource?.getAttribute('src'),
      nativeScene:[podiumSource?.naturalWidth,podiumSource?.naturalHeight],
      nativeHeading:[headingSource?.naturalWidth,headingSource?.naturalHeight],
      originalSprite:podiumSource?.dataset.originalSourceMember,
      visibleSprite:podiumSource&&getComputedStyle(podiumSource).display,
      fallbackDisplay:body.display,
      redundantVS:getComputedStyle(stage.querySelector('.battle-visual-vs')).display,
      sourceScreenBounds:sourceRect?.toJSON(),
      actorScreenBounds:actorView?.toJSON(),
      mesh:body.clipPath,bodyColor:body.backgroundImage,
      deck:top.backgroundImage,legs:leg.backgroundImage,
      openSupport:body.backgroundImage==='none'&&body.backgroundColor==='rgba(0, 0, 0, 0)',
      supports:[...podium.querySelectorAll('.leaf-battle-platform-leg')].map(e=>({
       width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,
       display:getComputedStyle(e).display
      })),
      bodyHeight:pr.height,actorFeet:ar.bottom,deckTop:pr.top,
      actor:actor.dataset.chessmanId,
      source:actor.querySelector('.leaf-chess-original-obs:not([hidden])')?.getAttribute('src')||
       actor.querySelector('.leaf-chess-portrait')?.getAttribute('src'),original:true};
    })
   };
  });
  assert.equal(state.stageBG,'rgba(0, 0, 0, 0)','the recovered forest is visible through the duel, no fake opaque window');
  assert.equal(state.stageBackgroundImage,'none','duel overlay is transparent, not a 2D screenshot');
  assert.equal(state.stageBorder,'none','duel uses real terrain, not a GUI popup box');
  assert.ok(state.world.includes('/original/IMG/bgtile.png'),'genuine 725x485 source forest remains below 3D mechanical stages');
  assert.equal(state.sides.length,2,'real active match has two independent duel platforms');
  assert.ok(state.sides.every(s=>s.sourceReady==='ready'&&s.nativeTitleReady==='ready'&&
   s.originalSprite==='Dice/IMG.pak:winBattle.spr'&&
   s.originalBattleScene==='./original/SourceSPRExtra/winBattle-01.png'&&
   s.originalTitle==='./original/SourceSPRExtra/winBattle-00.png'&&
   JSON.stringify(s.nativeScene)==='[355,113]'&&JSON.stringify(s.nativeHeading)==='[222,42]'),
   '2002 actual battle stage and BATTLE title must be native recovered source IMG sprites, NOT inferred CSS geometry');
  assert.ok(state.sides.every(s=>s.fallbackDisplay==='none'&&
   s.redundantVS==='none'&&s.visibleSprite==='block'),
   'source 355x113 bitmap must REPLACE CSS fake metal legs and duplicate HTML VS');
  // Original asset recovery must degrade honestly on transient CDN/PWA
  // failures: no invisible battle platform or fake "original" pixel claim.
  // Exercise the actual IMG element error event, not a synthetic dataset edit.
  const alternate=await page.evaluate(async()=>{
   const stage=document.querySelector('#battle-visual');
   const img=stage.querySelector('.leaf-native-winbattle-podiums');
   const missing=new Promise(resolve=>img.addEventListener('error',resolve,{once:true}));
   img.src='./original/SourceSPRExtra/__intentionally_missing_winBattle_src_test__.png';
   await missing;
   const legs=[...stage.querySelectorAll('.leaf-battle-platform-leg')];
   const proof={status:stage.dataset.nativeBattlePodium,
     sourceDisplay:getComputedStyle(img).display,
     fallback:[...stage.querySelectorAll('.battle-visual-pedestal')].map(el=>getComputedStyle(el).display),
     actualFighters:stage.querySelectorAll('.battle-visual-actor').length,
     activeDice:stage.querySelectorAll('.battle-visual-die').length,
     visibleLegs:legs.filter(el=>getComputedStyle(el).display!=='none').length};
   const restored=new Promise(resolve=>img.addEventListener('load',resolve,{once:true}));
   img.src='./original/SourceSPRExtra/winBattle-01.png';
   await restored;
   return {...proof,recovered:stage.dataset.nativeBattlePodium,
      recoveredSize:[img.naturalWidth,img.naturalHeight]};
  });
  assert.equal(alternate.status,'fallback',
   'original battle source missing means truthfully present CSS fallback, not a blank duel');
  assert.equal(alternate.sourceDisplay,'none');
  assert.deepEqual(alternate.fallback,['block','block']);
  assert.equal(alternate.actualFighters,2);
  assert.ok(alternate.activeDice>=2);
  assert.equal(alternate.visibleLegs,8,'fallback-only 4 legs per side remain available offline');
  assert.equal(alternate.recovered,'ready',
   'the very same running battle must switch back to authentic original pixels on reload');
  assert.deepEqual(alternate.recoveredSize,[355,113]);

  // These are native source GUI sprites, NOT the still-missing 3D die.
  // Do not mis-classify ability/result/jail as the live winBattle podium.
  const classified=await page.evaluate(async()=>{
   const files={ability:['winAbility-00.png',330,284],
     result:['winResult-00.png',452,88],
     jail:['winJail-00.png',136,219]};
   const result={};
   for(const [key,[name,w,h]] of Object.entries(files)){
    const img=new Image();img.src='./original/SourceSPRExtra/'+name;
    await img.decode();result[key]=[img.naturalWidth,img.naturalHeight];
   }
   return result;
  });
  assert.deepEqual(classified,{ability:[330,284],result:[452,88],jail:[136,219]},
   'all real recovered native GUI PNGs must exist at their exact unscaled source dimensions');
  assert.ok(state.sides.every(s=>s.actorScreenBounds.height>0&&
   Number.isFinite(s.actorScreenBounds.bottom)),
   'real game OBS fighters remain separate independently positioned DOM entities above original platform art');
  assert.ok(state.sides.every(s=>s.actor?.length===4&&['original/CardData/','original/OBS/'].some(x=>(s.source||'').includes(x))&&s.name&&/^\d\d$/.test(s.score)&&s.dice.length>=1),'selected Genesis actor and rolled numbers are independently drawn');
  assert.equal(state.sides[0].originalBattleScene,state.sides[1].originalBattleScene,
   'both sides are genuine independent fighters on ONE exact native 355x113 original VS stage');
  // Live-original battle.jpg shows BATTLE, scores, two ORIGINAL metal
  // podiums, independent OBS actors/dice; it does NOT put the normal-turn
  // event message or a 2000s WEB result popup directly across the 2002 VS.
  const battleHud=await page.evaluate(()=>{
   const area=document.querySelector('#board-area');
   const tray=area.querySelector('.leaf-native-battle-actions');
   const podium=document.querySelector('#battle-visual .leaf-native-winbattle-podiums');
   const first=tray?.querySelector('#modal-buttons button');
   const r=first?.getBoundingClientRect();
   return {
    eventVisibility:getComputedStyle(document.querySelector('#dice-native-event')).visibility,
    modernRollVisibility:getComputedStyle(document.querySelector('#game .control-center')).visibility,
    originalBattleSprite:podium?.dataset.originalSourceMember,
    realButtonInCanvas:!!tray?.querySelector('#modal-buttons'),
    canPhysicallyClick:!!r&&document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===first,
    clickProbe:!r?null:(()=>{
     const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
     const t=tray?.getBoundingClientRect();
     return {button:[r.x,r.y,r.width,r.height],tray:t&&[t.x,t.y,t.width,t.height],
      buttonVisibility:getComputedStyle(first).visibility,
      buttonPointer:getComputedStyle(first).pointerEvents,
      trayPointer:getComputedStyle(tray).pointerEvents,
      interceptedBy:hit?.outerHTML?.slice(0,230)||'none',
      modalPointer:getComputedStyle(document.getElementById('modal')).pointerEvents};
    })(),
    originalPodiumBottom:podium?.getBoundingClientRect().bottom,
    buttonsTop:tray?.getBoundingClientRect().top,
    duplicateButtons:document.querySelectorAll('#modal-buttons').length,
    modalOverlayVisible:getComputedStyle(document.querySelector('#modal.battle-present .modal-window')).visibility
   };
  });
  assert.equal(battleHud.eventVisibility,'hidden','normal-turn 244x52 event prompt must NOT obscure original BATTLE heading');
  assert.equal(battleHud.modernRollVisibility,'hidden','fake modern WEB roll bar must not obscure source battle dice and VS');
  assert.equal(battleHud.realButtonInCanvas,true,'move ACTUAL battle action buttons to native board canvas, no fake duplicate');
  assert.equal(battleHud.duplicateButtons,1,'preserve one authoritative WebRTC/result action container');
  assert.equal(battleHud.canPhysicallyClick,true,'real battle buttons must be visually topmost and reachable by actual mouse/touch '+JSON.stringify(battleHud.clickProbe));
  assert.equal(battleHud.modalOverlayVisible,'hidden','the old popup chrome cannot obscure the recovered winBattle art');
  assert.ok(battleHud.buttonsTop>battleHud.originalPodiumBottom,
   'battle result controls belong BELOW original metal platforms and VS: '+JSON.stringify(battleHud));
  await page.screenshot({path:'leaf-live-3d-battle-podiums-desktop.png'});
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.locator('#battle-visual').evaluate(stage=>({
   actor:stage.querySelectorAll('.battle-visual-actor').length,
   podium:stage.querySelectorAll('.battle-visual-pedestal').length,
   dice:stage.querySelectorAll('.battle-visual-die').length,
   native:stage.querySelector('.leaf-native-winbattle-podiums')?.naturalWidth,
   imageDisplayed:getComputedStyle(stage.querySelector('.leaf-native-winbattle-podiums')).display,
   fallbackDisplayed:[...stage.querySelectorAll('.battle-visual-pedestal')]
    .map(el=>getComputedStyle(el).display),
   bg:getComputedStyle(stage).backgroundColor
  }));
  assert.equal(mobile.actor,2);
  assert.equal(mobile.podium,2);
  assert.ok(mobile.dice>=2);
  assert.equal(mobile.bg,'rgba(0, 0, 0, 0)');
  assert.equal(mobile.native,355,'iPhone must show real source resolution graphic');
  assert.equal(mobile.imageDisplayed,'block');
  assert.deepEqual(mobile.fallbackDisplayed,['none','none']);
  const mobileActions=await page.evaluate(()=>{
   const button=document.querySelector('.leaf-native-battle-actions #modal-buttons button');
   const r=button.getBoundingClientRect(),tray=button.closest('.leaf-native-battle-actions');
   const board=document.getElementById('board-area').getBoundingClientRect();
   return {physical:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===button,
     insideBoard:r.left>=board.left-1&&r.right<=board.right+1&&
      r.top>=board.top-1&&r.bottom<=board.bottom+1,
     parentInBoard:tray.parentElement.id==='board-area'};
  });
  assert.ok(mobileActions.physical&&mobileActions.insideBoard&&mobileActions.parentInBoard,
   'iPhone battle result actions remain physically tappable INSIDE original game viewport: '+JSON.stringify(mobileActions));
  await page.screenshot({path:'leaf-live-3d-battle-podiums-mobile.png'});
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:8000});
  assert.equal(await page.locator('.leaf-native-battle-actions').count(),0,
   'result tray is cleaned up after battle to avoid stealing ordinary ROLL clicks');
  assert.equal(await page.locator('#modal .modal-window #modal-buttons').count(),1,
   'ONE result button container is returned to its original modal home');
  assert.equal(await page.locator('#dice-native-event').evaluate(x=>getComputedStyle(x).visibility),'visible',
   'native IMG/eventmsgbox prompt automatically resumes for ordinary map events');
  assert.equal(await page.locator('#game:not(.hidden)').count(),1,'actual game resumes after duel closes');
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('ORIGINAL 2002 winBattle.spr 355x113 NATIVE PIXELS PASS: 2 live OBS actors, dice, mobile and combat exit');
 }finally{await browser.close()}
})().catch(e=>{console.error('LIVE BATTLE PLATFORM FAILED:',e.stack||e);process.exit(1)});
