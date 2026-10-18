'use strict';
/* Full-source original DMP atlas navigation. All 26 source maps and each
 * of their 1,920 real TIS cells are independently focusable on both
 * Chromium 1280x900 desktop and iPhone 390x844 responsive layouts.
 * This proves no unreachable/blank source cells; it does NOT claim the
 * web-projected pitch is the historic 2004 MVE 3D camera.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const URL=process.env.FOURLEAF_TEST_URL||
 'file://'+path.resolve(__dirname,'../index.html');
async function audit(browser,mobile){
 const context=await browser.newContext({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'
 });
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(URL);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&
   window.ORIGINAL_LEAF_MAPS&&window.ORIGINAL_LEAF_MAP_INFO);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const results=await page.evaluate(()=>{
   const sources=window.ORIGINAL_LEAF_MAPS;
   const info=window.ORIGINAL_LEAF_MAP_INFO;
   const camera=window.__LEAF_CAMERA__;
   const game=window.__ROG_TEST__;
   const entries=Object.entries(info)
    .filter(([id,v])=>sources[id]?.length>=10);
   const original=game.getMatch(),log=[];
   // The actual client intentionally eases map camera transitions for 200ms
   // (#game .board-world { transition:transform .20s ease-out!important }).
   // A zero-delay 1920-cell synchronous hit test otherwise reads the
   // IN-FLIGHT CSS transform, not the destination of each real camera
   // focusRatio, giving false 'inaccessible DMP' reports (0219=0/45).
   // Disable only the animated interpolation for this *geometry audit*.
   // Movement calculation/rendering/culling continues through the
   // unmodified production camera focusRatio and actual tile DOM.
   const world=document.getElementById('board-world');
   const nativeTransition=getComputedStyle(world).transitionDuration;
   world.style.setProperty('transition','none','important');
   const valid=(a,b)=>Number.isFinite(a)&&Number.isFinite(b);
   for(const [id,metadata] of entries){
    const title=metadata.title,source=sources[id];
    const tiles=game.generateTiles(title);
    if(!Array.isArray(tiles)||tiles.length!==source.length)
     throw Error('Original DMP path/event length drift '+id+' '+title);
    const match={...original,map:title,tiles,
     active:0,round:1,finished:false,
     players:original.players.map(p=>({...p,position:0}))};
    game.setMatch(match);
    camera.reset();
    const all=[...document.querySelectorAll('#board-nodes>.tile')];
    if(all.length!==source.length)
     throw Error('Missing native 145x97 cells '+id+' '+all.length+' / '+source.length);
    if(!all.every((tile,i)=>
      Number(tile.dataset.dmpX)===source[i][0]&&
      Number(tile.dataset.dmpY)===source[i][1]&&
      tile.offsetWidth===145&&tile.offsetHeight===97))
      throw Error('Native source x/y or TIS pixels changed '+id);
    const state=camera.getState();
    const path=state.path,bounds=state.routeBounds;
    if(!path||path.length!==source.length||!bounds)
      throw Error('No source camera path bounds '+id);
    const viewport=document.querySelector('#board-area').getBoundingClientRect();
    if(!valid(viewport.width,viewport.height)||viewport.width<=100||viewport.height<=100)
      throw Error('Game viewport collapsed '+id);
    let reachable=0,miss=[];
    // All DMP cells get a genuine camera focus movement. Hidden CSS
    // source cells DO NOT count as reachable.
    for(let i=0;i<source.length;i++){
     camera.focusRatio(path[i].x/100,path[i].y/100);
     const tile=all[i];
     const r=tile.getBoundingClientRect();
     const shown=tile.style.visibility!=='hidden'&&
      r.right>viewport.left&&r.left<viewport.right&&
      r.bottom>viewport.top&&r.top<viewport.bottom;
     if(shown)reachable++;
     else if(miss.length<4)miss.push({id,index:i,xy:source[i].slice(0,2),rect:[r.x,r.y,r.width,r.height]});
    }
    if(reachable!==source.length){
      const current=camera.getState(),world=document.getElementById('board-world');
      throw Error('Unreachable original DMP platforms '+title+
       ' '+reachable+'/'+source.length+' '+JSON.stringify({
        missing:miss,cameraX:current.cameraX,cameraY:current.cameraY,
        scale:current.scale,panX:current.panX,panY:current.panY,
        bounds:current.routeBounds,path0:path[0],
        viewport:[viewport.width,viewport.height],
        gameViewportHidden:document.getElementById('game').className,
        worldTransform:world.style.transform,
        cssWorldTransform:getComputedStyle(world).transform,
        firstCell:[source[0][0],source[0][1]]
      }));
    }
    // Extrema must respect the actual route footprint, not empty
    // margins of the 6000px shared world allocated for all 26 maps.
    const before=camera.panBy(-1e5,-1e5);
    const bottom=camera.getState().visible;
    const after=camera.panBy(1e5,1e5);
    const top=camera.getState().visible;
    if(!bottom||!top||!valid(before.panX,after.panX)||
       before.routeBounds.minX!==bounds.minX)
      throw Error('Camera pan escaped source atlas '+id);
    log.push({id,name:title,total:source.length,reachable,
     bounds:{minX:bounds.minX,maxX:bounds.maxX,
      minY:bounds.minY,maxY:bounds.maxY},
     pan:[before.panX,after.panX]});
   }
   game.setMatch(original);
   camera.reset();
   world.style.removeProperty('transition');
   return {maps:log,allCells:log.reduce((n,a)=>n+a.total,0),
    reached:log.reduce((n,a)=>n+a.reachable,0),
    pitch:camera.getState().projectedPitch,
    rendererTransition:nativeTransition,
    restoredGame:game.getMatch().map};
  });
  assert.equal(results.maps.length,26,'All 26 genuine source DMP maps must be tested');
  assert.equal(results.allCells,1920,'All 1,920 source cells must be present');
  assert.equal(results.reached,1920,'Every original TIS cell must be reachable');
  assert.ok(results.pitch.x>=145&&results.pitch.y>=97);
  assert.equal(results.restoredGame,'4LEAF');
  assert.deepEqual(errors,[],'No source render/actor errors while changing all maps');
  await page.screenshot({path:mobile?'leaf-all-26-dmp-mobile.png':'leaf-all-26-dmp-desktop.png'});
  console.log('ORIGINAL 26-MAP CAMERA PASS',JSON.stringify({
   device:mobile?'mobile':'desktop',mapCount:results.maps.length,
   cells:results.allCells,reachable:results.reached,pitch:results.pitch,
   mapSummary:results.maps.map(x=>[x.id,x.total])
  }));
 }finally{await context.close()}
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{await audit(browser,false);await audit(browser,true)}
 finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL ALL-MAP CAMERA FAILED:',e.stack||e);process.exit(1)});
