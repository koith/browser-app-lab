'use strict';
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__,null,{timeout:30000});
  const cards=await page.evaluate(()=>{
   const playable=(window.ORIGINAL_LEAF_CHESSMEN||[]).filter(c=>
    c.move>=1&&c.move<=2&&c.atk>=1&&c.def>=1&&
    !['마장기 test','근육이','노동자스켈톤'].includes(c.name));
   return playable.map(c=>{
    const body=window.__LEAF_CHR_BODY_MAP__.resolve(c.id);
    return {id:c.id,expected:body?.frames?.find(f=>f.index===0)?.url||null,
     art:window.__ROG_TEST__.imageFor('c_'+c.id),
     provenance:window.__ROG_TEST__.portraitEvidence('c_'+c.id)};
   });
  });
  assert.ok(cards.length>=90,'genuine original CHR roster, not synthetic sample');
  assert.ok(cards.filter(x=>x.expected).length>=90,'recovered original CHR source available');
  for(const c of cards){
   assert.ok(!c.art.includes('CardData/chm_'),'unsupported face: '+c.id);
   assert.equal(c.art,c.expected||'./original/IMG/avatarback.png',
    'must show only same-card verified source or original cardback for '+c.id);
   assert.equal(c.provenance,c.expected?'verified-CHR-own-body-not-CardData-portrait':
    'no-verified-CardData-portrait');
  }
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForFunction(()=>{
   const imgs=[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty) img')];
   return imgs.length===9&&imgs.every(i=>i.complete&&i.naturalWidth>0);
  },null,{timeout:25000});
  assert.deepEqual(errors,[],'normal original card images do not crash runtime');
  console.log('4LEAF_CARD_OWNED_CHR_ART_PASS',JSON.stringify({
   engine:engine.name(),cards:cards.length,recovered:cards.filter(x=>x.expected).length}));
  await context.close();

  const brokenContext=await browser.newContext({viewport:{width:1280,height:900},
   serviceWorkers:'block'});
  const broken=await brokenContext.newPage();
  await broken.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await broken.route('**/original/OBS/**/*.png',r=>r.abort('failed'));
  await broken.goto(base,{waitUntil:'domcontentloaded'});
  await broken.locator('[data-route="shop"]').first().click();
  await broken.waitForFunction(()=>{
   const imgs=[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty) img')];
   return imgs.length===9&&imgs.every(i=>i.complete&&i.naturalWidth>0&&
    i.getAttribute('src')==='./original/IMG/avatarback.png');
  },null,{timeout:25000});
  console.log('4LEAF_CHR_CARD_ART_MISSING_IMAGE_FALLBACK_PASS',JSON.stringify({engine:engine.name()}));
  await brokenContext.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_CARD_ART_FAILED',e.stack||String(e));process.exit(1)});
