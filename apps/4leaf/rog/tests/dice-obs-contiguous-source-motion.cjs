'use strict';
/* Real DMP movement: CHR card 0056's original body 1040 and card 0088's
 * body 1071 use actual source 3,5,6,7,8 rear keys (frame 4 is skipped).
 * Original tick milliseconds and semantics are still inferred. */
const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   window.__LEAF_CHR_BODY_MAP__&&window.__LEAF_NATIVE_CARD_ACTIONS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const results=[];
  for(const [card,member] of [['0056','1040'],['0088','1071']]){
   const proof=await page.evaluate(async({card,member})=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team[0]='c_'+card;T.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    pawn.dataset.travelFacing='away';
    const before={turn:m.turn,active:m.active,position:m.players[0].position};
    const seen=new Map(),source=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    const capture=()=>{
     const i=Number(pawn.dataset.actorFrame),frame=source.frames[i];
     if(!frame)return;
     seen.set(i,{url:pawn.querySelector('img.leaf-chess-original-obs')?.getAttribute('src'),
      w:pawn.querySelector('img.leaf-chess-original-obs')?.style.getPropertyValue('--leaf-obs-width'),
      h:pawn.querySelector('img.leaf-chess-original-obs')?.style.getPropertyValue('--leaf-obs-height'),
      origin:pawn.dataset.sourceFrameNativeOrigin,
      expectedUrl:frame.url,expectedW:frame.width+'px',expectedH:frame.height+'px',
      expectedOrigin:frame.originX+','+frame.originY});
    };
    const observer=new MutationObserver(capture);
    observer.observe(pawn,{attributes:true,attributeFilter:['data-actor-frame']});
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'walk',1300);
    capture();await new Promise(resolve=>setTimeout(resolve,1000));
    observer.disconnect();
    const after={turn:m.turn,active:m.active,position:m.players[0].position};
    const out={card,member,source:pawn.dataset.actorSource,
      rig:pawn.dataset.actorRig,sequence:pawn.dataset.sourceFrameSequence,
      ticks:pawn.dataset.sourceNativeKeyTicks,provenance:pawn.dataset.sourceKeyframeProvenance,
      before,after,seen:[...seen]};
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
    return out;
   },{card,member});
   assert.equal(proof.rig,'original-obs-sprite');
   assert.ok(proof.source.includes(member+'.obs'));
   assert.equal(proof.sequence,'3,5,6,7,8');
   assert.equal(proof.ticks,'0,3,6,9,12');
   assert.match(proof.provenance,/source-native-18-byte-keyframe-indices-VERIFIED/);
   assert.deepEqual(proof.before,proof.after,'visual animation cannot modify actual DMP turn');
   const seen=proof.seen.map(([i])=>i).sort((a,b)=>a-b);
   assert.deepEqual(seen,[3,5,6,7,8],
    'real render must show every ORIGINAL source frame and skip 4');
   for(const [i,p] of proof.seen){
    assert.equal(p.url,p.expectedUrl);
    assert.equal(p.w,p.expectedW);assert.equal(p.h,p.expectedH);
    assert.equal(p.origin,p.expectedOrigin);
   }
   results.push({card,member,seen});
  }
  const oneShot=await page.evaluate(async()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team[0]='c_0056';T.drawGame();
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'attack',0);
   const mode=pawn.dataset.sourcePlaybackMode;
   const sequence=pawn.dataset.sourceFrameSequence;
   await new Promise(resolve=>setTimeout(resolve,1200));
   const end=Number(pawn.dataset.actorFrame),complete=pawn.dataset.sourcePlaybackComplete;
   await new Promise(resolve=>setTimeout(resolve,350));
   const still=Number(pawn.dataset.actorFrame);
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
   return {mode,sequence,end,still,complete};
  });
  assert.equal(oneShot.mode,'one-shot/WEB-action-unverified');
  assert.equal(oneShot.end,oneShot.still,'battle action must not loop after completion');
  assert.equal(oneShot.complete,'true');
  const turn=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0056';
   m.players[0].position=0;m.players[1].position=35;m.active=0;
   for(let i=1;i<=15;i++)m.tiles[i]='normal';
   window.__ROG_TEST__.drawGame();
   window.__CHR_RANDOM__=Math.random;Math.random=()=>0.84;
   return {before:m.players[0].position};
  });
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>=2,
   null,{timeout:24000});
  const live=await page.evaluate(()=>{
   Math.random=window.__CHR_RANDOM__;
   const m=window.__ROG_TEST__.getMatch(),p=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   return {position:m.players[0].position,roll:m.lastRoll,rig:p.dataset.actorRig,
    source:p.dataset.actorSource,coverage:p.dataset.sourceWalkCoverage};
  });
  assert.ok(live.position>=2&&live.roll?.length);
  assert.equal(live.rig,'original-obs-sprite');
  assert.ok(live.source.includes('1040.obs'));
  assert.match(live.coverage,/native-CHR-OBS-indices/);
  for(const card of ['0040','0156']){
   const bad=await page.evaluate(card=>{
    const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team[0]='c_'+card;T.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    return {rig:pawn.dataset.actorRig,
     image:pawn.querySelector('.leaf-chess-original-card-fallback')?.getAttribute('src')};
   },card);
   assert.equal(bad.rig,'original-card-portrait-fallback');
   assert.ok(bad.image?.startsWith('./original/CardData/chm_'));
  }
  await page.screenshot({path:'leaf-chr-native-5-frame-rear-walk-real-game.png'});
  assert.deepEqual(errors,[]);
  console.log('4LEAF CHR SOURCE-NATIVE CONTIGUOUS REAL MOVEMENT PASS',
   JSON.stringify({results,oneShot,live}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR NATIVE MOVEMENT GAME FAILED',e.stack||e);process.exit(1)});
