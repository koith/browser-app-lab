const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/');
  for(const [name,shot] of [['4LEAF','leaf-board-4leaf.png'],['악마의 달팽이','leaf-board-snail.png']]){
   await page.locator('[data-route="lobby"]').first().click();
   await page.locator('#lobby-create').click();
   await page.locator('#map-select').selectOption(name);
   await page.locator('#start-game').click();
   await page.waitForSelector('#game:not(.hidden)');
   await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')]
    .every(el=>el.dataset.tisAlpha==='ready'),null,{timeout:20000});
   const result=await page.evaluate(()=>{
    const tiles=[...document.querySelectorAll('#board-nodes .tile')];
    const sizes=tiles.map(e=>{const c=getComputedStyle(e);return {
     w:parseFloat(c.width),h:parseFloat(c.height),transform:c.transform,
     background:c.backgroundImage,clip:c.clipPath,native:e.dataset.nativeTisSize,
     source:e.dataset.originalArt,decodedSource:e.dataset.tisAlphaSource,
     alpha:e.dataset.tisAlpha,removed:Number(e.dataset.tisChromaRemoved),
     preserved:e.dataset.tisSourcePreserved,
     dmp:[Number(e.dataset.dmpX),Number(e.dataset.dmpY),Number(e.dataset.dmpCellCode)],
     depth:Number(e.style.zIndex)
    }});
    const pts=tiles.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top),
     dmpX:Number(e.dataset.dmpX),dmpY:Number(e.dataset.dmpY)}));
    const world=document.querySelector('#board-world');const width=world.clientWidth,height=world.clientHeight;
    const camera=window.__LEAF_CAMERA__.getState();
    let bad=0,adjacent=0,minimumH=Infinity,minimumV=Infinity;
    for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
     const a=pts[i],b=pts[j];
     const dx=Math.abs(a.x-b.x)*width/100,dy=Math.abs(a.y-b.y)*height/100;
     const horizontal=a.dmpY===b.dmpY&&Math.abs(a.dmpX-b.dmpX)===1;
     const vertical=a.dmpX===b.dmpX&&Math.abs(a.dmpY-b.dmpY)===1;
     if(horizontal||vertical){
      adjacent++;
      if(horizontal){minimumH=Math.min(minimumH,dx);if(Math.abs(dx-camera.projectedPitch.x)>1)bad++}
      if(vertical){minimumV=Math.min(minimumV,dy);if(Math.abs(dy-camera.projectedPitch.y)>1)bad++}
     }
    }
    return {count:tiles.length,sizes,adjacent,bad,minimumH,minimumV,
     sourceGrid:camera.sourceGrid,projectedPitch:camera.projectedPitch};
   });
   assert.ok(result.count>40,'original map contains game tiles');
   // Source DMP 70x47 is LOGICAL grid metadata, not a mandate to pack
   // full 145x97 sprite billboards every 70x47 physical screen pixels.
   // Live WEB projection avoids 50%-buried tiles while preserving native
   // source filenames, coordinates, artwork dimensions and game routes.
   assert.ok(result.sizes.every(t=>Math.abs(t.w-145)<.1&&Math.abs(t.h-97)<.1&&t.native==='145x97'),
    'all original TIS raised platforms retain true 145x97 source pixels');
   // The archived extractor already applied FLIP_TOP_BOTTOM to
   // the source TIS rows. The live scene corrects that preview inversion
   // while retaining authentic source PNG bytes and hit polygons.
   assert.ok(result.sizes.every(t=>t.transform.startsWith('matrix(1, 0, 0, -1,')),
    'all 145x97 original TIS previews render source lettering upright');
   assert.ok(result.sizes.every(t=>t.clip.startsWith('polygon(')),
    'inferred hit polygon restricts clicking transparent overlapping source corners');
   assert.ok(result.sizes.every(t=>t.dmp.every(Number.isFinite)&&Number.isFinite(t.depth)),
    'real DMP coordinates and 2D front/back order retained for each independent TIS');
   assert.ok(result.sizes.every(t=>t.alpha==='ready'&&
    t.decodedSource==='Tiles/'+t.source+'.png'&&
    (t.removed===0?t.preserved==='true'&&t.background.includes('/original/Tiles/'+t.source+'.png'):
     t.background.includes('data:image/png'))),
    'all tiles show their independently decoded recovered TIS PNG, not a fake or an unkeyed source');
   assert.deepEqual(result.sourceGrid,{width:1450,height:1120,pitchX:70,pitchY:47});
   assert.equal(result.bad,0,'every source DMP neighboring position uses projected sprite pitch');
   assert.ok(result.minimumH>140&&result.minimumV>95,
    '145x97 native tiles no longer visually bury adjacent path nodes: '+JSON.stringify(result));
   assert.ok(result.adjacent>10,'adjacent cells were checked');
   await page.screenshot({path:shot});
   await page.locator('#exit-game').click();
   await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
   console.log('BOARD LAYOUT PASS:',name,result.count,'tiles',result.adjacent,'neighbor comparisons');
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
