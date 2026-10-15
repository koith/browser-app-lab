'use strict';
// The six-region source KnightTown is a different 794x404 original interface
// from ChatTown (north/south) and Genesis Dice (Region/TOWN SELECT).
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_KNIGHT_TOWN__&&window.__LEAF_SOCIAL__);
  await page.locator('[data-region="knights"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'knighttown');
  const native=await page.evaluate(async()=>{
   const region=document.querySelector('#rooms');
   const frame=document.getElementById('social-image-frame');
   const stage=document.getElementById('social-stage');
   const backdrop=new Image();backdrop.src='./original/KnightTown/knightback.png';await backdrop.decode();
   const areas=window.__LEAF_KNIGHT_TOWN__.getState().areas;
   const arts=await Promise.all(areas.map(async a=>{
    const image=new Image();image.src='./original/KnightTown/'+a.asset+'.png';await image.decode();
    const control=frame.querySelector('[data-knight-area="'+a.id+'"]');
    const sprite=control.querySelector('.knight-source-hover');
    return {id:a.id,name:a.name,size:[image.naturalWidth,image.naturalHeight],
      nativeSource:control.dataset.source,
      nativeHit:control.dataset.nativeBounds.split(',').map(Number),
      nativeSprite:control.dataset.nativeSprite.split(',').map(Number),
      focusButton:control.tagName,
      bg:getComputedStyle(sprite).backgroundImage,
      frameSize:[sprite.offsetWidth,sprite.offsetHeight],
      backgroundOffset:getComputedStyle(sprite).backgroundPosition};
   }));
   return {archive:[backdrop.naturalWidth,backdrop.naturalHeight],
    declared:window.__LEAF_KNIGHT_TOWN__.getState().logicalSize,
    actualHeight:frame.style.height,
    actualBackground:getComputedStyle(frame).backgroundImage,
    areaCount:frame.querySelectorAll('.knight-district-hotspot').length,
    actualBgSize:getComputedStyle(frame).backgroundSize,
    roster:getComputedStyle(document.getElementById('social-peer-panel')).display,
    socialView:window.__LEAF_SOCIAL__.getState().view,
    diceVisible:!document.getElementById('dice-channels').classList.contains('hidden'),
    nativeClass:region.classList.contains('native-knight-town'),
    backdropRect:[stage.getBoundingClientRect().width,stage.getBoundingClientRect().height],
    arts};
  });
  assert.deepEqual(native.archive,[794,404],'KnightTown source native pixels, never a screenshot');
  assert.deepEqual(native.declared,[794,404],'logical coordinate system matches source PNG');
  assert.equal(native.actualHeight,'404px');
  assert.equal(native.nativeClass,true);
  assert.equal(native.areaCount,6,'exactly six real knight region sign hotspots');
  assert.ok(native.actualBackground.includes('original/KnightTown/knightback.png'),
   'real region backdrop from extracted KnightTown.pak');
  assert.equal(native.actualBgSize,'794px 404px');
  assert.equal(native.roster,'none','ChatRoom-only participant panel never covers native region art');
  assert.equal(native.diceVisible,false,'this is not Genesis Dice TOWN SELECT');
  assert.deepEqual(native.arts.map(a=>a.name),
   ['모험의 바다','패왕의 대지','침묵의 설원','도전의 바다','찬란한 바다','영광의 대지']);
  for(const art of native.arts){
   assert.deepEqual(art.size,[568,74],art.id+' source 4-frame native sign atlas');
   assert.deepEqual(art.frameSize,[142,74],art.id+' original frame, not scaled sprite');
   assert.equal(art.focusButton,'BUTTON','source sign is independent functional button');
   assert.ok(art.bg.includes('/original/KnightTown/'+art.id+'.png'));
   assert.deepEqual(art.nativeHit,windowDummy(art.nativeHit),'source hotspot bounds are finite');
   const [hx,hy,hw,hh]=art.nativeHit,[sx,sy]=art.nativeSprite;
   assert.ok(sx>=hx&&sy>=hy&&sx+142<=hx+hw&&sy+74<=hy+hh,
    art.id+' complete pixel-correlated original sprite remains pointer/keyboard reachable');
   assert.equal(art.backgroundOffset,'-142px 0px','hover uses authentic second atlas frame');
  }
  await page.locator('[data-knight-area="sea01"]').hover();
  assert.equal(await page.locator('[data-knight-area="sea01"] .knight-source-hover')
   .evaluate(el=>getComputedStyle(el).opacity),'1','original sign focus atlas actually appears');
  await page.screenshot({path:'leaf-original-knighttown-native.png'});
  for(const a of native.arts){
   await page.locator('[data-knight-area="'+a.id+'"]').focus();
   await page.keyboard.press('Enter');
   const state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
   assert.equal(state.view,'board','selected historical area is actionable');
   assert.equal(state.knightDistrict,a.name,'region name preserved in actual session');
   assert.ok(await page.locator('.recordable-board').isVisible(),
    'existing functional bulletin is accessible, with no fictional room catalogue');
   assert.equal(await page.locator('.knight-district-hotspot').count(),0,
    'selected region navigates, not overlays a fake screenshot');
   await page.locator('#social-back').click();
   assert.equal(await page.locator('.knight-district-hotspot').count(),6,
    'return from bulletin to all six real original signposts');
  }
  await page.setViewportSize({width:390,height:844});
  const narrow=await page.evaluate(()=>{
   const frame=document.getElementById('social-image-frame');
   const rect=frame.getBoundingClientRect();
   return {w:rect.width,h:rect.height,n:frame.querySelectorAll('.knight-district-hotspot').length};
  });
  assert.equal(narrow.n,6,'source image continues to work on touch-sized viewport');
  assert.ok(Math.abs(narrow.w/narrow.h-794/404)<.015,
   'native 794:404 proportions persist on small viewports');
  await page.locator('[data-knight-area="snow01"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().knightDistrict),'침묵의 설원');
  await page.locator('#social-back').click();
  await page.locator('#social-back').click();
  assert.ok(await page.locator('#sky:not(.hidden)').isVisible(),'native Recordable returns to source WorldMap');
  assert.deepEqual(errors,[],'native KnightTown introduces no page errors');
  console.log('NATIVE KNIGHTTOWN SIX DISTRICT PASS',JSON.stringify({native,narrow}));
 }finally{await browser.close()}
 function windowDummy(bounds){
  assert.equal(bounds.length,4);
  for(const n of bounds)assert.ok(Number.isFinite(n)&&n>=0&&n<=794);
  return bounds;
 }
})().catch(e=>{console.error('NATIVE KNIGHTTOWN FAILED',e.stack||e);process.exit(1)});
