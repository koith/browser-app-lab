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
  assert.ok(state.sides.every(s=>s.actorScreenBounds.height>0&&
   Number.isFinite(s.actorScreenBounds.bottom)),
   'real game OBS fighters remain separate independently positioned DOM entities above original platform art');
  assert.ok(state.sides.every(s=>s.actor?.length===4&&['original/CardData/','original/OBS/'].some(x=>(s.source||'').includes(x))&&s.name&&/^\d\d$/.test(s.score)&&s.dice.length>=1),'selected Genesis actor and rolled numbers are independently drawn');
  assert.equal(state.sides[0].originalBattleScene,state.sides[1].originalBattleScene,
   'both sides are genuine independent fighters on ONE exact native 355x113 original VS stage');
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
  await page.screenshot({path:'leaf-live-3d-battle-podiums-mobile.png'});
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:8000});
  assert.equal(await page.locator('#game:not(.hidden)').count(),1,'actual game resumes after duel closes');
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('ORIGINAL 2002 winBattle.spr 355x113 NATIVE PIXELS PASS: 2 live OBS actors, dice, mobile and combat exit');
 }finally{await browser.close()}
})().catch(e=>{console.error('LIVE BATTLE PLATFORM FAILED:',e.stack||e);process.exit(1)});
