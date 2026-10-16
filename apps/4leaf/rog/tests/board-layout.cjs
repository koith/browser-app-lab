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
   const result=await page.evaluate(()=>{
    const tiles=[...document.querySelectorAll('#board-nodes .tile')];
    const sizes=tiles.map(e=>{const c=getComputedStyle(e);return {
     w:parseFloat(c.width),h:parseFloat(c.height),transform:c.transform,
     background:c.backgroundImage,clip:c.clipPath,native:e.dataset.nativeTisSize,
     dmp:[Number(e.dataset.dmpX),Number(e.dataset.dmpY),Number(e.dataset.dmpCellCode)],
     depth:Number(e.style.zIndex)
    }});
    const pts=tiles.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top)}));
    const world=document.querySelector('#board-world');const width=world.clientWidth,height=world.clientHeight;
    let bad=0,adjacent=0;
    for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
     const dx=Math.abs(pts[i].x-pts[j].x)*width/100,dy=Math.abs(pts[i].y-pts[j].y)*height/100;
     if(dx<.01&&dy<.01)continue;
     if(dx<70.01&&dy<47.01){adjacent++;if(dx<69.5&&dy<46.5)bad++}
    }
    return {count:tiles.length,sizes,adjacent,bad};
   });
   assert.ok(result.count>40,'original map contains game tiles');
   // Native TIS bitmap footprint is VERIFIED 145x97. The DMP center-to-
   // center pitch remains 70x47, so adjacent raised source platforms DO
   // overlap visually; the source grid positions must not collapse.
   assert.ok(result.sizes.every(t=>Math.abs(t.w-145)<.1&&Math.abs(t.h-97)<.1&&t.native==='145x97'),
    'all original TIS raised platforms retain true 145x97 source pixels');
   assert.ok(result.sizes.every(t=>t.transform==='matrix(1, 0, 0, 1, -72.5, -48.5)'||
      (t.transform.startsWith('matrix(1, 0, 0, 1,')&&t.transform.includes('-72.5'))),
    'source hex art keeps upright, centered geometry; no forced rotate/skew');
   assert.ok(result.sizes.every(t=>t.clip.startsWith('polygon(')),
    'inferred hit polygon restricts clicking transparent overlapping source corners');
   assert.ok(result.sizes.every(t=>t.dmp.every(Number.isFinite)&&Number.isFinite(t.depth)),
    'real DMP coordinates and 2D front/back order retained for each independent TIS');
   assert.ok(result.sizes.every(t=>t.background.includes('original/Tiles/')),'all tiles show original TIS artwork');
   assert.equal(result.bad,0,'DMP grid centers retain native 70x47 spacing even though painted 145x97 sprites overlap');
   assert.ok(result.adjacent>10,'adjacent cells were checked');
   await page.screenshot({path:shot});
   await page.locator('#exit-game').click();
   await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
   console.log('BOARD LAYOUT PASS:',name,result.count,'tiles',result.adjacent,'neighbor comparisons');
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
