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
  console.log('M02 SNAPSHOT PASS '+engine+' '+JSON.stringify(source));
  await ctx.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('M02 SNAPSHOT FAIL',e.stack||e);process.exit(1)});
