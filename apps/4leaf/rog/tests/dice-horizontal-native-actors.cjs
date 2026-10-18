'use strict';
/* 2026-10-18 actual phone screenshot regression. The original TIS pixels
 * are 145x97; no adjacent horizontal/vertical DMP source cell may overlap
 * in the rendered board. The default match must show genuine OBS bodies,
 * never giant 112px CSS chessmen. No 2002 MVE claim is made.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},
   deviceScaleFactor:2,isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&
   window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes>.tile')]
   .length===104&&[...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')]
   .length===2,null,{timeout:15000});
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')]
   .every(el=>el.complete&&el.naturalWidth>15),null,{timeout:15000});
  const proof=await page.evaluate(()=>{
   const camera=window.__LEAF_CAMERA__.getState();
   const board=[...document.querySelectorAll('#board-nodes>.tile')];
   const actors=[...document.querySelectorAll('#board-pawns .board-pawn')];
   const source=window.ORIGINAL_LEAF_MAPS['0172'];
   const dims=board.map(t=>({x:Number(t.dataset.dmpX),y:Number(t.dataset.dmpY),
    rect:t.getBoundingClientRect(),index:Number(t.dataset.tile),
    native:[t.offsetWidth,t.offsetHeight]}));
   const horizontal=[],vertical=[];
   for(let i=0;i<dims.length;i++)for(let j=0;j<i;j++){
    const a=dims[i],b=dims[j],dx=Math.abs(a.x-b.x),dy=Math.abs(a.y-b.y);
    if(dx===1&&dy===0)horizontal.push({
     ids:[a.index,b.index],gap:Math.abs(a.rect.x-b.rect.x)-a.rect.width});
    if(dx===0&&dy===1)vertical.push({
     ids:[a.index,b.index],gap:Math.abs(a.rect.y-b.rect.y)-a.rect.height});
   }
   return {
    count:board.length,sourceCells:source.length,
    area:document.querySelector('#board-area').getBoundingClientRect().width,
    size:camera.size,pitch:camera.projectedPitch,
    sourceGrid:camera.sourceGrid,
    actors:actors.map(p=>({
     id:p.dataset.chessmanId,rig:p.dataset.actorRig,
     source:p.dataset.actorSource,
     cssRigVisible:getComputedStyle(p.querySelector('.leaf-chess-actor')).display,
     native:p.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
     nativeReady:p.querySelector('.leaf-chess-original-obs')?.naturalWidth>15
    })),
    horizontal,vertical,
    nativeSizes:dims.every(x=>x.native[0]===145&&x.native[1]===97),
    originalTileCount:board.filter(t=>t.dataset.tisAlpha==='ready').length,
    fakeBodies:document.querySelectorAll('#board-pawns .board-pawn[data-actor-rig="inferred-8head"]').length,
    fakeCards:document.querySelectorAll('#board-pawns .leaf-chess-original-card-fallback:not([hidden])').length
   };
  });
  assert.equal(proof.count,104,'real DMP still has 104 interactive cells');
  assert.equal(proof.sourceCells,104);
  assert.ok(proof.nativeSizes,'all tile artwork has exact source 145x97 dimensions');
  assert.ok(proof.horizontal.length>=10,'actual horizontal DMP source neighbors audited');
  assert.ok(proof.vertical.length>=10,'actual vertical DMP source neighbors audited');
  assert.ok(proof.horizontal.every(x=>x.gap>0),
   'screenshot regression: 145px horizontal neighbors must NOT overlap '+JSON.stringify(proof.horizontal.filter(x=>x.gap<=0)));
  assert.ok(proof.vertical.every(x=>x.gap>0),
   '97px vertical neighbors must NOT overlap');
  assert.ok(proof.pitch.x>=145&&proof.pitch.y>=97,
   'DMP source artwork cannot be more tightly pitched than its real dimensions');
  assert.equal(proof.actors.length,2,'no bogus non-player actor');
  assert.ok(proof.actors.every(a=>a.rig==='original-obs-sprite'&&
    a.cssRigVisible==='none'&&a.native?.includes('/OBS/')&&a.nativeReady),
   'default human and opponent MUST both render genuine recovered Genesis OBS sprites');
  assert.equal(proof.fakeBodies,0,'the giant default fake stickman is gone');
  assert.equal(proof.fakeCards,0,'default players need no source-missing card fallback');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-iphone-original-board-no-overlap.png'});
  console.log('IPHONE ORIGINAL BOARD NONOVERLAP + AUTHENTIC OBS PASS',JSON.stringify({
   tiles:proof.count,pitch:proof.pitch,source:proof.sourceGrid,
   horizontal:proof.horizontal.length,vertical:proof.vertical.length,
   minHorizontalGap:Math.min(...proof.horizontal.map(x=>x.gap)),
   minVerticalGap:Math.min(...proof.vertical.map(x=>x.gap)),
   chessmen:proof.actors
  }));
 }finally{await browser.close()}
})().catch(error=>{console.error('IPHONE 4LEAF REGRESSION FAILED',error.stack||error);process.exit(1)});
