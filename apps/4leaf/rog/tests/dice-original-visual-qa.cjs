'use strict';
/* Persistent UI comparison frame: exact 800x600 source game, no UI mock.
 * A JPEG base64 source audit is included in CI logs ONLY so investigators
 * can compare original 2004 board.jpg against actual Chromium output.
 * This screenshot is NOT displayed as an in-game background.
 */
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,serviceWorkers:'block'});
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+require('node:path').resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOURCE_ROLL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>[...document.querySelectorAll('#game #board-nodes .tile')].every(x=>x.dataset.tisAlpha==='ready'),null,{timeout:20000});
  await page.waitForTimeout(550);
  const game=page.locator('#app');
  const size=await game.evaluate(el=>{const r=el.getBoundingClientRect();return {w:r.width,h:r.height}});
  if(Math.abs(size.w-800)>3||Math.abs(size.h-600)>3)throw Error('original fixed UI 800x600 missing');
  const audit=await page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes .tile')];
   const source=document.querySelector('#board-world');
   const r=source.getBoundingClientRect();
   return {
    tileCount:tiles.length,
    worldBox:[r.x,r.y,r.width,r.height],
    orientation:getComputedStyle(tiles[0]).transform,
    alphaReady:tiles.filter(x=>x.dataset.tisAlpha==='ready').length,
    clipping:tiles[0].style.clipPath,
    tiles:tiles.slice(0,9).map(x=>({
      tile:x.dataset.tile,id:x.dataset.originalArt,x:x.dataset.dmpX,y:x.dataset.dmpY,
      left:x.style.left,top:x.style.top,
      z:Number(x.style.zIndex),image:getComputedStyle(x).backgroundImage.slice(-45)
    }))
   };
  });
  const img=await game.screenshot({type:'jpeg',quality:70,animations:'disabled',timeout:18000});
  console.log('SOURCE_SCREENSHOT_QA '+JSON.stringify(audit));
  console.log('SOURCE_SCREENSHOT_JPEG_BASE64 '+img.toString('base64'));
  console.log('SOURCE_SCREENSHOT_END');
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE SCREENSHOT QA ERROR',e.stack||e);process.exit(1)});
