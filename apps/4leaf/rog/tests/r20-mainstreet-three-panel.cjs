'use strict';
/* WORLD-02: physical desktop left/centre/right original 1938x404 MainStreet
   with seven source chroma-key building overlays. This verifies SOURCE PNG
   registration, not undiscovered 2004 EXE hotspot command coordinates. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_STREET__&&window.__ROG_TEST__);
  await page.evaluate(()=>window.__ROG_TEST__.go('city'));
  await page.waitForFunction(()=>[...document.querySelectorAll('.street-building-art')].length===7&&
   [...document.querySelectorAll('.street-building-art')].every(x=>x.dataset.ready==='true'),null,{timeout:16000});
  await page.waitForFunction(()=>document.querySelector('#street-track')?.getBoundingClientRect().width>500);
  const first=await page.evaluate(async()=>{
   const im=new Image();im.src='./original/MainStreet/back.png';await im.decode();
   const a=[...document.querySelectorAll('.street-location')].map(b=>({
    id:b.dataset.street,src:b.querySelector('canvas').dataset.hitMaskSource,
    ready:b.querySelector('canvas').dataset.ready}));
   return {source:[im.naturalWidth,im.naturalHeight],buildings:a};
  });
  assert.deepEqual(first.source,[1938,404]);
  assert.equal(first.buildings.length,7);
  assert.ok(first.buildings.every(x=>x.ready==='true'&&x.src.startsWith('MainStreet/')));
  const report=[];
  for(const [id,desired] of [['left',323],['centre',969],['right',1615]]){
   await page.evaluate(target=>{const api=window.__LEAF_STREET__;
    api.pan(target-api.getState().x);
   },desired);
   // The original street has a real .18s CSS pan transition. Sample the
   // finished physical view rather than the previous transform frame.
   await page.waitForTimeout(240);
   const x=await page.evaluate(()=>window.__LEAF_STREET__.getState().x);
   assert.equal(x,desired,'panorama original limits and middle must be reachable');
   const state=await page.evaluate(()=>{
    const t=document.querySelector('#street-track'),b=t.getBoundingClientRect();
    const v=document.querySelector('#street-viewport').getBoundingClientRect();
    return {src:document.querySelector('#street-track>.street-artwork')?.getAttribute('src'),
     scrollable:b.width>v.width,visibleRect:[b.left,b.top,b.width,b.height],
     viewport:[v.left,v.top,v.width,v.height],
     label:document.getElementById('street-area-label')?.textContent,
     sourceButtons:[...document.querySelectorAll('.street-location')].length};
   });
   assert.ok(state.src.includes('original/MainStreet/back.png'));
   assert.ok(state.viewport[2]>50&&state.viewport[3]>50&&state.visibleRect[2]>500,
    'actual original panorama stage must be visible in browser: '+JSON.stringify(state));
   assert.equal(state.sourceButtons,7);
   assert.ok(state.label&&state.label.includes(id==='left'?'왼쪽':id==='right'?'오른쪽':'중앙'));
   await page.screenshot({path:'leaf-r20-street-'+id+'.png'});
   report.push({panel:id,sourceX:x,label:state.label,viewport:state.viewport});
  }
  assert.equal(new Set(report.map(r=>Math.round(r.viewport[0]))).size,1,
   'three source views share one fixed real user viewport');
  assert.deepEqual(errors,[]);
  console.log('R20_SOURCE_MAINSTREET_THREE_PANEL_PASS',JSON.stringify({source:first.source,sourceBuildings:first.buildings,panels:report,legacyExeHotspotMap:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R20_SOURCE_MAINSTREET_THREE_PANEL_FAIL',e.stack||e);process.exit(1)});
