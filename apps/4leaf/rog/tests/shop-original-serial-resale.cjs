'use strict';
/* Official 4LEAF Sept 2003 notice: a card GRANTED by a historical serial
 * registration sells for exactly 1,000 GP. A shop-purchased card's resale
 * uses the secondary historic 25% rule, not an invented original server table.
 * No fake serial validation.
 * https://4leafmemorial.geld.kr/959
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await browserType.launch({headless:true,args:browserType===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{
   window.LEAF_CENTRAL_API_URL='';
   const real=Storage.prototype.setItem;
   Storage.prototype.setItem=function(key,value){
    if(this===localStorage&&key==='rog_profile'&&
       sessionStorage.getItem('__leaf_serial_quota_test')==='1')
     throw new DOMException('Source-card save quota', 'QuotaExceededError');
    return real.call(this,key,value);
   };
  });
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_CHESSMEN);
  // A previously verified/imported original-profile record, NOT fabricated
  // live serial authentication, is the only allowed provenance source.
  await page.evaluate(()=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));
   p.serialRedeemed=['c_0045','c_0045','c_9999']; // duplication and invalid ID must not survive migration
   localStorage.setItem('rog_profile',JSON.stringify(p));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__);
  await page.locator('[data-route="shop"]').first().click();
  await page.locator('#shop:not(.hidden)').waitFor();
  await page.locator('#shop-grid .shop-card[data-card-id="c_0045"]').click();
  const original=await page.locator('#shop-sell').evaluate(el=>({
   disabled:el.disabled,source:el.dataset.resaleStatus,gp:Number(el.dataset.resaleGp),title:el.title
  }));
  assert.equal(original.disabled,false,'non-equipped real owned card must remain sellable');
  assert.equal(original.gp,1000,'original serial redemption re-sell is exactly 1000 GP');
  assert.equal(original.source,'original-2003-serial-redemption-1000gp');
  assert.match(original.title,/2003년 시리얼 등록 카드/);
  const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  const rawBefore=await page.evaluate(()=>localStorage.getItem('rog_profile'));
  const button=page.locator('#shop-sell');
  // A failed persistent write must roll back GP, card and SERIAL origin, not
  // just the purchase cost, so an authentic one-time resale can be retried.
  await page.evaluate(()=>sessionStorage.setItem('__leaf_serial_quota_test','1'));
  await button.click();
  assert.match(await page.locator('#modal-content').textContent(),/시리얼 등록 카드 재판매 1,000 GP/);
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).click();
  assert.match(await page.locator('#modal-title').textContent(),/저장 실패/);
  assert.equal(await page.evaluate(()=>localStorage.getItem('rog_profile')),rawBefore);
  const quoteAfterFailure=await page.locator('#shop-sell').evaluate(el=>({
   gp:Number(el.dataset.resaleGp),source:el.dataset.resaleStatus
  }));
  assert.equal(quoteAfterFailure.gp,1000);
  assert.equal(quoteAfterFailure.source,'original-2003-serial-redemption-1000gp');
  await page.locator('#modal-buttons button').filter({hasText:'확인'}).click();
  await page.evaluate(()=>sessionStorage.removeItem('__leaf_serial_quota_test'));
  await button.click();
  assert.match(await page.locator('#modal-content').textContent(),/시리얼 등록 카드 재판매 1,000 GP/);
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).click();
  await page.waitForFunction(()=>!JSON.parse(localStorage.getItem('rog_profile')).owned.includes('c_0045'));
  const sold=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(sold.gp,before.gp+1000,'actual GP balance must receive exact original payment');
  assert.ok(!sold.owned.includes('c_0045'));
  assert.deepEqual(sold.serialRedeemed,[],'selling a redeemed card consumes its provenance');
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__);
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).serialRedeemed),[]);
  await page.locator('[data-route="shop"]').first().click();
  await page.locator('#shop-grid .shop-card[data-card-id="c_0045"]').click();
  const purchase=await page.locator('#shop-grid .shop-card[data-card-id="c_0045"]').getAttribute('title');
  const price=Number(purchase.match(/([0-9,]+)GP/)[1].replaceAll(',',''));
  assert.ok(sold.gp>=price,'fixture should afford normal purchase');
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(()=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes('c_0045'));
  const bought=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(bought.gp,sold.gp-price,'actual ordinary GP purchase deducted exactly the historical date price');
  assert.deepEqual(bought.serialRedeemed,[],'buying with GP must NOT make a fake serial registration');
  await page.locator('#shop-grid .shop-card[data-card-id="c_0045"]').click();
  const ordinary=await page.locator('#shop-sell').evaluate(el=>({
   gp:Number(el.dataset.resaleGp),source:el.dataset.resaleStatus,title:el.title
  }));
  assert.equal(ordinary.source,'historical-secondary-2002-2004-resale-25pct',
   'ordinary cards use documented retrospective 25%, not serial redemption');
  assert.equal(ordinary.gp,Math.floor(price/4),'secondary historical ordinary resale rate');
  assert.match(ordinary.title,/25%.*원본 서버 계산식 미확인/);
  await page.screenshot({path:'leaf-archival-serial-resale-real-shop-'+browserType.name()+'.png'});
  assert.deepEqual(errors,[]);
  console.log('4LEAF_OFFICIAL_2003_SERIAL_CARD_RESALE_PASS',JSON.stringify({
   browser:browserType.name(),official1000:original.gp,gpBefore:before.gp,gpAfter:sold.gp,
   ordinaryPurchase:price,ordinarySource:ordinary.source,ordinaryFallback:ordinary.gp,
   actualSavedAndReloaded:true,noFakeSerialMinting:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_OFFICIAL_2003_SERIAL_CARD_RESALE_FAILED',e.stack||e);process.exit(1)});
