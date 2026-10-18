'use strict';
/* Source TIS platform opacity QA, not a historical MVE 3D mesh claim.
 * Pixel-by-pixel inspect ALL extracted 145x97 source PNGs in real Chromium.
 * The clickable polygon must NEVER crop a nontransparent original pixel,
 * especially at top/bottom rows or antialiased decorative edges.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const errors=[];
  page.on('pageerror',error=>errors.push(String(error)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
    'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
   window.__LEAF_TIS_ALPHA__&&window.ORIGINAL_LEAF_TILE_ART);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes>.tile')]
   .every(e=>e.dataset.tisAlpha==='ready'),null,{timeout:25000});
  const report=await page.evaluate(async()=>{
   const ids=Object.keys(window.ORIGINAL_LEAF_TILE_ART.tiles);
   const shapes=[];
   const intersects=(poly,y)=>{
    const xs=[];
    for(let i=0;i<poly.length;i++){
     const a=poly[i],b=poly[(i+1)%poly.length];
     if((a.y<=y&&b.y>y)||(b.y<=y&&a.y>y))
      xs.push(a.x+(y-a.y)*(b.x-a.x)/(b.y-a.y));
    }
    return xs.sort((a,b)=>a-b);
   };
   for(const id of ids){
    const entry=await window.__LEAF_TIS_ALPHA__.prepare(id);
    if(!entry.clip)throw Error('Original source has no clip polygon: '+id);
    const points=entry.clip.slice(8,-1).split(',').map(entry=>{
     const [x,y]=entry.trim().split(/\s+/);
     return {x:Number.parseFloat(x)*145/100,y:Number.parseFloat(y)*97/100};
    });
    const img=new Image();
    img.src=entry.url;
    await img.decode();
    const canvas=document.createElement('canvas');
    canvas.width=145;canvas.height=97;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(img,0,0);
    const pixels=ctx.getImageData(0,0,145,97).data;
    let opaque=0,clipped=0,top=0,bottom=0;
    const failing=[];
    for(let y=0;y<97;y++){
     const xs=intersects(points,y+.5);
     for(let x=0;x<145;x++){
      const alpha=pixels[(y*145+x)*4+3];
      if(!alpha)continue;
      opaque++;
      if(y<=2)top++;
      if(y>=94)bottom++;
      let inside=false;
      for(let k=0;k+1<xs.length;k+=2)
       if(x+.5>=xs[k]-.025&&x+.5<=xs[k+1]+.025)inside=true;
      if(!inside){clipped++;if(failing.length<5)failing.push([x,y,alpha]);}
     }
    }
    shapes.push({id,opaque,clipped,top,bottom,vertices:points.length,
     removed:entry.removed,failing});
   }
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   return {images:shapes,tiles:tiles.length,
    syntheticOverlayCount:document.querySelectorAll('#board-nodes>.tile small, #board-nodes>.tile .tile-symbol').length,
    allSourceTilesUnobscured:tiles.every(t=>t.dataset.originalArt&&
      t.getAttribute('aria-label')===t.title&&t.title.includes('칸 · ')&&
      !t.querySelector('small,.tile-symbol')),
    preservedOrientation:tiles.every(t=>getComputedStyle(t).transform.startsWith('matrix(1, 0, 0, -1,')),
    sourceSize:tiles.every(t=>t.offsetWidth===145&&t.offsetHeight===97)};
  });
  assert.ok(report.images.length>=30,'audit every recovered TIS entry, not a single sample');
  assert.equal(report.tiles,104,'true source 104-cell playable board kept');
  assert.equal(report.syntheticOverlayCount,0,'source pictures must not be covered by invented numbered tiles');
  assert.ok(report.allSourceTilesUnobscured,'all game events and hover labels remain identifiable');
  assert.ok(report.preservedOrientation,'prior confirmed original TIS upright orientation survives');
  assert.ok(report.sourceSize,'never scale the 145x97 source artwork');
  assert.ok(report.images.every(i=>i.opaque>350&&i.vertices>=50),'each source platform was actually decoded and traced');
  const truncated=report.images.filter(i=>i.clipped>0);
  assert.deepEqual(truncated,[],'native alpha clip must contain ALL nontransparent source image pixels');
  assert.deepEqual(errors,[],'no source image error in live browser');
  await page.screenshot({path:'leaf-board-native-unclipped-original-tiles.png'});
  console.log('NATIVE ORIGINAL TIS FULL-ALPHA OUTLINE PASS',JSON.stringify({
   sprites:report.images.length,tiles:report.tiles,
   totalOpaque:report.images.reduce((sum,i)=>sum+i.opaque,0),
   croppedSourcePixels:report.images.reduce((sum,i)=>sum+i.clipped,0),
   syntheticOverlays:report.syntheticOverlayCount,
   topEdgeOpaque:report.images.reduce((sum,i)=>sum+i.top,0),
   bottomEdgeOpaque:report.images.reduce((sum,i)=>sum+i.bottom,0)
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL TIS OUTLINE QA FAILED',e.stack||e);process.exit(1)});
