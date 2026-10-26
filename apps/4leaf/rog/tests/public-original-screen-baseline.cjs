'use strict';
/* Published, independently playable 4LEAF screenshot baseline.
 * Historical 2002-2004 reference: apps/4leaf/assets/board.jpg is an
 * 800x600 LIVE BATTLE, so a new two-player starting turn is NOT pixel-
 * equivalent. The comparison image is visual evidence, never game art.
 */
const {chromium,webkit}=require('playwright');
const {readFileSync,writeFileSync}=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const viewport=mobile?{width:390,height:844}:{width:1280,height:900};
 const page=await browser.newPage({viewport,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile').length===104);
  const geometry=await page.evaluate(()=>{
   const el=s=>document.querySelector(s);
   const box=s=>{const r=el(s).getBoundingClientRect();return {
    x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right};};
   const mini=el('#board-mini'),world=el('#board-world'),area=el('#board-area');
   const app=box('#app');
   return {app,area:box('#board-area'),mini:box('#board-mini'),
    miniParent:mini.parentElement.id,
    miniPosition:getComputedStyle(mini).position,
    worldRepeat:getComputedStyle(world).backgroundRepeat,
    areaRepeat:getComputedStyle(area).backgroundRepeat,
    worldImage:getComputedStyle(world).backgroundImage,
    worldSize:getComputedStyle(world).backgroundSize,
    miniImage:getComputedStyle(mini).backgroundImage,
    originalObs:document.querySelectorAll('#board-pawns .board-pawn[data-actor-rig="original-obs-sprite"]').length,
    actualPlayers:window.__ROG_TEST__.getMatch().players.length,
    cells:document.querySelectorAll('#board-nodes .tile').length};
  });
  assert.equal(geometry.cells,104,'original DMP game remains fully interactive');
  assert.equal(geometry.actualPlayers,2);
  assert.ok(geometry.originalObs>=1,'real OBS rather than a screenshot of actors');
  assert.ok(geometry.worldImage.includes('original/IMG/bgtile.png'),
   'the recovered terrain texture, not stock gradient or screenshot wallpaper');
  if(mobile){
   assert.equal(geometry.miniParent,'board-area','ONE original live minimap is on mobile game board');
   assert.equal(geometry.miniPosition,'absolute',
    'public 2026-10-26 regression: a source tab stylesheet moved minimap to top-left');
   assert.ok(geometry.mini.bottom>=geometry.area.bottom-8 &&
    geometry.mini.bottom<=geometry.area.bottom+2,
    'native minimap bottom is anchored to actual game lower-left; got '+JSON.stringify(geometry));
   assert.ok(Math.abs(geometry.mini.x-geometry.area.x)<8);
   assert.equal(geometry.worldRepeat,'no-repeat',
    'no repeated village/cliff seam every 485 pixels in portrait');
   assert.equal(geometry.areaRepeat,'no-repeat');
   assert.equal(geometry.worldSize,'auto 100%','unchanged 725x485 source proportionally covers portrait height');
   assert.ok(geometry.miniImage.includes('/original/IMG/minimap.png'));
  }else{
   assert.ok(Math.abs(geometry.app.width-800)<2&&Math.abs(geometry.app.height-600)<2);
   assert.equal(geometry.miniParent,'dice-native-minidock',
    '2004 source desk: real minimap must be immediately left of chat');
   assert.equal(geometry.worldRepeat,'repeat',
    'do not alter genuine 725x485 desktop panning scene');
   assert.equal(geometry.worldSize,'725px 485px');
  }
  await page.screenshot({path:'leaf-public-target-'+(mobile?'mobile-':'desktop-')+engine.name()+'.png'});
  if(!mobile){
   const current=await page.locator('#app').screenshot();
   const original=readFileSync(path.resolve(__dirname,'../../assets/board.jpg'));
   const meta=await browser.newPage({viewport:{width:1640,height:660},deviceScaleFactor:1});
   const esc=x=>x.replaceAll('&','&amp;').replaceAll('<','&lt;');
   await meta.setContent('<style>body{background:#13192e;color:#e6edff;font:14px Arial;margin:6px;}' +
    '.compare{display:flex;gap:12px}.compare img{display:block;width:800px;height:600px}' +
    '</style><div class="compare"><section>2004 ORIGINAL — battle state'+
    '<img src="data:image/jpeg;base64,'+original.toString('base64')+'"></section>'+
    '<section>DEPLOYED WEB — fresh 2-player board, SAME 800×600 frame'+
    '<img src="data:image/png;base64,'+current.toString('base64')+'"></section></div>');
   await meta.waitForFunction(()=>[...document.images].every(x=>x.complete&&x.naturalWidth===800));
   // Source screenshot is historical combat; current capture is a fresh
   // match, so these numeric per-ROI distances are EVIDENCE ONLY, never a
   // hard pass/fail target or a claim that client art is exact. Distinguish
   // stable HUD regions from incomparable dynamic battle/map areas.
   const comparison=await meta.evaluate(()=>{
    const [reference,current]=document.querySelectorAll('.compare img');
    const cvs=document.createElement('canvas');cvs.width=800;cvs.height=600;
    const ctx=cvs.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(reference,0,0,800,600);
    const original=ctx.getImageData(0,0,800,600).data;
    ctx.clearRect(0,0,800,600);ctx.drawImage(current,0,0,800,600);
    const deployed=ctx.getImageData(0,0,800,600).data;
    const regions=[
     {id:'historic-menu',x:96,y:0,w:608,h:30,comparable:true},
     {id:'historic-minimap',x:0,y:448,w:172,h:152,comparable:true},
     {id:'historic-chat-window',x:172,y:448,w:406,h:152,comparable:true},
     {id:'historic-tools-and-chessmen',x:578,y:448,w:222,h:152,comparable:true},
     {id:'battle-vs-fresh-board-INCOMPARABLE',x:96,y:30,w:608,h:418,comparable:false}
    ];
    return regions.map(r=>{
     let abs=0,total=0,greaterThan48=0,meanOriginal=[0,0,0],meanPublished=[0,0,0];
     for(let y=r.y;y<r.y+r.h;y++)for(let x=r.x;x<r.x+r.w;x++){
      const at=(y*800+x)*4;
      for(let c=0;c<3;c++){
       const av=original[at+c],bv=deployed[at+c];
       const delta=Math.abs(av-bv);abs+=delta;total++;
       if(delta>48)greaterThan48++;
       meanOriginal[c]+=av;meanPublished[c]+=bv;
      }
     }
     const n=r.w*r.h;
     return {...r,source:'original 800x600 JPG vs deployed 800x600 PNG',
      meanAbsoluteRgbDifference:Number((abs/total).toFixed(3)),
      fractionRgbChannelsDifferingOver48:Number((greaterThan48/total).toFixed(4)),
      meanOriginalRgb:meanOriginal.map(q=>Math.round(q/n)),
      meanPublishedRgb:meanPublished.map(q=>Math.round(q/n)),
      acceptance:'DIAGNOSTIC ONLY; dynamics/players/time differ, not historical sprite-perfect tolerance'};
    });
   });
   writeFileSync('leaf-original-vs-public-800x600-roi-evidence.json',
     JSON.stringify({viewport:[800,600],original:'apps/4leaf/assets/board.jpg',
      deployed:process.env.FOURLEAF_TEST_URL||'local PR',
      originalState:'battle',deployedState:'two-player first turn',
      benchmarkTrust:'source-region proximity diagnostic; NOT pixel-perfect state match',
      regions:comparison},null,2)+'\\n');
   console.log('HISTORICAL-PUBLISHED-ROI-MEASUREMENTS '+JSON.stringify(comparison));
   await meta.screenshot({path:'leaf-original-2004-vs-public-live-800x600.png'});
   await meta.close();
  }
  // The game still moves through true DMP cells after both DOM and scenery changes.
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,
    null,{timeout:25000});
  const after=await page.evaluate(()=>({move:window.__ROG_TEST__.getMatch().players[0].position,
   dice:window.__ROG_TEST__.getMatch().lastRoll}));
  assert.ok(after.move>before&&after.dice.length>0,'real move and dice preserved');
  assert.deepEqual(errors,[],'published browser has no game source exceptions');
  console.log('PUBLIC VISUAL BASELINE SOURCE-ANCHORED PASS '+JSON.stringify({
   engine:engine.name(),mobile,geometry,after}));
 }finally{await browser.close();}
})().catch(e=>{console.error('PUBLIC 4LEAF SOURCE BASELINE FAILED',e.stack||e);process.exit(1);});
