'use strict';
/* Real SOURCE pixels (not CSS mannequin or screenshot overlay):
 * 2002 OBS verified front-facing frame pairs + Region/1234.png selected
 * state atlas, all wired to actual game board and channel navigation.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},serviceWorkers:'block'});
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__LEAF_LOBBY__&&window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.evaluate(()=>window.__LEAF_LOBBY__.openChannelSelect());
  await page.waitForSelector('#dice-channels:not(.hidden)');
  await page.waitForFunction(()=>window.__LEAF_DICE_CHANNEL_SPR__?.getState().loaded==='ready',null,{timeout:16000});
  const source=await page.evaluate(async()=>{
   const img=new Image();img.src='./original/Region/1234.png';await img.decode();
   return {size:[img.naturalWidth,img.naturalHeight],
    status:window.__LEAF_DICE_CHANNEL_SPR__.getState()};
  });
  assert.deepEqual(source.size,[132,124],'original Region number source atlas must be 132x124');
  assert.equal(source.status.buttons,28,'seven original channel rows each have four working real-source buttons');
  const target=page.locator('#dice-channels [data-channel="ispin:2"]');
  if(!mobile)await target.hover();
  else await target.focus();
  const lit=await target.locator('canvas.dice-source-channel-number').evaluate(canvas=>{
   const rgba=canvas.getContext('2d',{willReadFrequently:true})
    .getImageData(0,0,canvas.width,canvas.height).data;
   let ink=0;for(let i=3;i<rgba.length;i+=4)if(rgba[i]>100)ink++;
   return {original:canvas.dataset.originalMember,frame:canvas.dataset.originalFrame,
    bitmap:[canvas.width,canvas.height],ink};
  });
  assert.equal(lit.original,'Region/1234.png');
  assert.equal(lit.frame,'5','number 2/hover is ORIGINAL atlas packet 5');
  assert.ok(lit.ink>20,'visible genuine number pixels must replace empty hotspots: '+JSON.stringify(lit));
  await page.screenshot({path:'leaf-2002-region-native-number-'+(mobile?'mobile-':'')+engine.name()+'.png'});
  await target.click();
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:2');
  await page.evaluate(()=>window.__LEAF_LOBBY__.openChannelSelect());
  const selected=await page.evaluate(()=>window.__LEAF_DICE_CHANNEL_SPR__.getState());
  assert.deepEqual(selected.selected,['ispin:2'],'source selected numeral matches ACTUAL chosen Genesis channel');
  const chosen=await page.locator('#dice-channels [data-channel="ispin:2"] canvas')
   .getAttribute('data-original-frame');
  assert.equal(chosen,'7','native selected number 2 state must show source packet 7');
  await page.locator('#dice-channels [data-channel="ispin:2"]').click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const inspected=[];
  for(const id of ['0040','0042','0043']){
   const row=await page.evaluate(id=>{
    const match=window.__ROG_TEST__.getMatch();
    match.players[0].team[0]='c_'+id;window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const idle=pawn.dataset.sourceFrameSequence;
    const image=pawn.querySelector('img.leaf-chess-original-obs');
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(match.players[0].id,'walk',900);
    const walking=pawn.dataset.sourceFrameSequence;
    const evidence=pawn.dataset.sourceActionEvidence;
    const continuity=pawn.dataset.sourceFrontWalkVerified;
    const atlas=pawn.dataset.actorSource;
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(match.players[0].id,'attack',0);
    const attack=pawn.dataset.sourceFrameSequence;
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(match.players[0].id,'hurt',0);
    const hurt=pawn.dataset.sourceFrameSequence;
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(match.players[0].id,'victory',0);
    const victory=pawn.dataset.sourceFrameSequence;
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(match.players[0].id,'idle',0);
    return {id,idle,walking,attack,hurt,victory,evidence,continuity,atlas,
     image:image.getAttribute('src'),rig:pawn.dataset.actorRig};
   },id);
   assert.equal(row.idle,'25',id+' source-verified front idle');
   assert.equal(row.walking,'25,30,25,30',id+' forward-facing source-only movement (not BACK 0..7)');
   assert.equal(row.continuity,'true');
   assert.equal(row.attack,'25,18,25',id+' existing original event packet within front recovery');
   assert.equal(row.hurt,'25',id+' unrecovered native hit direction must stay front, not jump to rear');
   assert.equal(row.victory,'25,30,25');
   assert.ok(row.evidence.includes('WEB-movement-and-FPS-inferred'));
   assert.equal(row.rig,'original-obs-sprite');
   assert.ok(row.image.includes('/OBS/')&&row.image.endsWith('-25.png'));
   inspected.push(row);
  }
  // A fourth, separately reviewed original card lacked trustworthy forward
  // alternation. It must hold the VERIFIED front, not old back-facing packets.
  const staticFront=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0046';
   window.__ROG_TEST__.drawGame();
   const p=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(0,'walk',0);
   return {sequence:p.dataset.sourceFrameSequence,coverage:p.dataset.sourceWalkCoverage};
  });
  assert.equal(staticFront.sequence,'25');
  assert.ok(staticFront.coverage.startsWith('front-only/'));
  // A real TURN and dice-roll moves source actor on original DMP terrain.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0042';
   for(let i=1;i<=14;i++)m.tiles[i]='normal';
   window.__ROG_TEST__.drawGame();
  });
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,
   null,{timeout:24000});
  const after=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),p=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   return {pos:m.players[0].position,roll:m.lastRoll,actor:p.dataset.actorRig,
    original:p.dataset.actorSource,front:p.dataset.sourceFacingFrame,
    walkEvidence:p.dataset.sourceFrontWalkVerified};
  });
  assert.ok(after.pos>before&&after.roll?.length>0);
  assert.equal(after.actor,'original-obs-sprite');
  assert.equal(after.front,'25');
  await page.screenshot({path:'leaf-obs-2002-front-motion-live-'+(mobile?'mobile-':'')+engine.name()+'.png'});
  assert.deepEqual(errors,[],'native actor and regional UI must not cause runtime exceptions');
  console.log('SOURCE REGION NUMBERS + FRONT OBS REAL DMP GAME PASS',JSON.stringify({engine:engine.name(),mobile,source,lit,inspected,staticFront,after}));
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE REGION / OBS FRONT GAME FAILED',e.stack||e);process.exit(1)});
