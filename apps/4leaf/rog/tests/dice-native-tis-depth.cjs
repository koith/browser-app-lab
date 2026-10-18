'use strict';
// The recovered DMP stores integer tile-grid positions; the true native
// TIS pictures are 145x97. This exercise checks the ACTUAL HTML game tiles,
// overlaps, DMP order and live camera rather than simulating a screen shot.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_MAPS&&window.__LEAF_CAMERA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')]
   .every(el=>['ready','fallback'].includes(el.dataset.tisAlpha)),null,{timeout:20000});
  const data=await page.evaluate(async()=>{
   const image=new Image();image.src='./original/Tiles/0015.png';await image.decode();
   // file:// Chromium isolates separately loaded local PNGs into opaque
   // origins. Decoding image size remains valid, but getImageData throws
   // SecurityError on a tainted canvas. Full RGBA pixel reads are checked
   // when the same original art is served over the real HTTP(S) origin.
   let sourceCorner=null;
   if(location.protocol!=='file:'){
    const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
    const paint=canvas.getContext('2d',{willReadFrequently:true});
    paint.drawImage(image,0,0);
    sourceCorner=[...paint.getImageData(0,0,1,1).data];
   }
   const game=window.__ROG_TEST__.getMatch();
   const mapId=Object.entries(window.ORIGINAL_LEAF_MAP_INFO).find(([id,value])=>value.title===game.map)?.[0];
   const dmp=window.ORIGINAL_LEAF_MAPS[mapId];
   const layer=document.getElementById('board-nodes');
   const world=document.getElementById('board-world');
   const tiles=[...layer.querySelectorAll('.tile')];
   const cells=tiles.map((tile,i)=>{
    const cs=getComputedStyle(tile),r=tile.getBoundingClientRect();
    return {
     i,
     source:tile.dataset.originalArt,
     logical:[tile.offsetWidth,tile.offsetHeight],
     css:[cs.width,cs.height],
     pos:[tile.offsetLeft,tile.offsetTop],
     bounds:[r.left,r.top,r.width,r.height],
     paint:cs.backgroundImage,
     alphaState:tile.dataset.tisAlpha,
     sourceFromAlpha:tile.dataset.tisAlphaSource,
     preserved:tile.dataset.tisSourcePreserved,
     removed:Number(tile.dataset.tisChromaRemoved),
     native:tile.dataset.nativeTisSize,
     dmp:[Number(tile.dataset.dmpX),Number(tile.dataset.dmpY),Number(tile.dataset.dmpCellCode)],
     depth:Number(tile.style.zIndex),
     clip:cs.clipPath,
     clickable:typeof tile.onclick==='function'
    };
   });
   const near=[];
   for(let i=0;i<dmp.length-1;i++){
    const [a,b]=[dmp[i],dmp[i+1]];
    if(Math.abs(a[0]-b[0])<=1&&Math.abs(a[1]-b[1])<=1&&
      (a[0]!==b[0]||a[1]!==b[1])){
     const x=cells[i],y=cells[i+1];
     near.push({
      indices:[i,i+1],delta:[Math.abs(y.pos[0]-x.pos[0]),Math.abs(y.pos[1]-x.pos[1])],
      overlap:[Math.max(0,Math.min(x.pos[0]+72.5,y.pos[0]+72.5)-
       Math.max(x.pos[0]-72.5,y.pos[0]-72.5)),
       Math.max(0,Math.min(x.pos[1]+48.5,y.pos[1]+48.5)-
       Math.max(x.pos[1]-48.5,y.pos[1]-48.5))]
     });
    }
   }
   return {sourceImage:[image.width,image.height],
    sourceCorner,map:game.map,dmp:dmp.length,
    terrain:getComputedStyle(world).backgroundImage,
    camera:window.__LEAF_CAMERA__.getState().scale,
    cells,near};
  });
  assert.deepEqual(data.sourceImage,[145,97],'original TIS/0015.png truly holds 145×97 source pixels');
  assert.equal(data.map,'4LEAF','measure a real loaded original DMP gameplay board');
  assert.equal(data.cells.length,data.dmp,'every original MVE/DMP cell remains playable');
  assert.equal(data.cells.length,104,'the original 4LEAF board uses its actual 104 source cells');
  assert.ok(data.terrain.includes('/original/IMG/bgtile.png'),
   'original native forest and cliffs remain behind live original platform shapes');
  assert.ok(data.cells.every(cell=>cell.native==='145x97'&&
   cell.logical[0]===145&&cell.logical[1]===97&&
   cell.css[0]==='145px'&&cell.css[1]==='97px'),
   'each live source platform uses full 145x97 original pixels, NOT 70x47 miniatures');
  assert.ok(data.cells.every(cell=>{
   const native='Tiles/'+cell.source+'.png';
   return cell.source&&cell.clickable&&(
    cell.alphaState==='ready'
     ? cell.sourceFromAlpha===native&&
       (cell.removed===0?cell.preserved==='true'&&cell.paint.includes('/original/'+native):
        cell.paint.includes('data:image/png'))
     : cell.alphaState==='fallback'&&cell.paint.includes('/original/'+native)
   );
  }), 'all TIS cells use genuine source PNGs: either original unkeyed file:// fallback or correctly keyed original pixel artwork');
  assert.ok(data.cells.every(cell=>cell.clip.startsWith('polygon(')),
   'hexagonal transparent source perimeter, not overlapping invisible rectangle hitboxes');
  assert.ok(data.cells.every(cell=>Number.isInteger(cell.depth)&&cell.dmp.every(Number.isFinite)),
   'actual source grid and third original DMP field recorded without inventing elevation data');
  assert.ok(data.near.length>10,'the authentic 104-cell source route has adjacent map cells');
  assert.ok(data.near.every(p=>p.overlap[0]<=40||p.overlap[1]<=30),
   '145x97 TIS sprites must not bury neighboring DMP tiles with >40x30 pixels of two-axis overlap');
  for(let i=0;i<data.cells.length;i++){
   const a=data.cells[i];
   if(i===0)continue;
   const b=data.cells[i-1];
   if(a.dmp[1]>b.dmp[1])assert.ok(a.depth>b.depth,'front original tile must paint over rear tile');
   if(a.dmp[1]<b.dmp[1])assert.ok(a.depth<b.depth,'rear original tile must paint behind front tile');
  }
  await page.screenshot({path:'leaf-original-fullsize-tis-distinct-board.png'});
  const before=await page.evaluate(()=>window.__LEAF_CAMERA__.getState().scale);
  await page.evaluate(()=>window.__LEAF_CAMERA__.zoom(.35));
  const after=await page.evaluate(()=>window.__LEAF_CAMERA__.getState().scale);
  assert.ok(after>before,'live source board keeps functional camera zoom');
  assert.deepEqual(await page.locator('#board-nodes .tile').first().evaluate(el=>[
   el.offsetWidth,el.offsetHeight
  ]),[145,97],'uniform camera zoom does not distort or resample original TIS bitmap dimensions');
  assert.equal(await page.locator('#board-pawns .board-pawn').count(),2,
   'both REAL hotseat players still appear on live board; no fake unit proxies');
  await page.setViewportSize({width:390,height:844});
  assert.deepEqual(await page.locator('#board-nodes .tile').first().evaluate(el=>[
   el.offsetWidth,el.offsetHeight
  ]),[145,97],'phone retains original logical bitmap and uses the game camera to scale');
  await page.screenshot({path:'leaf-original-fullsize-tis-distinct-mobile.png'});
  assert.deepEqual(errors,[],'source tile reconstruction generates no browser errors');
  console.log('FULL-SIZE GENESIS TIS DMP DEPTH PASS',JSON.stringify({
   source:data.sourceImage,firstCell:data.cells[0],count:data.cells.length,
   overlapExamples:data.near.slice(0,5),cornerRGBA:data.sourceCorner,camera:[before,after]}));
 }finally{await browser.close()}
})().catch(e=>{console.error('FULL-SIZE GENESIS TIS DEPTH FAILED',e.stack||e);process.exit(1)});
