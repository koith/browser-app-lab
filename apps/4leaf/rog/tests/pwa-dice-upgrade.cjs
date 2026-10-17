'use strict';
// Regression: a successfully published game.js/CSS must replace an old PWA
// cache immediately while online, yet remain usable without the network.
// This reproduces the exact stale-roll-handler failure the user encountered.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:390,height:844},
  isMobile:true,hasTouch:true,serviceWorkers:'allow'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  assert.match(base,/^https?:\/\//,'service workers require an HTTP(S) origin');
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_PWA__?.getState().registered===true,
   null,{timeout:30000});
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await page.reload();
  await page.waitForFunction(()=>Boolean(navigator.serviceWorker.controller),
   null,{timeout:20000});
  // The application upgrades its PWA revision whenever new native sprites
  // or gameplay input bindings ship. Always poison and inspect the CURRENT
  // active cache; checking hard-coded v64 after sw.js bumped to v65 can
  // pass online while testing an obsolete cache for offline preservation.
  const activeRevision=await page.evaluate(async()=>{
   const keys=await caches.keys();
   return keys.filter(x=>/^4leaf-revival-pwa-v\d+$/.test(x))
    .sort((a,b)=>Number(a.split('-v').at(-1))-Number(b.split('-v').at(-1))).at(-1);
  });
  assert.match(activeRevision||'',/^4leaf-revival-pwa-v\d+$/);
  const old='/* STALE-4LEAF-DICE-HANDLER-SHOULD-NOT-RUN */';
  const files=['game.js','dice-native-tis-depth.css'];
  await page.evaluate(async({files,old,activeRevision})=>{
   const cache=await caches.open(activeRevision);
   for(const file of files){
    await cache.put('./'+file,new Response(old,{
     headers:{'Content-Type':file.endsWith('.js')?
      'application/javascript':'text/css'}
    }));
   }
  },{files,old,activeRevision});
  const online=await page.evaluate(async files=>{
   const readings=[];
   for(const file of files){
    const response=await fetch('./'+file);
    readings.push({file,status:response.status,text:await response.text()});
   }
   return readings;
  },files);
  assert.ok(online.every(({status,text})=>status===200&&!text.includes('STALE-4LEAF')),
   'online service worker must fetch newly published game code instead of stale cached dice logic');
  assert.ok(online[0].text.includes('function startGame()'),
   'online game.js comes from the real installed game engine');
  assert.ok(online[1].text.includes('width:145px!important'),
   'online TIS CSS comes from the complete original sprite layout');
  const cached=await page.evaluate(async({files,activeRevision})=>{
   const cache=await caches.open(activeRevision);
   return Promise.all(files.map(async file=>{
    const item=await cache.match('./'+file);
    return item?await item.text():null;
   }));
  },{files,activeRevision});
  assert.ok(cached.every(x=>x&&!x.includes('STALE-4LEAF')),
   'successful network responses replace the old JS/CSS cache entries');
  await context.setOffline(true);
  const offline=await page.evaluate(async files=>{
   const result=[];
   for(const file of files){
    const response=await fetch('./'+file);
    result.push({status:response.status,text:await response.text()});
   }
   return result;
  },files);
  assert.ok(offline.every(x=>x.status===200&&!x.text.includes('STALE-4LEAF')),
   'the same upgraded genuine game scripts remain cached offline');
  const native=await page.evaluate(async(activeRevision)=>{
   const cache=await caches.open(activeRevision);
   const tile=await cache.match('./original/Tiles/0015.png');
   return {originalCached:Boolean(tile),size:tile?(await tile.blob()).size:0,
    controller:Boolean(navigator.serviceWorker.controller)};
  },activeRevision);
  assert.ok(native.controller&&native.originalCached&&native.size>500,
   'native TIS artwork remains accessible offline after the JS/CSS update');
  assert.deepEqual(errors,[],'no browser JavaScript errors during upgrade and offline fetches');
  console.log('4LEAF PWA FRESH DICE HANDLERS + OFFLINE SOURCE PASS',
   JSON.stringify({url:base,files,sourceBytes:online.map(x=>x.text.length),native}));
 }finally{await browser.close();}
})().catch(error=>{
 console.error('4LEAF PWA DICE UPGRADE FAILED',error.stack||error);
 process.exit(1);
});
