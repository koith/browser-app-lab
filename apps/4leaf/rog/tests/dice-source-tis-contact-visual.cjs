'use strict';
/* Same-state before/after archival 145x97 TIS edge and recovered OBS
 * footing. The original 2002 MVE 3D camera/shadow caster is NOT decoded.
 * Do not count WEB render halo removal as proof of original camera fidelity.
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
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_TIS_ALPHA__&&
   window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes>.tile').length===104&&
   [...document.querySelectorAll('#board-nodes>.tile')].every(t=>t.dataset.tisAlpha==='ready')&&
   [...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')].length===2&&
   [...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')]
    .every(img=>img.complete&&img.naturalWidth>10),null,{timeout:20000});
  const original=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();
   return {tiles:match.tiles.slice(),position:match.players.map(p=>p.position),
    original:document.querySelector('#board-nodes>.tile')?.dataset.originalArt};
  });
  const legacyCss=`
   #app.app-classic-dice #game .board-world #board-nodes
     .tile[data-native-tis-size="145x97"]{
    filter:drop-shadow(2px 7px 3px #090e28b3)!important;
   }
   #app.app-classic-dice #game .board-world #board-nodes
     .tile[data-native-tis-size="145x97"].player-here{
    filter:drop-shadow(0 0 4px #bcefffaa)
      drop-shadow(2px 6px 4px #191a3aba)!important;
   }
   #app.app-classic-dice #game .board-world #board-nodes
     #board-pawns .board-pawn::before{
    left:15px!important;bottom:6px!important;width:36px!important;
    transform:none!important;
   }`;
  await page.evaluate(css=>{
   const legacy=document.createElement('style');
   legacy.id='qa-legacy-web-halo';legacy.textContent=css;
   document.head.append(legacy);
  },legacyCss);
  await page.screenshot({path:'leaf-tis-obs-source-contact-before.png'});
  await page.evaluate(()=>document.getElementById('qa-legacy-web-halo').remove());
  const measure=()=>page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   const pawns=[...document.querySelectorAll('#board-pawns .board-pawn')];
   return {
    tiles:tiles.map(t=>({w:t.offsetWidth,h:t.offsetHeight,
     alpha:t.dataset.tisAlpha,filter:getComputedStyle(t).filter,
     dmp:[Number(t.dataset.dmpX),Number(t.dataset.dmpY)],art:t.dataset.originalArt})),
    pawns:pawns.map(p=>{
     const img=p.querySelector('.leaf-chess-original-obs');
     const f=window.ORIGINAL_LEAF_OBS_FRAMES[p.dataset.chessmanId]
      ?.frames.find(f=>f.index===Number(p.dataset.actorFrame));
     const shadow=getComputedStyle(p,'::before');
     const root=getComputedStyle(p);
     return {
      id:p.dataset.id,member:p.dataset.chessmanId,
      source:p.dataset.actorSource,pose:p.dataset.actorPose,
      frame:Number(p.dataset.actorFrame),
      actualSourceWidth:f?.width,sourceOriginal:f?.url,
      cssNativeWidth:img?.style.getPropertyValue('--leaf-obs-width'),
      nativeReady:img?.complete&&img?.naturalWidth>0,
      footprint:p.dataset.sourceContactWidth,
      provenance:p.dataset.sourceContactFootprint,
      cssFootprint:shadow.width,cssGround:shadow.bottom,
      cssLeft:shadow.left,cssTransform:shadow.transform,
      pawnWidth:root.width,
      shadowBackground:shadow.backgroundImage,
      shadowBorder:shadow.borderStyle,
      sourceFootOffset:p.dataset.sourceFootOffset,
      sourceGrounding:p.dataset.sourceGrounding
     };
    })
   };
  });
  const desktop=await measure();
  assert.equal(desktop.tiles.length,104,'native source DMP match unchanged');
  assert.ok(desktop.tiles.every(t=>t.w===145&&t.h===97&&t.alpha==='ready'&&
    t.filter==='none'),'real TIS art cannot bleed WEB shadow beyond its own original RGBA pixel bounds');
  assert.ok(desktop.pawns.every(p=>p.nativeReady&&p.source.includes('OBS/')),
   'native chessman source body must remain on the board');
  for(const actor of desktop.pawns){
   assert.equal(actor.provenance,'inferred-shadow-width/from-original-OBS-frame');
   const w=Math.max(18,Math.min(84,Math.round(actor.actualSourceWidth*.72)));
   assert.equal(actor.footprint,String(w),'contact width derives from genuine OBS source metadata');
   assert.equal(actor.cssFootprint,w+'px','actual visible shadow scales to original sprite');
   assert.ok(Math.abs(parseFloat(actor.cssGround)-(14.88-5))<.12,
    'contact ellipse center must align with shared source foot ground');
   assert.equal(actor.shadowBorder,'none','no fake portal ring may reappear');
   assert.match(actor.shadowBackground,/radial-gradient/);
   assert.match(actor.sourceGrounding,/inferred-shared-foot-plane/);
  }
  await page.screenshot({path:'leaf-tis-obs-source-contact-after.png'});
  // Exercise the two ends of original OBS body widths, not one arbitrary
  // WEB size for every 2002 character. Same exact source TIS cell & match.
  const variants=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),out=[];
   for(const id of ['0046','0092']){
    m.players[0].team[0]='c_'+id;
    window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const img=pawn.querySelector('.leaf-chess-original-obs');
    const first=window.ORIGINAL_LEAF_OBS_FRAMES[id].frames.find(f=>f.index===0);
    out.push({id,source:first.width,footprint:parseFloat(getComputedStyle(pawn,'::before').width),
      expected:Math.max(18,Math.min(84,Math.round(first.width*.72))),
      member:pawn.dataset.actorSource,alpha:document.querySelector('#board-nodes>.tile').dataset.tisAlpha,
      img:img.getAttribute('src')});
   }
   return out;
  });
  assert.ok(variants[0].footprint<variants[1].footprint,'actual small/wide original bodies must not share a made-up contact ring');
  assert.ok(variants.every(x=>x.footprint===x.expected&&x.member.includes('/OBS/')&&
   x.img?.includes('/OBS/')&&x.alpha==='ready'));
  await page.setViewportSize({width:390,height:844});
  const mobile=await measure();
  assert.equal(mobile.tiles.length,104,'iPhone did not lose genuine 26-DMP source cells');
  assert.ok(mobile.tiles.every(t=>t.w===145&&t.h===97&&t.filter==='none'));
  await page.screenshot({path:'leaf-tis-obs-source-contact-iphone.png'});
  const final=await page.evaluate(()=>({
   positions:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   selectedArt:document.querySelector('#board-nodes>.tile')?.dataset.originalArt
  }));
  assert.deepEqual(final.positions,original.position,'visual TIS/shadow cleanup never moves real game state');
  assert.equal(final.selectedArt,original.original,'original PNG identity preserved');
  assert.deepEqual(errors,[],'no script failure during native TIS and OBS shadow QA');
  console.log('4LEAF NATIVE TIS EDGE BLEED + OBS CONTACT PASS '+JSON.stringify({
   tiles:desktop.tiles.length,sourceDimensions:[145,97],
   projection:'150x100-WEB/2002-MVE-UNVERIFIED',
   before:'legacy external glow/shadow photographed same state',
   after:'source RGBA only; no invented outside shadow',
   nativeContact:desktop.pawns.map(p=>({id:p.member,width:p.actualSourceWidth,footprint:p.footprint})),
   variants,mobileTiles:mobile.tiles.length
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error('NATIVE TIS/OBS CONTACT VISUAL FAILED',e.stack||e);process.exit(1);});
