'use strict';
// Genuine WorldMap/ChatTown/ChatRoom assets must work after cold PWA install,
// not only if a user happened to browse each image once while online.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:800},serviceWorkers:'allow'});
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.evaluate(async()=>{
   await navigator.serviceWorker.register('./sw.js');
   await navigator.serviceWorker.ready;
  });
  const critical=[
   'world-social.css','social-chat.js','world-map.js',
   ...['mainstreet','knights','northchatrgn','southchatrgn','dice','m4leaf'].map(s=>'original/WorldMap/'+s+'.png'),
   ...['northback','southback','plainbtn','seabtn','snowbtn'].map(s=>'original/ChatTown/'+s+'.png'),
   ...Array.from({length:6},(_,n)=>'original/ChatRoom/room'+n+'.png'),
   ...[3,4,5].map(n=>'original/ChatRoom/room'+n+'t.png'),
   'original/Registry/sava00.png'
  ];
  await page.waitForFunction(async files=>{
   const cache=await caches.open('4leaf-revival-pwa-v38');
   return (await Promise.all(files.map(file=>cache.match('./'+file)))).every(Boolean);
  },critical,{timeout:40000});
  // An established controller must answer image and JS fetches offline.
  await page.reload();
  await page.waitForFunction(()=>!!navigator.serviceWorker.controller,null,{timeout:12000});
  await context.setOffline(true);
  await page.reload({waitUntil:'domcontentloaded',timeout:15000});
  await page.waitForFunction(()=>document.querySelector('#leaf-world-stage .world-backdrop')?.dataset.ready==='true'
   &&document.querySelectorAll('#leaf-world-stage .world-sprite[data-ready="true"]').length===6,
   null,{timeout:18000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms');});
  await page.waitForFunction(()=>document.querySelectorAll('.social-district-hotspot').length===8,null,{timeout:8000});
  await page.locator('.social-district-hotspot').nth(3).click();
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('오프라인 원본 리소스 확인',4));
  await page.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',null,{timeout:8000});
  const original=await page.locator('.social-room-foreground').evaluate(el=>({
   source:el.dataset.source,native:[el.width,el.height],
   position:[parseFloat(el.style.left),parseFloat(el.style.top)]
  }));
  assert.equal(original.source,'room4t');
  assert.deepEqual(original.native,[115,103]);
  assert.deepEqual(original.position,[427,425]);
  assert.equal(await page.locator('.social-avatar.self').count(),1,'only genuine offline self occupant');
  assert.deepEqual(errors,[],'no unexpected JavaScript errors during offline play');
  console.log('4LEAF NATIVE OFFLINE CACHE PASS',JSON.stringify({cached:critical.length,original}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE OFFLINE CACHE FAILED',e.stack||e);process.exit(1)});
