'use strict';
/* Genuine 2002 OBS byte-run frames 0-7 play in the actual movement state.
 * Source indices, byte-authentic dimensions and per-frame native origin
 * are verified. Historical direction/attack FPS table is NOT recovered.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  // These four authentic source members contain every original 0..7 packet.
 const ids=['0046','0061','0064','0137'];
  const results=[];
  for(const id of ids){
   const setup=await page.evaluate(id=>{
    const match=window.__ROG_TEST__.getMatch();
    match.players[0].team[0]='c_'+id;
    window.__ROG_TEST__.drawGame();
    const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const native=window.ORIGINAL_LEAF_OBS_FRAMES[id];
    return {playerId:match.players[0].id,card:actor?.dataset.chessmanId,
     originalCount:native?.originalAnimationCount,
     indexes:native?.frames.map(f=>f.index),
     recovered:actor?.dataset.actorOriginalModelRecovered};
   },id);
   assert.equal(setup.card,id);
   assert.equal(setup.recovered,'true');
   assert.deepEqual(setup.indexes.slice(0,8),[0,1,2,3,4,5,6,7],
    'must source actual consecutive 8 original OBS video-packets; no invented frames');
   const motion=await page.evaluate(async playerId=>{
    const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const id=actor.dataset.chessmanId;
    const native=window.ORIGINAL_LEAF_OBS_FRAMES[id];
    const before={
     position:window.__ROG_TEST__.getMatch().players[0].position,
     turn:window.__ROG_TEST__.getMatch().turn,
     active:window.__ROG_TEST__.getMatch().active};
    const seen=new Map();
    const record=()=>{
     const idx=Number(actor.dataset.actorFrame);
     const f=native.frames.find(f=>f.index===idx);
     const img=actor.querySelector('.leaf-chess-original-obs');
     if(f&&img)seen.set(idx,{url:img.getAttribute('src'),
       width:img.style.getPropertyValue('--leaf-obs-width'),
       height:img.style.getPropertyValue('--leaf-obs-height'),
       nativeOrigin:actor.dataset.sourceFrameNativeOrigin,
       nativeSize:actor.dataset.sourceFrameNativeSize,
       footOffset:actor.dataset.sourceFootOffset,
       ground:actor.dataset.sourceGrounding,
       frameSequence:actor.dataset.sourceFrameSequence,
       claim:actor.dataset.sourcePoseMapping});
    };
    const observer=new MutationObserver(record);
    observer.observe(actor,{attributes:true,attributeFilter:['data-actor-frame']});
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(playerId,'walk',1700);
    record();
    await new Promise(resolve=>setTimeout(resolve,1350));
    observer.disconnect();
    const after={
     position:window.__ROG_TEST__.getMatch().players[0].position,
     turn:window.__ROG_TEST__.getMatch().turn,
     active:window.__ROG_TEST__.getMatch().active};
    return {frames:[...seen],before,after,sequence:actor.dataset.sourceFrameSequence,
     provenance:actor.dataset.sourceFrameSequenceProvenance};
   },setup.playerId);
   assert.deepEqual(motion.after,motion.before,
    'original sprite animation may not change Dice movement/turn/dice source rules');
   assert.equal(motion.sequence,'0,1,2,3,4,5,6,7');
   assert.equal(motion.provenance,'original-OBS-indexes/WEB-action-timing-unverified');
   assert.deepEqual(motion.frames.map(([i])=>i).sort((a,b)=>a-b),[0,1,2,3,4,5,6,7],
    'actual running game must visit all eight genuine OBS packet indexes');
   for(const [idx,proof] of motion.frames){
    const frame=await page.evaluate(([id,i])=>
     window.ORIGINAL_LEAF_OBS_FRAMES[id].frames.find(f=>f.index===i),[id,idx]);
    assert.equal(proof.url,frame.url);
    assert.equal(proof.width,frame.width+'px');
    assert.equal(proof.height,frame.height+'px');
    assert.equal(proof.nativeOrigin,frame.originX+','+frame.originY);
    assert.equal(proof.nativeSize,frame.width+'x'+frame.height);
    assert.match(proof.ground,/inferred.*native-relative/);
    assert.equal(proof.claim,'unverified');
   }
   results.push({id,sourceFrames:setup.indexes.length,
    nativeSamples:motion.frames.map(x=>x[0])});
   // Avoid carrying a live sequence into the next character identity.
   await page.evaluate(playerId=>window.__LEAF_GENESIS_ACTORS__.poseByPlayer(playerId,'idle'),setup.playerId);
  }
  // Genuine recovered combat-event frames should play ONCE, then hold
  // the last packet until the gameplay event asks for idle. This does not
  // claim that 2002 EXE action frame lookup or FPS has been recovered.
  const oneShot=await page.evaluate(async()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0046';
   window.__ROG_TEST__.drawGame();
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'attack',0);
   const sequence=pawn.dataset.sourceFrameSequence.split(',').map(Number);
   const mode=pawn.dataset.sourcePlaybackMode;
   await new Promise(resolve=>setTimeout(resolve,900));
   const at900=Number(pawn.dataset.actorFrame);
   const complete=pawn.dataset.sourcePlaybackComplete;
   await new Promise(resolve=>setTimeout(resolve,420));
   const at1320=Number(pawn.dataset.actorFrame);
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
   return {sequence,mode,at900,at1320,complete};
  });
  assert.equal(oneShot.mode,'one-shot/WEB-action-unverified');
  assert.ok(oneShot.sequence.length>=2,'recovered source must offer multiple actual event packets');
  assert.equal(oneShot.complete,'true');
  assert.equal(oneShot.at900,oneShot.sequence.at(-1));
  assert.equal(oneShot.at1320,oneShot.at900,
   'source attack packets must not repeat as a fake new gameplay hit');
  // A real PLAYER roll, not a direct poseByPlayer test, must advance all
  // eight genuine OBS indexes. The game moves one DMP cell every ~60ms;
  // previous per-cell walk(240) restarted the 120ms source clock and
  // almost always left physical gameplay stuck on source indexes 0/1.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0046'; // confirmed original source 0..7
   m.players[0].position=0;m.players[1].position=35;m.active=0;
   // Controlled event-free GAME turn; retains actual native DMP map,
   // original source player, dice engine and turn transition.
   for(let i=1;i<=15;i++)m.tiles[i]='normal';
   window.__ROG_TEST__.drawGame();
   const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   // Force a reproducible HIGH but genuine D6 result (via the game's
   // ordinary dice RNG) so multiple DMP steps occur. No source frames,
   // authoritative movement rules or production RNG are modified.
   window.__OBS_REAL_TURN_RANDOM__=Math.random;
   Math.random=()=>0.84;
   window.__OBS_REAL_TURN_FRAMES__=[];
   const sample=()=>{
    if(actor.dataset.actorPose!=='walk')return;
    window.__OBS_REAL_TURN_FRAMES__.push({
     frame:Number(actor.dataset.actorFrame),
     position:Number(actor.dataset.position),
     clock:actor.dataset.walkSourceClock,
     file:actor.querySelector('.leaf-chess-original-obs')?.getAttribute('src')
    });
   };
   window.__OBS_REAL_TURN_OBSERVER__=new MutationObserver(sample);
   window.__OBS_REAL_TURN_OBSERVER__.observe(actor,{attributes:true,
    attributeFilter:['data-actor-frame','data-position']});
  });
  await page.screenshot({path:'leaf-obs-real-roll-source-walk-before.png'});
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__OBS_REAL_TURN_FRAMES__?.some(x=>x.frame===7),
   null,{timeout:18000});
  await page.screenshot({path:'leaf-obs-real-roll-source-walk-frame7.png'});
  const liveTurn=await page.evaluate(()=>{
   Math.random=window.__OBS_REAL_TURN_RANDOM__;
   window.__OBS_REAL_TURN_OBSERVER__?.disconnect();
   const m=window.__ROG_TEST__.getMatch();
   const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   return {lastRoll:m.lastRoll,position:m.players[0].position,
    recorded:window.__OBS_REAL_TURN_FRAMES__.slice(),
    rig:actor.dataset.actorRig,source:actor.dataset.actorSource,
    coverage:actor.dataset.sourceWalkCoverage};
  });
  assert.ok(liveTurn.position>=2,'deterministic legal D6 real Dice engine must traverse multiple DMP cells');
  assert.ok(liveTurn.lastRoll?.length&&liveTurn.lastRoll.every(Number.isInteger),
   'real source visual playback must be driven by actual rolled dice values');
  assert.equal(liveTurn.rig,'original-obs-sprite');
  assert.match(liveTurn.coverage,/^8-of-8-original-source-indices/);
  assert.deepEqual([...new Set(liveTurn.recorded.map(x=>x.frame))].sort((a,b)=>a-b),
   [0,1,2,3,4,5,6,7],
   'REAL dice movement must render all eight source OBS frames, not repeatedly restart 0,1');
  assert.ok(liveTurn.recorded.some(x=>x.clock?.startsWith('continuous-across-real-DMP-steps/')),
   'later DMP steps must preserve source frame clock instead of restarting it');
  assert.ok(liveTurn.recorded.every(x=>x.file?.includes('/OBS/bulk/1046-')),
   'real roll cannot substitute simulated or ChatTown figure frames');
  const missing=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0091';window.__ROG_TEST__.drawGame();
   const a=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   return {rig:a.dataset.actorRig,obs:!!window.ORIGINAL_LEAF_OBS_FRAMES['0091'],
    fallback:a.querySelector('.leaf-chess-original-card-fallback')?.getAttribute('src')};
  });
  assert.equal(missing.rig,'original-card-portrait-fallback');
  assert.equal(missing.obs,false);
  assert.ok(missing.fallback.includes('original/CardData/'));
  await page.screenshot({path:'leaf-obs-eight-contiguous-real-native-motion.png'});
  assert.deepEqual(errors,[]);
  console.log('GENUINE OBS 0-7 REAL GAME MOTION PASS '+JSON.stringify({
   results,missing,provenance:'source-verified per-frame OBS X/Y; provisional 2002 action/FPS'
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('OBS 8-FRAME GAME MOTION FAILED',e.stack||e);process.exit(1)});
