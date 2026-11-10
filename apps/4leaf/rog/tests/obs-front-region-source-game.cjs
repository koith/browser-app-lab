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
  if(mobile)await page.locator('#dice-room-ready-focus').click();
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const inspected=[];
  for(const id of ['0056','0059','0060']){
   const row=await page.evaluate(id=>{
    const match=window.__ROG_TEST__.getMatch();
    match.players[0].team[0]='c_'+id;window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const idle=pawn.dataset.sourceFrameSequence;
    const image=pawn.querySelector('img.leaf-chess-original-obs');
    // Front-only regression must not inherit a prior horizontal DMP
    // vector from an unrelated real move.
    pawn.dataset.travelFacing='toward';
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
     fullFrames:window.__LEAF_CHR_BODY_MAP__?.resolve(id)?.frames?.length||0,
     image:image.getAttribute('src'),rig:pawn.dataset.actorRig};
   },id);
   const tableActor=row.fullFrames===37&&!['0084','0085','0086'].includes(id);
   assert.equal(row.idle,'22,23,24',id+' CHR native front idle');
   assert.equal(row.walking,'25,26,27,28,29,30',
    id+' forward-facing original source movement without a BACK 0..7 spin');
   assert.equal(row.continuity,'true');
   const structural=row.fullFrames===37&&!['0084','0085','0086'].includes(id);
   assert.equal(row.attack,structural?'25,31,32,32,25':'25,18,18,25',
    id+' reviewed original source strike sequence with INFERRED WEB timing');
   assert.equal(row.hurt,'22',id+' native hurt slot unknown: hold ORIGINAL front idle key 22, not synthetic frame 25');
   assert.equal(row.victory,'22',id+' native victory slot unknown: hold same body front idle 22');
   assert.ok(row.evidence.includes('WEB-movement-and-FPS-inferred'));
   assert.equal(row.rig,'original-obs-sprite');
   assert.ok(row.image.includes('/OBS/')&&
    (tableActor?['-22.png','-23.png','-24.png'].some(s=>row.image.endsWith(s)):row.image.endsWith('-25.png')),
    id+' source front image is genuine OBS packet '+row.image);
   inspected.push(row);
  }
  // 0045 is source-front frame18 ONLY (original OBS member 1045), not a
  // visually approved 25/30 pair. Never infer 2002 action/FPS from 0046.
  const formerlyStatic=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0062';
   window.__ROG_TEST__.drawGame();
   const p=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(0,'walk',0);
   return {sequence:p.dataset.sourceFrameSequence,coverage:p.dataset.sourceWalkCoverage};
  });
  assert.equal(formerlyStatic.sequence,'25,26,27,28,29,30',
   'original 1045 OBS native 18-byte table now reveals genuine 25-30 walk');
  assert.ok(formerlyStatic.coverage.startsWith('native-CHR-OBS-indices/'));
  // A real TURN and dice-roll moves source actor on original DMP terrain.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0059';
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
  assert.equal(after.front,'22');
  await page.screenshot({path:'leaf-obs-2002-front-motion-live-'+(mobile?'mobile-':'')+engine.name()+'.png'});
  assert.deepEqual(errors,[],'native actor and regional UI must not cause runtime exceptions');
  console.log('SOURCE REGION NUMBERS + CHR OBS REAL DMP GAME PASS',JSON.stringify({engine:engine.name(),mobile,source,lit,inspected,formerlyStatic,after}));
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE REGION / OBS FRONT GAME FAILED',e.stack||e);process.exit(1)});
