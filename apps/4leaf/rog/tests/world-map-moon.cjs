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
