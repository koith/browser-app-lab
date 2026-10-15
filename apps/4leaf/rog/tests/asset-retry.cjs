'use strict';
// Browser regression for intermittent Pages HTTP 503 on authentic PAK art.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const errors=[];let failures=0,requests=0,worldFailures=0,worldRequests=0,spriteFailures=0,spriteRequests=0;
 page.on('pageerror',err=>errors.push(String(err)));
 await page.route('**/original/ChatRoom/room3t.png*',async route=>{
  requests++;
  if(failures<2){failures++;await route.fulfill({status:503,contentType:'text/plain',body:'Temporary CDN outage during original-art request'})}
  else await route.continue();
 });
 await page.route('**/original/WorldMap/worldmapback.png*',async route=>{
  worldRequests++;
  if(worldFailures<2){worldFailures++;await route.fulfill({status:503,contentType:'text/plain',body:'Transient native WorldMap background error'})}
  else await route.continue();
 });
 await page.route('**/original/WorldMap/northchatrgn.png*',async route=>{
  spriteRequests++;
  if(spriteFailures<2){spriteFailures++;await route.fulfill({status:503,contentType:'text/plain',body:'Transient native WorldMap sprite error'})}
  else await route.continue();
 });
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.waitForFunction(()=>{
   const background=document.querySelector('#leaf-world-stage .world-backdrop');
   const sprites=[...document.querySelectorAll('#leaf-world-stage canvas.world-sprite')];
   return background?.dataset.ready==='true'&&sprites.length===6
    &&sprites.every(sprite=>sprite.dataset.ready==='true');
  },null,{timeout:20000});
  assert.equal(worldFailures,2,'two simulated native WorldMap backdrop HTTP 503 errors');
  assert.equal(spriteFailures,2,'two simulated North Haiacan sprite HTTP 503 errors');
  assert.ok(worldRequests>=3&&spriteRequests>=3,'native WorldMap art retries succeed without substitutes');
  const recovered=await page.locator('#leaf-world-stage canvas.world-sprite').nth(2).evaluate(canvas=>{
   const data=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
   let visible=0,clear=0;
   for(let i=3;i<data.length;i+=4){if(data[i]>0)visible++;else clear++}
   return {visible,clear};
  });
  assert.ok(recovered.visible>1500&&recovered.clear>1500,
   'original North Haiacan frame is restored with its actual chroma-key transparency');
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  assert.deepEqual(await page.locator('#social-map-plane').evaluate(el=>({
   type:el.dataset.terrain,background:getComputedStyle(el).backgroundImage
  })),{type:'unverified',background:'none'},
   'ChatTown never loads Genesis Dice bgtile as a fake historic region terrain');
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('임시 리소스 장애 복구 QA',3));
  await page.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',null,{timeout:18000});
  const art=await page.locator('.social-room-foreground').evaluate(canvas=>{
   const d=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
   let visible=0,transparent=0;
   for(let i=3;i<d.length;i+=4)if(d[i])visible++;else transparent++;
   return {width:canvas.width,height:canvas.height,visible,transparent};
  });
  assert.equal(failures,2,'two simulated HTTP 503 responses occurred');
  assert.ok(requests>=3,'renderer retried the original file after 503');
  assert.ok(art.visible>500&&art.transparent>500,'native original furniture eventually renders with alpha');
  assert.deepEqual(errors,[],'no unhandled JavaScript exceptions');
  console.log('ORIGINAL WORLD AND ROOM ART RETRY PASS',JSON.stringify({requests,failures,worldRequests,worldFailures,spriteRequests,spriteFailures,...art}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL ROOM ASSET CDN RETRY FAILED',e.stack||e);process.exit(1)});
