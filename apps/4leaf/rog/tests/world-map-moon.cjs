const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  const url=process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html');
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__ROG_TEST__);
  const world=await page.evaluate(async()=>{
   const stage=document.querySelector('#leaf-world-stage');
   const moon=document.querySelector('#world-original-moon');
   const frame=document.querySelector('#leaf-world-viewport');
   const backdrop=document.querySelector('.world-backdrop');
   await backdrop.decode();
   const m=getComputedStyle(moon);
   const r=moon.getBoundingClientRect(),s=stage.getBoundingClientRect();
   return {
    native:[backdrop.naturalWidth,backdrop.naturalHeight],
    moonCount:stage.querySelectorAll('#world-original-moon').length,
    moonStyle:[m.position,m.pointerEvents,m.borderRadius,m.backgroundImage,m.boxShadow],
    worldBg:getComputedStyle(frame).backgroundColor,
    relative:[(r.x-s.x)/s.width*796,(r.y-s.y)/s.height*528,(r.width/s.width)*796],
    regions:document.querySelectorAll('.world-location').length,
    nativeSprites:[...document.querySelectorAll('.world-sprite')].map(c=>({kind:c.className,src:c.dataset.ready})),
    legacyCaptions:document.querySelectorAll('.world-map-caption').length,
    original:backdrop.getAttribute('src')
   };
  });
  assert.deepEqual(world.native,[796,528],'actual recovered source PNG dimensions retained');
  assert.ok(world.original.includes('original/WorldMap/worldmapback.png'),'genuine source bitmap not replaced with fabricated screenshot');
  assert.equal(world.moonCount,1,'independent original-reference full moon drawn exactly once');
  assert.equal(world.moonStyle[0],'absolute');
  assert.equal(world.moonStyle[1],'none','decorative lunar disc cannot intercept world map navigation');
  assert.ok(world.moonStyle[3].includes('radial-gradient'),'moon is an independent CSS moon with no screenshot cutout');
  assert.ok(world.moonStyle[4].includes('rgb'),'moon has original warm edge glow');
  assert.ok(Math.abs(world.relative[0]-650)<2&&Math.abs(world.relative[1]-11)<2&&Math.abs(world.relative[2]-122)<2,'moon registered to native 796x528 reference layout');
  // Original sky.jpg (794x528) shows a persistent 184x61 Notice at (23,9).
  // It must be independently composed from original/WorldMap/notice.png;
  // hover tooltips are NOT substitutes for the missing resting panel.
  await page.waitForFunction(()=>['true','fallback'].includes(
   document.querySelector('#world-native-notice')?.dataset.ready),null,{timeout:13000});
  const nativeNotice=await page.evaluate(async()=>{
   const stage=document.querySelector('#leaf-world-stage');
   const el=document.querySelector('#world-native-notice');
   const rect=el.getBoundingClientRect(),frame=stage.getBoundingClientRect();
   const image=el.style.backgroundImage;
   const result={
    count:stage.querySelectorAll('#world-native-notice').length,
    dimensions:[rect.width/frame.width*796,rect.height/frame.height*528],
    location:[(rect.left-frame.left)/frame.width*796,(rect.top-frame.top)/frame.height*528],
    visible:getComputedStyle(el).display,ready:el.dataset.ready,
    source:el.dataset.source,liveText:el.textContent,
    pointer:getComputedStyle(el).pointerEvents,
    nativeSprite:null,cornerAlpha:null,sourceImage:image
   };
   if(el.dataset.ready==='true'){
    const img=new Image();img.src=image.slice(5,-2);await img.decode();
    const pixel=document.createElement('canvas');pixel.width=img.naturalWidth;pixel.height=img.naturalHeight;
    const ctx=pixel.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
    result.nativeSprite=[img.naturalWidth,img.naturalHeight];
    result.cornerAlpha=ctx.getImageData(0,0,1,1).data[3];
   }
   return result;
  });
  assert.equal(nativeNotice.count,1,'original WorldMap has exactly one permanent Notice layer');
  assert.equal(nativeNotice.source,'WorldMap/notice.png','independently mounted genuine source notice asset');
  assert.equal(nativeNotice.visible,'block','native announcement panel rests visible on the WorldMap');
  assert.equal(nativeNotice.pointer,'none','notice never blocks original map clicks');
  assert.equal(nativeNotice.liveText,'월드맵에서 지역을 선택하세요','expired historical event is not advertised as live');
  assert.ok(Math.abs(nativeNotice.location[0]-23)<1.5&&Math.abs(nativeNotice.location[1]-9)<1.5,
   'original sky.jpg notice placement matches native 796x528 coordinates');
  if(!url.startsWith('file:')){
   assert.equal(nativeNotice.ready,'true','source Notice bitmap must load on HTTP(S)');
   assert.deepEqual(nativeNotice.nativeSprite,[184,61],'actual recovered native notice frame dimensions');
   assert.equal(nativeNotice.cornerAlpha,0,'source bright-green chroma key removed from notice corners');
   assert.ok(Math.abs(nativeNotice.dimensions[0]-184)<1&&Math.abs(nativeNotice.dimensions[1]-61)<1,
    'original notice source size is preserved, not stretched or screenshot-pasted');
  }else{
   assert.ok(['true','fallback'].includes(nativeNotice.ready),
    'local file:// must keep accessible fallback without a cross-origin canvas exception');
  }

  assert.equal(world.regions,6,'all independently clickable recovered original locations remain');
  assert.equal(world.nativeSprites.length,6,'native four-frame canvases and focus handlers retained');
  assert.equal(world.legacyCaptions,0,'no new invented giant WORLD MAP caption obscures original text');
  await page.screenshot({path:'leaf-original-worldmap-full-moon.png'});
  await page.locator('.world-location[data-region="north"]').click();
  await page.waitForSelector('#rooms:not(.hidden)');
  const north=await page.evaluate(()=>window.__LEAF_SOCIAL__?.getState?.()?.region);
  assert.ok(north==='north'||await page.locator('#rooms .social-town-map').count()>0,'north ChatTown remains real independent scene');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('.world-location[data-region="south"]').click();
  await page.waitForSelector('#rooms:not(.hidden)');
  await page.locator('[data-route="sky"]').first().click();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('#world-original-moon').count(),1,'full moon remains part of logical world and shrinks with source map');
  assert.equal(await page.locator('.world-location').count(),6,'mobile map navigation intact');
  assert.deepEqual(errors,[],'original scene augmentation does not trigger runtime errors');
  console.log('WORLD MAP SOURCE MOON PASS: 796x528 original source, 2003 screenshot 122px moon, six live regions, independent ChatTown navigation, mobile');
 }finally{await browser.close()}
})().catch(e=>{console.error('WORLD MAP SOURCE MOON FAILED:',e.stack||e);process.exit(1)});
