'use strict';
// Actual recovered DMP route / 145x97 original TIS image exploration.
// This test does NOT pretend recovered DMP type codes encode 3D height.
// It exercises the real board, camera gestures, and game turn tracking.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const BASE=process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html');
 try{
  await page.goto(BASE);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&window.ORIGINAL_LEAF_MAPS);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile').length>30
   &&document.querySelector('#board-world')?.style.transform);
  const snapshot=()=>page.evaluate(()=>{
   const c=window.__LEAF_CAMERA__.getState();
   const area=document.querySelector('#board-area'),world=document.querySelector('#board-world');
   const ab=area.getBoundingClientRect(),wb=world.getBoundingClientRect();
   return {scale:c.scale,panX:c.panX,panY:c.panY,manual:c.manual,
    world:[c.size.width,c.size.height],area:[ab.width,ab.height],
    visual:[wb.width,wb.height],transform:world.style.transform,
    tiles:document.querySelectorAll('#board-nodes .tile').length,
    sourceVisible:[...document.querySelectorAll('#board-nodes .tile')]
     .filter(e=>e.style.visibility!=='hidden').length,
    match:window.__ROG_TEST__.getMatch().map,
    active:window.__ROG_TEST__.getMatch().active
   };
  });
  const initial=await snapshot();
  assert.deepEqual(initial.world,[1450,1120],'original mapped 1450x1120 camera plane is real');
  assert.ok(initial.tiles>30&&initial.sourceVisible>2,'original independent TIS cells render visibly');
  assert.equal(initial.scale,1.25,'initial player-follow zoom matches existing original-game UX');
  const endpoints=await page.evaluate(()=>{
   const camera=window.__LEAF_CAMERA__;
   const left=camera.panBy(-100000,0),right=camera.panBy(100000,0);
   return {left:left.panX,right:right.panX,last:right};
  });
  const horizontalSpan=endpoints.right-endpoints.left;
  assert.ok(horizontalSpan>initial.area[0]*.6,
   'real pan covers more than a tiny zoom-only scroll (span '+horizontalSpan+')');
  // Return to left board edge and walk the camera toward the other side
  // using genuine pointer events, without touching turn/game decisions.
  await page.evaluate(()=>window.__LEAF_CAMERA__.panBy(-100000,0));
  const beforeDrag=await snapshot();
  const bounds=await page.locator('#board-area').boundingBox();
  assert.ok(bounds&&bounds.width>100&&bounds.height>100);
  const px=bounds.x+bounds.width*.52,py=bounds.y+bounds.height*.46;
  await page.mouse.move(px,py);
  await page.mouse.down();
  await page.mouse.move(px+115,py+48,{steps:9});
  await page.mouse.up();
  const dragged=await snapshot();
  assert.ok(dragged.panX>beforeDrag.panX+70,
   'genuine pointer drag can move visible source camera right by >70px');
  assert.equal(dragged.active,initial.active,'pan is camera-only, never changes real turn owner');
  await page.locator('#board-area').focus();
  await page.keyboard.press('ArrowLeft');
  const keyboard=await snapshot();
  assert.ok(keyboard.panX>=dragged.panX+35,'keyboard pans recovered map, not browser page');
  const prevScale=keyboard.scale;
  await page.mouse.move(px,py);await page.mouse.wheel(0,-160);
  const wheeled=await snapshot();
  assert.ok(wheeled.scale>prevScale,'plain wheel zooms native 145x97 cells without Ctrl key');
  const pinch=await page.evaluate(()=>{
   const area=document.querySelector('#board-area'),rc=area.getBoundingClientRect();
   const x=rc.x+rc.width/2,y=rc.y+rc.height/2;
   const fire=(event,id,dx)=>area.dispatchEvent(new PointerEvent(event,{
    bubbles:true,pointerType:'touch',pointerId:id,button:0,
    clientX:x+dx,clientY:y
   }));
   const prior=window.__LEAF_CAMERA__.getState().scale;
   fire('pointerdown',77,-25);fire('pointerdown',78,25);
   fire('pointermove',78,110);
   const after=window.__LEAF_CAMERA__.getState().scale;
   fire('pointerup',77,-25);fire('pointerup',78,110);
   return {prior,after};
  });
  assert.ok(pinch.after>pinch.prior,
   'real pointer touch gesture enables two-finger pinch zoom on original live game');
  await page.locator('#board-zoom-reset').click();
  const reset=await snapshot();
  assert.ok(Math.abs(reset.scale-1.25)<.01,
   'native camera reset returns to 125% original follow zoom');
  assert.equal(reset.manual,false,'reset restores live pawn follow instead of remembered stale drag');

  // Low zoom still pans the whole DMP: old game.js blocked ALL dragging
  // when mapViewport.zoom <=1, despite a 1450x1120 world behind the client.
  for(let i=0;i<3;i++)await page.locator('#board-zoom-out').click();
  const lowZoom=await snapshot();
  assert.ok(lowZoom.scale<=1,'source camera genuinely supports 100% and below');
  await page.evaluate(()=>window.__LEAF_CAMERA__.panBy(-100000,0));
  const lowEdge=await snapshot();
  await page.locator('#board-area').focus();
  await page.keyboard.press('ArrowLeft');
  const lowKeyboard=await snapshot();
  assert.ok(lowKeyboard.panX>lowEdge.panX,
   'even at <=100% zoom original large map remains draggable and navigable');
  const atlas=await page.evaluate(async()=>{
   const img=new Image();img.src='./original/Tiles/0000.png';
   await img.decode();
   return {pixels:[img.naturalWidth,img.naturalHeight],
    dmp:document.querySelector('#board-nodes .tile[data-dmp-cell-code]')?.dataset.dmpCellCode,
    tiles:document.querySelectorAll('#board-nodes .tile').length};
  });
  assert.deepEqual(atlas.pixels,[145,97],'no fabricated geometry replaces 145x97 original TIS');
  assert.ok(atlas.dmp!==undefined,'unaltered source DMP third field is retained as unclassified code');
  assert.equal(atlas.tiles,initial.tiles,'full camera travel neither deletes playable cells nor changes TIS event data');
  await page.screenshot({path:'leaf-dmp-full-camera-wide-map.png'});
  await page.setViewportSize({width:390,height:844});
  await page.locator('#board-zoom-reset').click();
  const mobile=await snapshot();
  assert.ok(mobile.area[0]<initial.area[0]&&mobile.tiles===initial.tiles,
   'responsive board keeps all actual original DMP cells while camera resizes');
  assert.equal(await page.locator('#board-area').evaluate(e=>getComputedStyle(e).touchAction),'none',
   'mobile board touch controls are not eaten by browser viewport scrolling');
  assert.deepEqual(errors,[],'all camera gestures preserve client exception safety');
  console.log('DMP FULL CAMERA PASS',JSON.stringify({
   initial,horizontalSpan,dragged,keyboard,wheeled,pinch,reset,lowKeyboard,atlas,mobile
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('DMP FULL CAMERA FAILED',e.stack||e);process.exit(1)});
