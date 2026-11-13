'use strict';
/* EVID-01: reproducible browser captures for all seven archived reference
 * photos (six logical scenes). Metadata separates actual source screenshot
 * state from our live scene. NOT a false historical same-state/SSIM claim. */
const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},deviceScaleFactor:1,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const out={schema:'4leaf-reproducible-source-live-state-v1',generated:new Date().toISOString(),
  originalStillFrameCannotProveTiming:true,scenes:[]};
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  const capture=async(id,ref,selector,steps,limit)=>{
   await page.waitForSelector(selector,{state:'visible',timeout:18000});
   const source=fs.readFileSync(path.resolve(__dirname,'../../assets/'+ref));
   const media=(ref.endsWith('.png')?'image/png':'image/jpeg');
   const original=await page.evaluate(async url=>{
    const img=new Image();img.src=url;await img.decode();
    return [img.naturalWidth,img.naturalHeight];
   },'data:'+media+';base64,'+source.toString('base64'));
   const state=await page.evaluate(sel=>{
    const el=document.querySelector(sel),rect=el.getBoundingClientRect();
    const m=window.__ROG_TEST__?.getMatch?.();
    return {liveStage:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
     match:m?{map:m.map,players:m.players.length,round:m.round,active:m.active,
      turnPositions:m.players.map(p=>p.position),finished:m.finished}:null,
     peerCount:document.querySelectorAll('#social-avatar-layer .social-avatar').length,
     viewport:{width:innerWidth,height:innerHeight}};
   },selector);
   assert.ok(original[0]>100&&original[1]>100);
   assert.ok(state.liveStage.width>50&&state.liveStage.height>50);
   const shot='leaf-r20-evidence-'+id+'.png';
   await page.screenshot({path:shot});
   out.scenes.push({id,reference:'apps/4leaf/assets/'+ref,referenceSha256:crypto.createHash('sha256').update(source).digest('hex'),
    originalImageSize:original,liveCapture:shot,sourceState:limit,
    liveState:state,reproduce:steps,exactlyIdenticalHistoricalState:false,
    historicProtocol3DPositionAndFullParticipantRoster:'UNVERIFIED'});
  };
  await capture('world','sky.jpg','#leaf-world-stage',
   ['open index.html','wait for source sky art'], '2002-2004 WorldMap screenshot; no historic user/session snapshot');
  await page.evaluate(()=>window.__ROG_TEST__.go('city'));
  await capture('street','street.jpg','#street-viewport',
   ['navigate city from live WorldMap','use source 1938x404 three-panel panorama'],
   'archived MainStreet screenshot; original EXE hotspot commands unknown');
  await page.evaluate(()=>window.__ROG_TEST__.go('shop'));
  await capture('shop','shop_ref.png','#shop-native-stage',
   ['navigate Magic Carden','source-backed shop stage and account inventory'],
   '2003-2004 shop screenshot; later 4x2 scene differs from source 2002 3x3 atlas');
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('R20 archived chat state evidence',4,12);
  });
  await capture('chat','chat.jpg','#social-image-frame',
   ['enter north ChatTown','open room background 4','send original source chat'],
   'archived 2004 794x528 room4, participant names and actual message history cannot be reproduced');
  await capture('chat_ref','chat_ref.jpg','#social-image-frame',
   ['remain inside original room4','inspect native furniture/participant list'],
   'archived second room4 screenshot, different archival avatars/participants');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await capture('board','board.jpg','#game',
   ['create live hotseat original DMP match','record original map id and turn'],
   'historic file board.jpg scene may contain duel overlay; exact historic board state unknown');
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players.forEach(p=>{p.position=5;});
   T.setMatch(m);T.drawGame();T.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.nativeBattlePodium==='ready',null,{timeout:15000});
  await capture('battle','battle.jpg','#battle-visual',
   ['trigger real live 2-player battle','show source winBattle.spr and original OBS actors'],
   'archived 800x600 battle image shows historically different participants/dice; six stable anchors independently tested');
  assert.equal(out.scenes.length,7,'all six reference scene categories and two chat photos');
  fs.writeFileSync('leaf-r20-evidence-scene-states.json',JSON.stringify(out,null,2)+'\n');
  assert.deepEqual(errors,[]);
  console.log('R20_SEVEN_REFERENCE_SCENE_STATES_PASS',JSON.stringify(out.scenes.map(x=>({id:x.id,source:x.reference,size:x.originalImageSize,live:x.liveState.liveStage}))));
 }finally{await browser.close()}
})().catch(e=>{console.error('R20_SCENE_CAPTURE_FAIL',e.stack||e);process.exit(1)});
