'use strict';
/* Original Magic Carden tables: real source sprites at 2002 table coords. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const BOX={normal:[272,147,111,90],valuable:[430,142,160,123]};
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SHOP_STAGE__);
  await page.evaluate(()=>window.__ROG_TEST__.go('shop'));
  // WebKit can lay out the native CardShop scene after the first viewport
  // transition. Never divide anchors by a 0 scale during frame hydration.
  await page.waitForFunction(()=>{
   const stage=window.__LEAF_SHOP_STAGE__;
   const box=document.querySelector('#shop-native-stage')?.getBoundingClientRect();
   return stage?.getState().scale>0.05&&box?.width>10&&box.height>10;
  },null,{timeout:15000});
  const state=async()=>page.evaluate(()=>{
   const stage=document.getElementById('shop-native-stage').getBoundingClientRect();
   const scale=window.__LEAF_SHOP_STAGE__.getState().scale;
   const tab=g=>{const t=document.querySelector('.group-tab[data-group="'+g+'"]');const r=t.getBoundingClientRect();
    return {box:[(r.left-stage.left)/scale,(r.top-stage.top)/scale,r.width/scale,r.height/scale].map(v=>Math.round(v)),
     bg:getComputedStyle(t).backgroundImage,selected:t.classList.contains('selected')}};
   return {normal:tab('normal'),valuable:tab('valuable'),
    ranks:[...new Set([...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')].map(b=>b.dataset.rank))]};
  });
  const initial=await state();
  for(const g of ['normal','valuable'])assert.deepEqual(initial[g].box,BOX[g],g+' hotspot position');
  await page.locator('.group-tab[data-group="normal"]').click();await page.mouse.move(2,2);await page.waitForTimeout(200);
  const n=await state();
  assert.deepEqual(n.ranks,['normal']);assert.ok(n.normal.bg.includes('CardShop/normalcard.png'));
  assert.equal(n.valuable.bg,'none');
  await page.locator('.group-tab[data-group="valuable"]').click();await page.mouse.move(2,2);await page.waitForTimeout(200);
  const v=await state();
  assert.deepEqual(v.ranks,['valuable']);assert.ok(v.valuable.bg.includes('CardShop/valuablecard.png'));
  assert.equal(v.normal.bg,'none');
  const loaded=await page.evaluate(()=>Promise.all(['normalcard','valuablecard'].map(n=>new Promise(r=>{
   const i=new Image();i.onload=()=>r([i.naturalWidth,i.naturalHeight]);i.onerror=()=>r(null);i.src='./original/CardShop/'+n+'.png';}))));
  assert.deepEqual(loaded,[[111,90],[160,123]]);
  assert.deepEqual(errors,[]);
  console.log('SHOP ORIGINAL TABLES PASS',JSON.stringify({engine,initial:{normal:initial.normal.box,valuable:initial.valuable.box}}));
 }finally{await browser.close();}
})().catch(e=>{console.error('SHOP ORIGINAL TABLES FAILED',e.stack||e);process.exit(1);});
