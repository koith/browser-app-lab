'use strict';
/* Historical Rare tier appeared as a 2004 screenshot tab, but no card
 * from it was ever released. The later game removed the empty tier.
 * Secondary archive: https://seore.org/raw/문서:주사위의%20잔영
 * UI/rare metadata must NEVER invent original CHR category membership. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__&&window.__ROG_TEST__);
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  const first=await page.evaluate(()=>({
   era:window.__LEAF_SHOP_ERA__.getState(),
   tabs:[...document.querySelectorAll('#shop .group-tab')].map(b=>({group:b.dataset.group,visible:getComputedStyle(b).display!=='none'})),
   count:document.querySelectorAll('#shop-grid .shop-card').length,
   gp:JSON.parse(localStorage.getItem('rog_profile')).gp,
   owned:JSON.parse(localStorage.getItem('rog_profile')).owned
  }));
  assert.equal(first.era.era,'2002');
  assert.equal(first.count,9);
  assert.equal(first.era.rareMembershipVerified,false);
  assert.equal(first.tabs.find(x=>x.group==='rare').visible,false);
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  const scene=await page.evaluate(()=>({
   era:window.__LEAF_SHOP_ERA__.getState(),
   total:document.querySelectorAll('#shop-grid .shop-card').length,
   sourceLayout:document.querySelector('#shop-native-stage')?.dataset.era,
   gp:JSON.parse(localStorage.getItem('rog_profile')).gp
  }));
  assert.equal(scene.total,8,'historical 2004 source 4x2 screenshot must remain interactive');
  assert.equal(scene.sourceLayout,'2004');
  assert.equal(scene.era.rareMembershipVerified,false,'unreleased Rare list not misrepresented as EXE');
  await page.locator('#shop .group-tab[data-group="rare"]').click();
  const rare=await page.evaluate(()=>({
   title:document.querySelector('#shop-selected').textContent,
   cards:document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)').length,
   buyDisabled:document.querySelector('#shop-buy').disabled,
   sellDisabled:document.querySelector('#shop-sell').disabled,
   provenance:document.querySelector('#shop-era-provenance').textContent,
   rareLabel:document.querySelector('#shop .group-tab[data-group="rare"]').getAttribute('aria-label'),
   gp:JSON.parse(localStorage.getItem('rog_profile')).gp,
   owned:JSON.parse(localStorage.getItem('rog_profile')).owned
  }));
  assert.equal(rare.cards,0,'zero historically released RARE chessmen');
  assert.ok(rare.title.includes('0종')&&rare.title.includes('EXE 분류표는 미확인'));
  assert.equal(rare.buyDisabled,true);
  assert.equal(rare.sellDisabled,true);
  assert.ok(rare.provenance.includes('역사상 발매 0종'));
  assert.ok(rare.rareLabel.includes('발매 기록 0종'));
  assert.equal(rare.gp,first.gp);assert.deepEqual(rare.owned,first.owned);
  await page.locator('#shop .group-tab[data-group="valuable"]').click();
  assert.ok(await page.locator('#shop-grid .shop-card:not(.shop-empty)').count()>0);
  await page.locator('#shop-era-toggle button[data-era="2002"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9);
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).owned),first.owned);
  assert.deepEqual(errors,[]);
  console.log('R28_ORIGINAL_2004_RARE_UNRELEASED_UI_PASS',JSON.stringify({
   engine,eraOne:'2002 source 3x3',eraTwo:'2004 archived screenshot 4x2',
   historicallyIssuedRareCards:0,realPurchaseInRare:false,otherCategories:'WEB-SOURCE-RECONSTRUCTION',
   historicExeCategoryTable:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R28_ORIGINAL_RARE_FAIL',e.stack||e);process.exit(1)});
