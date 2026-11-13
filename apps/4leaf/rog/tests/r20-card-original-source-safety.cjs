'use strict';
/* ACT-05: never claim unverified CHR->CardData/chm_N face ownership.
   The visible card must show its own authentic CHR frame 0, or the genuine
   original IMG cardback for missing 0156. Test source and real shop DOM. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const game=fs.readFileSync(path.join(root,'game.js'),'utf8');
assert.ok(game.includes("const originalBodyCardArt=id=>"),'source card fallback routing missing');
assert.ok(game.includes("const NEUTRAL_CARD_ART='./original/IMG/avatarback.png'"));
assert.ok(!game.includes('(sourceId%59)+1'),'must not resurrect false CardData facial matching');
assert.ok(game.includes('verified-CHR-own-body-not-CardData-portrait'));
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_CHR_BODY_MAP__&&window.__ROG_TEST__);
  const roster=await page.evaluate(()=>{
   const map=window.__LEAF_CHR_BODY_MAP__,ids=Object.keys(map.cards);
   return {cards:ids.length,recovered:ids.filter(id=>!!map.resolve(id)).length,
    missing:ids.filter(id=>!map.resolve(id)),originalFacesVerified:false};
  });
  assert.equal(roster.cards,98);assert.equal(roster.recovered,97);
  assert.deepEqual(roster.missing,['0156']);
  await page.evaluate(()=>window.__ROG_TEST__.go('shop'));
  await page.waitForSelector('#shop:not(.hidden) #shop-grid');
  await page.waitForFunction(()=>[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty) .pixel-portrait')]
   .every(x=>x.complete&&x.naturalWidth>0),null,{timeout:20000});
  const visible=await page.evaluate(()=>[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')].map(c=>{
   const id=c.dataset.cardId?.replace(/^c_/,'')||'';
   const img=c.querySelector('.pixel-portrait');
   const own=window.__LEAF_CHR_BODY_MAP__.resolve(id);
   const url=own?.frames?.find(f=>f.index===0)?.url||'./original/IMG/avatarback.png';
   return {id,src:img?.getAttribute('src'),ownSource:url,indicator:img?.dataset.cardArtEvidence,
    decoded:Boolean(img?.complete&&img?.naturalWidth>0)};
  }));
  assert.ok(visible.length>=3,'actual native shop has original cards');
  for(const v of visible){
   assert.equal(v.src,v.ownSource,'no unrelated original face may impersonate '+v.id);
   assert.equal(v.decoded,true);
   assert.ok(v.indicator==='verified-CHR-own-body-not-CardData-portrait'||
    v.indicator==='no-verified-CardData-portrait');
  }
  await page.screenshot({path:'leaf-r20-owned-card-source-safety.png'});
  assert.deepEqual(errors,[]);
  console.log('R20_CHR_CARD_ART_NO_FALSE_FACIAL_MATCH_PASS',JSON.stringify({roster,liveShopCards:visible.length,CardDataOriginalFaceMap:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R20_CARD_OWN_SOURCE_FAIL',e.stack||e);process.exit(1)});
