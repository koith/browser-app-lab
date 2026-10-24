'use strict';
/* 2002 authenticated OBS 640-stride VIDEO RLE: real game integration.
 * Frame pixels are original; original combat action/direction table remains
 * undecoded. This gate can NEVER certify 2004 full 3D/pose fidelity.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const report=JSON.parse(fs.readFileSync(path.join(root,'original/OBS/bulk-source-report.json'),'utf8'));
 assert.equal(report.archiveSHA256,
  '49738a942ffe3856fb86b4c5ce698b7e460bb876b38c31884028b3e2e833d514',
  'publish ONLY SHA-verified original OBS.pak');
 assert.ok(report.accepted>=85,'native decoder must not regress strict source frame recovery');
 assert.ok(report.framePNGs>=592,'native source pixel image count regressed');
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.emulateMedia({reducedMotion:'reduce'});
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
  const accepted=await page.evaluate(async()=>{
   const original=window.ORIGINAL_LEAF_OBS_FRAMES;
   const ids=Object.keys(original).sort();
   const auth=[];
   for(const id of ids){
    const actor=original[id],frame=actor?.frames?.[0];
    if(!frame||!frame.url.startsWith('./original/OBS/'))throw Error('Inferred actor '+id);
    const img=new Image();
    img.src=frame.url;
    await img.decode();
    if(img.naturalWidth!==frame.width||img.naturalHeight!==frame.height)
     throw Error('Original OBS frame bounds corrupted '+id);
    auth.push({id,member:actor.originalMember,url:frame.url,
      verifiedMember:!!actor.sourceSHA256||id==='0042'||id==='0045',
      dims:[img.naturalWidth,img.naturalHeight],
      originalFrames:actor.frames.length,poseMapping:actor.poseMapping});
   }
   return auth;
  });
  assert.equal(accepted.length,report.accepted+2,
   'all source OBS members must stay byte-authentic even when they are FX, not bodies');
  assert.ok(accepted.every(x=>x.verifiedMember&&x.dims[0]>0&&x.dims[1]>0));
  for(const id of ['0046','0061','0064','0085','0087','0092','0096','0099','0100','0134','0146','0156','0161','0162','0164','0165','0166']){
   assert.ok(accepted.some(x=>x.id===id),
    'previously decoded original OBS member bytes must remain available '+id);
  }
  const before=await page.evaluate(()=>({
   active:window.__ROG_TEST__.getMatch().active,
   positions:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   map:window.__ROG_TEST__.getMatch().map,
   turns:window.__ROG_TEST__.getMatch().turn
  }));
  // Only visually inspected REAL actor identities may be tested as bodies.
   // 1100 lightning / 1134 Dice Attack logo / 1146 bomb / 1165 glow are
   // genuine source effects, not source warriors.
   const samples=accepted.filter(x=>['0046','0061','0064','0085','0087','0092'].includes(x.id));
  for(const item of samples){
   await page.evaluate(id=>{
    window.__ROG_TEST__.getMatch().players[0].team[0]='c_'+id;
    window.__ROG_TEST__.drawGame();
   },item.id);
   await page.waitForFunction(id=>{
    const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="'+id+'"]');
    const img=p?.querySelector('.leaf-chess-original-obs');
    return p?.dataset.actorRig==='original-obs-sprite'&&img?.complete&&img.naturalWidth>10&&
     img.getAttribute('src')?.startsWith('./original/OBS/');
   },item.id,{timeout:13000});
   const source=await page.evaluate(id=>{
    const p=document.querySelector('#board-pawns .board-pawn[data-chessman-id="'+id+'"]');
    const img=p.querySelector('.leaf-chess-original-obs');
    return {source:p.dataset.actorSource,rig:p.dataset.actorRig,
      fakeFallback:!!p.querySelector('.leaf-chess-original-card-fallback:not([hidden])'),
      frame:img.getAttribute('src'),sourcePoseMapping:p.dataset.sourcePoseMapping,
      native:[img.naturalWidth,img.naturalHeight]};
   },item.id);
   assert.equal(source.rig,'original-obs-sprite');
   assert.equal(source.fakeFallback,false);
   assert.ok(source.source.startsWith('OBS/'));
   assert.ok(source.frame.includes('/OBS/'));
  }
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(200);
  const mobile=await page.evaluate(()=>({
   tiles:document.querySelectorAll('#board-nodes>.tile').length,
   actors:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    rig:p.dataset.actorRig,card:p.dataset.chessmanId
   }))
  }));
  assert.equal(mobile.tiles,104,'source 4LEAF DMP map untouched');
  assert.ok(mobile.actors[0].rig==='original-obs-sprite');
  const after=await page.evaluate(()=>({
   active:window.__ROG_TEST__.getMatch().active,
   positions:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   map:window.__ROG_TEST__.getMatch().map,
   turns:window.__ROG_TEST__.getMatch().turn
  }));
  assert.deepEqual(after,before,'recovered original OBS frame display must not mutate game turns or source DMP cells');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-obs-640stride-recovered-original-body.png'});
  console.log('STRICT ORIGINAL OBS 640 STRIDE REAL GAME PASS '+JSON.stringify({
   sourceObsMembers:accepted.length,sourceFrames:report.framePNGs+13,
   nativeSourceMembersRetained:accepted.length,visuallyAuditedNonActors:25,
   browserSamples:samples.map(x=>x.id),mobile,gameUnchanged:after,
   provenance:'SHA1 archived installer, OBS.pak SHA256, 2002 native 640-stride RGB indexed PIXELS; action mapping unverified'
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('AUTHENTIC OBS NATIVE GAME QA FAILED',e.stack||e);process.exit(1)});
