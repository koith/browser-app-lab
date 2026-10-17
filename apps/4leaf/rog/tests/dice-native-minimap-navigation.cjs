'use strict';
// 4LEAF actual Genesis/DMP minimap navigation, not a static picture or fake
// view rectangle. Verifies the original IMG/minimap.png 172x152 source plus
// one working 152x112 Canvas and one shared camera for real TIS/pawns.
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const snap=()=>page.evaluate(()=>{
  const mini=window.__LEAF_MINIMAP_NAV__?.getState();
  const cam=mini?.camera;
  const canvas=document.querySelector('#mini-map-canvas');
  const css=getComputedStyle(canvas);
  return {
   source:mini?.source,canvas:mini?.canvas,
   follow:mini?.follow,manual:cam?.manual,visible:cam?.visible,
   pan:[cam?.panX,cam?.panY],scale:cam?.scale,
   world:document.querySelector('#board-world')?.style.transform,
   nativeFrame:getComputedStyle(document.querySelector('#board-mini')).backgroundImage,
   parent:document.querySelector('#board-mini')?.parentElement?.id,
   pointers:css.pointerEvents,role:canvas.getAttribute('role'),
   keyboard:canvas.getAttribute('aria-keyshortcuts'),
   tabindex:canvas.tabIndex,dots:document.querySelectorAll('#board-nodes .tile').length,
   playerPosition:window.__ROG_TEST__?.getMatch()?.players?.map(p=>p.position)
  };
 });
 const neq=(a,b,label)=>assert.notDeepEqual(a,b,label);
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&window.__LEAF_MINIMAP_NAV__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>window.__LEAF_CAMERA__?.getState().visible?.width>0);

  const original=await page.evaluate(async()=>{
   const image=new Image();image.src='./original/IMG/minimap.png';await image.decode();
   const source=document.querySelector('#mini-map-canvas');
   return {bitmap:[image.naturalWidth,image.naturalHeight],
    canvas:[source.width,source.height],
    sourcePaint:getComputedStyle(document.querySelector('#board-mini')).backgroundImage};
  });
  assert.deepEqual(original.bitmap,[172,152],'genuine original minimap frame is 172x152');
  assert.deepEqual(original.canvas,[152,112],'same single source game canvas at 152x112');
  assert.ok(original.sourcePaint.includes('/original/IMG/minimap.png'),'paint recovered source bitmap');
  const first=await snap();
  assert.deepEqual(first.canvas,[152,112]);
  assert.equal(first.role,'button','one real interactive canvas rather than screenshot overlay');
  assert.equal(first.pointers,'auto','native map must accept user gestures');
  assert.equal(first.tabindex,0,'real minimap is keyboard focusable');
  assert.ok(first.dots>40,'source route contains independently rendered DMP cells');
  assert.ok(first.visible.width>0&&first.visible.width<1&&first.visible.height>0&&first.visible.height<1,
   'camera viewport covers an actual fraction of 1450x1120 original world');
  const canvas=page.locator('#mini-map-canvas');
  const initialPositions=first.playerPosition;

  // The original route must be explored without moving a single character.
  const size=await canvas.boundingBox();
  assert.ok(size.width>90&&size.height>80,'native 152x112 minimap is visible');
  await canvas.click({position:{x:size.width*.88,y:size.height*.80}});
  let bottom=await snap();
  assert.equal(bottom.follow,false,'real map interaction temporarily overrides pawn-follow');
  assert.equal(bottom.manual,true,'source minimap actually drives manual camera');
  neq(bottom.world,first.world,'source DMP world pans when minimap is clicked');
  assert.deepEqual(bottom.playerPosition,initialPositions,'minimap camera never changes real board game positions');
  assert.ok(bottom.visible.x>first.visible.x||bottom.visible.y>first.visible.y,
   'visible actual world viewport moves toward selected part of the minimap');

  await canvas.click({position:{x:size.width*.12,y:size.height*.15}});
  const top=await snap();
  neq(top.world,bottom.world,'clicking another quadrant changes the SAME real camera');
  assert.ok(top.visible.x<bottom.visible.x||top.visible.y<bottom.visible.y,
   'second click moves world toward upper-left DMP tiles');

  // Dragging a map is a continuously live camera operation, not a hyperlink.
  const bounds=await canvas.boundingBox();
  await page.mouse.move(bounds.x+bounds.width*.2,bounds.y+bounds.height*.25);
  await page.mouse.down();
  await page.mouse.move(bounds.x+bounds.width*.65,bounds.y+bounds.height*.55,{steps:5});
  await page.mouse.up();
  const dragged=await snap();
  neq(dragged.world,top.world,'dragging on original minimap continuously pans DMP camera');
  assert.deepEqual(dragged.playerPosition,initialPositions,'dragging never alters character position');
  await page.screenshot({path:'leaf-real-dmp-interactive-minimap-desktop.png'});

  await canvas.focus();
  await page.keyboard.press('ArrowRight');
  const keyed=await snap();
  assert.ok(keyed.visible.x>dragged.visible.x || (keyed.visible.x===dragged.visible.x&&keyed.visible.width===1),
   'minimap arrow keys pan right using world-relative camera coordinates');
  await page.keyboard.press('Home');
  const followed=await snap();
  assert.equal(followed.follow,true,'Home restores original active pawn tracking');
  assert.equal(followed.manual,false,'camera returns to automatic player following without modifying turns');

  await page.locator('#board-zoom-in').click();
  const zoomed=await snap();
  assert.ok(zoomed.visible.width<followed.visible.width,'zooming reduces correct world fraction in the real minimap box');
  assert.equal(zoomed.dots,first.dots,'source TIS cells are never recreated or hidden for the minimap');

  // Old mobile layout relocates the SAME canvas to the battlefield and
  // paints a half-size original frame. It must remain actually interactive.
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('#board-mini')?.parentElement?.id==='board-area');
  const mobileStart=await snap();
  assert.equal(mobileStart.parent,'board-area','mobile reuses the same minimap canvas, no fake copy');
  assert.ok(mobileStart.nativeFrame.includes('/original/IMG/minimap.png'));
  assert.equal(mobileStart.pointers,'auto','touch viewport can interact with source map');
  const miniRect=await canvas.boundingBox();
  assert.ok(miniRect.width>=50&&miniRect.height>=35,'native mobile minimap is visible');
  await canvas.click({position:{x:miniRect.width*.85,y:miniRect.height*.80},force:true});
  const mobile=await snap();
  assert.equal(mobile.follow,false,'mobile pointer click navigates real DMP terrain');
  assert.equal(mobile.manual,true,'touch uses the same manual camera state as desktop');
  neq(mobile.world,mobileStart.world,'mobile tap changes true battlefield transform');
  assert.deepEqual(mobile.playerPosition,initialPositions);
  await page.screenshot({path:'leaf-real-dmp-interactive-minimap-mobile.png'});
  assert.deepEqual(errors,[],'real original minimap and DMP camera generate no errors');
  console.log('REAL NATIVE MINIMAP NAVIGATION PASS',JSON.stringify({original,first,bottom,top,dragged,followed,mobile}));
 }finally{await browser.close()}
})().catch(e=>{console.error('REAL NATIVE MINIMAP NAVIGATION FAILED',e.stack||e);process.exit(1)});
