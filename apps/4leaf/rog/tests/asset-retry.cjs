'use strict';
// Browser regression for intermittent Pages HTTP 503 on authentic PAK art.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
 const errors=[];let failures=0,requests=0,mapFailures=0,mapRequests=0;
 page.on('pageerror',err=>errors.push(String(err)));
 await page.route('**/original/ChatRoom/room3t.png*',async route=>{
  requests++;
  if(failures<2){failures++;await route.fulfill({status:503,contentType:'text/plain',body:'Temporary CDN outage during original-art request'})}
  else await route.continue();
 });
 await page.route('**/original/IMG/bgtile.png*',async route=>{
  mapRequests++;
  if(mapFailures<2){mapFailures++;await route.fulfill({status:503,contentType:'text/plain',body:'Transient original terrain CDN 503'})}
  else await route.continue();
 });
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  await page.waitForFunction(()=>document.querySelector('#social-map-plane')?.dataset.terrain==='ready',null,{timeout:18000});
  assert.equal(mapFailures,2,'two simulated native ChatTown terrain HTTP 503 failures occurred');
  assert.ok(mapRequests>=3,'native ChatTown terrain image recovered through retries');
  assert.ok(await page.locator('#social-map-plane').evaluate(el=>getComputedStyle(el).backgroundImage.includes('original/IMG/bgtile.png')),'rendered terrain is original IMG source');
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
  console.log('ORIGINAL ROOM ASSET CDN RETRY PASS',JSON.stringify({requests,failures,mapRequests,mapFailures,...art}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL ROOM ASSET CDN RETRY FAILED',e.stack||e);process.exit(1)});
