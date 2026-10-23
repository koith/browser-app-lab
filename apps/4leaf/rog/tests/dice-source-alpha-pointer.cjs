'use strict';
/* FL-07/08 original TIS source pixel acceptance.
 * This does not assert that the unrecovered 2002 MVE projection is matched.
 * It rejects false tile interactions in the transparent parts of authentic
 * 145x97 TIS PNGs, including the repaired vertical orientation and camera zoom.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_TIS_ALPHA__&&window.__LEAF_CAMERA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes>.tile')].length===104&&
    [...document.querySelectorAll('#board-nodes>.tile')].every(t=>t.dataset.tisAlpha==='ready'),
    null,{timeout:35000});

  // All 32 independently recovered 2002 TIS source bitmaps get decoded.
  // Compare pixel-accurate picks at 145x97, not a CSS polygon's bounds.
  const atlas=await page.evaluate(async()=>{
   const API=window.__LEAF_TIS_ALPHA__,ids=Object.keys(window.ORIGINAL_LEAF_TILE_ART.tiles);
   const probe=document.createElement('div');
   probe.style.cssText='position:fixed;left:250px;top:110px;width:145px;height:97px;transform:scaleY(-1);pointer-events:none;z-index:99999';
   document.body.append(probe);
   const rows=[];
   try{
    for(const id of ids){
     const frame=await API.prepare(id);
     probe.dataset.originalArt=id;
     const rect=probe.getBoundingClientRect();
     let opaque=0,transparent=0,mismatches=0,probes=0;
     // Exhaustive native source-alpha test plus subpixel mouse mapping probes.
     for(let y=0;y<97;y++)for(let x=0;x<145;x++){
      const alpha=frame.alpha[y*145+x];
      if(alpha)opaque++;else transparent++;
      if((x%7)||(y%5))continue;
      const clientX=rect.left+(x+.5)*rect.width/145;
      const clientY=rect.top+(96-y+.5)*rect.height/97;
      const hit=API.hitPoint(probe,clientX,clientY);
      probes++;
      if(!hit.ready||hit.source!==id||hit.x!==x||hit.y!==y||
        hit.alpha!==alpha||hit.hit!==(alpha>0)||!hit.inverted)mismatches++;
     }
     rows.push({id,opaque,transparent,mismatches,probes,native:frame.native,removed:frame.removed});
    }
   }finally{probe.remove();}
   return rows;
  });
  assert.ok(atlas.length>=30,'audit every actually recovered 2002 TIS');
  assert.ok(atlas.every(x=>x.opaque>100&&x.transparent>100),'original sprites must retain source transparency');
  assert.ok(atlas.every(x=>x.mismatches===0&&x.probes>200),
   'genuine original pixels MUST determine point hit after Y repair: '+JSON.stringify(atlas.filter(x=>x.mismatches)));
  // The topmost visible pixel of a vertically flipped source 145x97 tile
  // is source row 96, not invalid row 97. Matrix3d serialization must
  // produce the same result as scaleY(-1) on Safari/iPhone.
  const sourceEdgeProof=await page.evaluate(()=>{
   const API=window.__LEAF_TIS_ALPHA__;
   const probe=document.createElement('div');
   probe.style.cssText='position:fixed;left:250px;top:110px;width:145px;height:97px;pointer-events:none';
   probe.dataset.originalArt='0000';document.body.append(probe);
   const check=transform=>{
    probe.style.transform=transform;
    const rect=probe.getBoundingClientRect();
    const x=rect.left+rect.width/2;
    const top=API.hitPoint(probe,x,rect.top+rect.height*.000001);
    const bottom=API.hitPoint(probe,x,rect.bottom-rect.height*.000001);
    return [top.y,bottom.y,top.inverted,bottom.inverted];
   };
   try{return {flip:check('scaleY(-1)'),matrix3d:check(
    'matrix3d(1,0,0,0,0,-1,0,0,0,0,1,0,0,0,0,1)'),normal:check('none')};}
   finally{probe.remove();}
  });
  assert.deepEqual(sourceEdgeProof.flip,[96,0,true,true]);
  assert.deepEqual(sourceEdgeProof.matrix3d,[96,0,true,true]);
  assert.deepEqual(sourceEdgeProof.normal,[0,96,false,false]);
  const findPhysical=async()=>page.evaluate(()=>{
   const API=window.__LEAF_TIS_ALPHA__;
   const area=document.querySelector('#board-area').getBoundingClientRect();
   for(const tile of document.querySelectorAll('#board-nodes>.tile')){
    if(getComputedStyle(tile).visibility!=='visible')continue;
    const rect=tile.getBoundingClientRect();
    if(!rect.width||!rect.height)continue;
    for(let iy=3;iy<94;iy+=7)for(let ix=3;ix<142;ix+=7){
     const x=rect.left+(ix+.5)*rect.width/145;
     const y=rect.top+(96-iy+.5)*rect.height/97;
     if(x<area.left+3||x>area.right-3||y<area.top+3||y>area.bottom-3)continue;
     const el=document.elementFromPoint(x,y);
     if(el!==tile&&!tile.contains(el))continue;
     const hit=API.hitPoint(tile,x,y);
     if(hit.ready&&hit.hit)return {x,y,id:tile.dataset.tile,source:tile.dataset.originalArt,pixel:[hit.x,hit.y],rect:[rect.width,rect.height]};
    }
   }
   return null;
  });
  // Native camera/world layout can keep a short transition alive after
  // entering a game or changing viewport. A sampled DOM point from BEFORE
  // mouse.move may no longer be topmost when the physical click arrives.
  // Check the real hit target again after pointer movement; never replace
  // this with a synthetic event or mark the original sprite as clickable
  // just because the source-alpha math said so.
  const clickRealOpaque=async phase=>{
   const attempts=[];
   for(let n=0;n<4;n++){
    await page.waitForTimeout(n===0?350:220);
    const point=await findPhysical();
    if(!point){attempts.push({reason:'no-visible-original-pixel'});continue;}
    await page.mouse.move(point.x,point.y);
    const aligned=await page.evaluate(info=>{
     const tile=document.querySelector('#board-nodes>.tile[data-tile="'+info.id+'"]');
     const top=document.elementFromPoint(info.x,info.y);
     const source=tile?window.__LEAF_TIS_ALPHA__.hitPoint(tile,info.x,info.y):null;
     return {topmost:!!tile&&(top===tile||tile.contains(top)),
      hit:source?.hit,ready:source?.ready,alpha:source?.alpha,
      actualTop:top?.id||String(top?.className||'').slice(0,70)};
    },point);
    if(!aligned.topmost||!aligned.hit||!aligned.ready){
     attempts.push({point,aligned,reason:'camera-or-foreground-moved'});
     continue;
    }
    await page.mouse.down();await page.mouse.up();
    const actual=await page.evaluate(id=>{
     const tile=document.querySelector('#board-nodes>.tile[data-tile="'+id+'"]');
     return {hit:tile?.dataset.sourcePixelHit,coords:[
      tile?.dataset.sourceHitX,tile?.dataset.sourceHitY]};
    },point.id);
    if(actual.hit==='true')return {...point,actual,attempts:n+1,phase};
    attempts.push({point,aligned,actual,reason:'original-pixel-click-not-delivered'});
   }
   throw Error('Real '+phase+' original TIS mouse failed after verifying topmost pixels: '+
    JSON.stringify(attempts));
  };
  const first=await clickRealOpaque('desktop');
  // An artificial MouseEvent sent to a tile's transparent source pixel is
  // intentionally rejected, not reported as a tile interaction. Keyboard
  // .click() is explicitly exempt to keep native tab/button accessibility.
  const synthetic=await page.evaluate(()=>{
   const tile=document.querySelector('#board-nodes>.tile');
   const API=window.__LEAF_TIS_ALPHA__,rect=tile.getBoundingClientRect();
   const find=(want)=>{
    for(let y=0;y<97;y++)for(let x=0;x<145;x++){
     const px=rect.left+(x+.5)*rect.width/145;
     const py=rect.top+(96-y+.5)*rect.height/97;
     const h=API.hitPoint(tile,px,py);
     if(h.ready&&h.hit===want)return {px,py,x,y};
    }
    return null;
   };
   const clear=find(false);if(!clear)return {found:false};
   tile.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:1,clientX:clear.px,clientY:clear.py}));
   const rejected=tile.dataset.sourcePixelHit==='false';
   delete tile.dataset.sourcePixelHit;
   tile.click();
   return {found:true,rejected,keyboardUnblocked:tile.dataset.sourcePixelHit===undefined};
  });
  assert.ok(synthetic.found&&synthetic.rejected&&synthetic.keyboardUnblocked,
   'transparent bitmap cells cannot trigger source tile clicks; keyboard must still work');

  // Check the same real original art after zoom and on a narrow mobile board.
  await page.evaluate(()=>window.__LEAF_CAMERA__.zoom(.4));
  await page.waitForTimeout(250);
  const zoomed=await clickRealOpaque('camera-zoom');
  await page.setViewportSize({width:390,height:844});
  const mobile=await clickRealOpaque('mobile');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-source-tis-physical-alpha-mobile.png'});
  console.log('NATIVE TIS SOURCE PIXEL POINTER PASS '+JSON.stringify({
   sources:atlas.length,probes:atlas.reduce((a,b)=>a+b.probes,0),
   errors:0,desktop:first,zoomed,mobile,synthetic,
   status:'genuine-2002-RGBA + live-browser; historical-3D-mesh-still-unverified'
  }));
 }finally{await browser.close();}
})().catch(error=>{console.error('NATIVE TIS SOURCE POINTER FAILED',error.stack||error);process.exit(1)});
