'use strict';
/* SHOP-02 regression: legacy account imports may encode GP as a string.
 * Selling must ADD numbers, never concatenate strings. Invalid/overflow
 * values must fail closed without minting any currency or cards.
 * Original resale policy is NOT claimed verified by this test. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(
  engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const ctx=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  const saved=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  await page.goto(base);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SHOP_NATIVE__);
  await page.evaluate(()=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));p.gp='1000000';
   localStorage.setItem('rog_profile',JSON.stringify(p));
  });
  await page.reload();
  await page.locator('[data-route="shop"]').first().click();
  const card=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
  assert.ok(await card.count(),'source shop contains at least one purchasable item');
  const id=await card.getAttribute('data-card-id');
  await card.click();
  const before=await saved();
  assert.equal(typeof before.gp,'string','legacy string GP fixture is active');
  const quoted=await page.locator('#shop-selected').textContent();
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(id=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),id);
  const bought=await saved();
  assert.equal(typeof bought.gp,'number','buy normalizes GP into exact integer');
  assert.ok(bought.gp<1000000,'buy deducts actual price');
  const sell=page.locator('#shop-sell');
  assert.equal(await sell.isDisabled(),false,'new card is not equipped');
  const refund=Number(await sell.getAttribute('data-resale-gp'));
  assert.ok(Number.isSafeInteger(refund)&&refund>=0,'quote must be safe integer');
  await sell.click();
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).click();
  await page.waitForFunction(id=>!JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),id);
  const sold=await saved();
  assert.equal(sold.gp,bought.gp+refund,'sale adds numeric GP, never concatenates string digits');
  assert.equal(typeof sold.gp,'number');
  await page.reload();
  const reloaded=await saved();
  assert.equal(reloaded.gp,sold.gp,'actual reload retains consistent GP');

  // Invalid/overflow persisted balances must never permit real transactions.
  for(const invalid of ['Infinity','not-a-number','9007199254740999']){
   await page.evaluate(gp=>{
    const p=JSON.parse(localStorage.getItem('rog_profile'));p.gp=gp;
    localStorage.setItem('rog_profile',JSON.stringify(p));
   },invalid);
   await page.reload();
   await page.locator('[data-route="shop"]').first().click();
   const available=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
   await available.click();
   const prior=await page.evaluate(()=>localStorage.getItem('rog_profile'));
   await page.locator('#shop-buy').click();
   if(await page.locator('#modal-title').textContent()==='매직카덴 GP 확인 필요'){
    // Guard rejected the malformed number before showing a confirmation.
   }else{
    await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
   }
   const after=await page.evaluate(()=>localStorage.getItem('rog_profile'));
   assert.equal(after,prior,'invalid GP must not mint cards/credits: '+invalid);
   assert.match(await page.locator('#modal-content').textContent(),/올바르지 않/);
   await page.locator('#modal-buttons button').first().click();
  }
  console.log('SOURCE CARDSHOP IMPORTED GP PASS '+engine+' '+JSON.stringify({
   cardId:id,initialGP:1000000,boughtGP:bought.gp,soldGP:sold.gp,
   resaleStatus:'not-historically-verified',invalidCases:3,quote:quoted.slice(0,60)
  }));
  await ctx.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE CARDSHOP IMPORTED GP FAILED',e.stack||e);process.exit(1)});
