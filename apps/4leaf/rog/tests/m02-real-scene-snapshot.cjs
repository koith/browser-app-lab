'use strict';
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try {
  const ctx=await browser.newContext({viewport:{width:800,height:600},deviceScaleFactor:1,serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(base);
  const where='apps/4leaf/rog/tests/.visual-captures';
  fs.mkdirSync(where,{recursive:true});
  async function capture(name){
   await page.waitForTimeout(350);
   const geom=await page.evaluate(()=>{
    const ids=['#app','#main','#city','#street-viewport','.street-location[data-street="magic"]','#shop','#shop-native-stage','#shop-grid','.group-tab[data-group="normal"]','.group-tab[data-group="valuable"]','.group-tab[data-group="rare"]','#shop-selected','#shop-owned-list','#shop-gp','#shop-buy','#shop-sell','#shop-prev','#shop-next','#shop-page','.shop-era-toggle'];
    const o={route:window.__ROG_TEST__?.getState?.()?.route,era:window.__LEAF_SHOP_ERA__?.getState?.().era,items:{}};
    for(const id of ids){const e=document.querySelector(id);if(!e)continue;const r=e.getBoundingClientRect(),c=getComputedStyle(e);o.items[id]={xywh:[r.x,r.y,r.width,r.height].map(x=>+x.toFixed(2)),display:c.display,visible:!!(r.width>1&&r.height>1&&c.visibility!=='hidden'),source:e.dataset.source||null}}
    return o;
   });
   const jpeg=await page.screenshot({type:'jpeg',quality:52,animations:'disabled'});
   fs.writeFileSync(where+'/'+engine+'-m02-'+name+'.jpg',jpeg);
   console.log('4LEAF_M02_GEOM_'+name+'='+JSON.stringify(geom));
   if(process.env.LEAF_VISUAL_LOG_B64==='1')console.log('4LEAF_M02_JPEG_'+name+'='+jpeg.toString('base64'));
  }
  await page.locator('[data-route="city"]').first().click();
  await page.locator('#street-viewport').waitFor({state:'visible'});
  await capture('city');
  await page.locator('.street-location[data-street="magic"]').click();
  await page.locator('#shop-native-stage').waitFor({state:'visible'});
  assert.equal(await page.evaluate(()=>window.__LEAF_SHOP_ERA__.getState().era),'2004',
   'new M02 visitor lands on the archival 2004 4x2 scene');
  await page.locator('#shop-era-toggle button[data-era="2002"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SHOP_ERA__.getState().era),'2002',
   'explicit 2002 3x3 source atlas remains available');
  await capture('shop-2002');
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  await page.locator('#shop-grid .shop-card').first().click();
  await capture('shop-2004');
  const source=await page.evaluate(()=>{
   const r=document.getElementById('shop-native-stage').getBoundingClientRect();
   const cards=[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')];
   return {era:window.__LEAF_SHOP_ERA__.getState(),stage:[r.width,r.height],visibleCards:cards.length,
    cards:cards.slice(0,8).map(c=>{const x=c.getBoundingClientRect();return [x.x,x.y,x.width,x.height]})};
  });
  assert.equal(source.era.era,'2004');
  assert.equal(source.era.pageSize,8);
  assert.equal(source.visibleCards,8);
  const acceptance=await page.evaluate(()=>{
   const stage=document.querySelector('#shop-native-stage').getBoundingClientRect();
   const scale=stage.width/794;
   const pos=selector=>{
    const e=document.querySelector(selector);
    if(!e)return null;
    const r=e.getBoundingClientRect();
    return {x:(r.left-stage.left)/scale,y:(r.top-stage.top)/scale,
     width:r.width/scale,height:r.height/scale,rect:r};
   };
   const targets={
    normal:[32,15,'.group-tab[data-group="normal"]'],
    valuable:[134,15,'.group-tab[data-group="valuable"]'],
    rare:[233,15,'.group-tab[data-group="rare"]'],
    firstCard:[47,56,'#shop-grid .shop-card:first-child'],
    fifthCard:[47,145,'#shop-grid .shop-card:nth-child(5)'],
    owned:[402,32,'.shop-equipped'],
    gp:[402,294,'.shop-keeper .money'],
    cardInfo:[32,260,'.shop-detail'],
    buy:[402,333,'#shop-buy'],sell:[505,333,'#shop-sell']
   };
   const results={};let maxDelta=0;
   for(const [key,[x,y,selector]] of Object.entries(targets)){
    const actual=pos(selector);
    const delta=actual?Math.max(Math.abs(actual.x-x),Math.abs(actual.y-y)):999;
    maxDelta=Math.max(maxDelta,delta);
    results[key]={expected:[x,y],actual:actual?[+actual.x.toFixed(2),+actual.y.toFixed(2)]:null,delta:+delta.toFixed(2)};
   }
   const header=document.querySelector('#app>.toolbar .shop-era-toggle');
   const stageElement=document.querySelector('#shop-native-stage');
   const art=stageElement.querySelector('.shop-detail');
   return {maxDelta:+maxDelta.toFixed(2),results,
    comparisonOutsideSource:!!header&&!stageElement.contains(header),
    cardInfoLabel:getComputedStyle(art,'::before').content,
    sourceArtWidth:794,sourceArtHeight:404
   };
  });
  assert.ok(acceptance.maxDelta<=4,'2004 archived screenshot original pixels, 4px tolerance: '+JSON.stringify(acceptance));
  assert.equal(acceptance.comparisonOutsideSource,true,'WEB year/date tools must never overlay original 2004 canvas');
  assert.match(acceptance.cardInfoLabel,/Card Info/,'original Card Info label restored');
  console.log('M02_ARCHIVAL_2004_GEOMETRY_PASS '+engine+' '+JSON.stringify(acceptance));
  console.log('M02 SNAPSHOT PASS '+engine+' '+JSON.stringify(source));
  await ctx.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('M02 SNAPSHOT FAIL',e.stack||e);process.exit(1)});
