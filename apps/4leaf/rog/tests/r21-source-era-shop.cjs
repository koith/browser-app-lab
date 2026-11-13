'use strict';
/* 2002 vs 2004 original Magic Carden: REAL live-browser/card/GP/purchase
 * comparison, never paste shop_ref.png over controls. 2004 RARE membership
 * currently unverified and should not be replaced with guessed actors. */
const assert=require('node:assert/strict'),{chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__&&window.__ROG_TEST__&&window.__LEAF_SHOP_STAGE__);
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  await page.waitForFunction(()=>window.__LEAF_SHOP_STAGE__.getState().scale>0.05);
  const source=await page.evaluate(()=>{
   const stage=document.querySelector('#shop-native-stage');
   return {era:window.__LEAF_SHOP_ERA__.getState(),grid:stage.querySelectorAll('.shop-card').length,
    native:stage.dataset.source,rareVisible:getComputedStyle(stage.querySelector('[data-group="rare"]')).display,
    priceSource:window.ORIGINAL_LEAF_SHOP_PRICE_SNAPSHOT_20030105?.source};
  });
  assert.equal(source.era.era,'2002');assert.equal(source.era.pageSize,9);assert.equal(source.grid,9);
  assert.equal(source.native,'CardShop/cardshopback.png');assert.equal(source.rareVisible,'none');
  assert.equal(source.priceSource,'https://4leafmemorial.geld.kr/1451');
  await page.screenshot({path:'leaf-r21-2002-native-shop.png'});
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__.getState().era==='2004');
  let current=await page.evaluate(()=>{
   const st=document.querySelector('#shop-native-stage');
   const grid=st.querySelector('#shop-grid');
   const rect=grid.getBoundingClientRect();
   const cards=[...grid.querySelectorAll('.shop-card')];
   const positions=cards.map(c=>{const box=c.getBoundingClientRect();return [Math.round(box.left),Math.round(box.top)];});
   const rarity=st.querySelector('.group-tab[data-group="rare"]');
   return {count:cards.length,cols:getComputedStyle(grid).gridTemplateColumns,
    rows:getComputedStyle(grid).gridTemplateRows,positions,
    era:st.dataset.era,rareVisible:getComputedStyle(rarity).display,provenance:st.querySelector('#shop-era-provenance').textContent,
    money:document.querySelector('#shop-gp').textContent,inventory:JSON.parse(localStorage.getItem('rog_profile')).owned};
  });
  assert.equal(current.count,8);assert.equal(current.era,'2004');
  assert.notEqual(current.rareVisible,'none');
  assert.equal(new Set(current.positions.map(x=>x[0])).size,4,'2004 screenshot means four visible cards per row');
  assert.equal(new Set(current.positions.map(x=>x[1])).size,2,'2004 screenshot means exactly two rows');
  assert.ok(current.provenance.includes('RARE 명단 미확보'),'no fake 2004 rarity classification');
  const firstOwned=current.inventory;
  await page.screenshot({path:'leaf-r21-2004-native-shop.png'});
  await page.locator('#shop .group-tab[data-group="rare"]').click();
  const rare=await page.evaluate(()=>({
   rareCount:document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)').length,
   disabled:document.querySelector('#shop-buy').disabled,
   status:document.querySelector('#shop-selected').textContent,
   GP:document.querySelector('#shop-gp').textContent,
   inventory:JSON.parse(localStorage.getItem('rog_profile')).owned}));
  assert.equal(rare.rareCount,0);
  assert.equal(rare.disabled,true);
  assert.ok(rare.status.includes('분류표'));
  assert.equal(rare.GP,current.money);assert.deepEqual(rare.inventory,firstOwned);
  await page.locator('#shop .group-tab[data-group="all"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),8);
  // Credit a local test profile only. Then verify a real purchase from
  // the 2004 reconstruction persists when reopening the genuine 2002 view.
  await page.evaluate(()=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));p.gp=1000000;
   localStorage.setItem('rog_profile',JSON.stringify(p));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__&&window.__ROG_TEST__);
  assert.equal(await page.evaluate(()=>window.__LEAF_SHOP_ERA__.getState().era),'2004','era persisted on reload');
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  const unowned=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
  assert.ok(await unowned.count(),'original CHR inventory has purchasable item in 4x2 source-based view');
  const card=await unowned.getAttribute('data-card-id');
  const gpBefore=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).gp);
  const price=Number((await unowned.getAttribute('title')).match(/([0-9,]+)GP/)[1].replaceAll(',',''));
  await unowned.click();
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(id=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),card);
  const afterBuy=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(afterBuy.gp,gpBefore-price);
  await page.locator('#shop-era-toggle button[data-era="2002"]').click();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__.getState().era==='2002');
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9);
  const afterSwitch=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.deepEqual(afterSwitch.owned,afterBuy.owned);
  assert.equal(afterSwitch.gp,afterBuy.gp);
  await page.locator('#shop-owned-list .shop-owned-entry[data-card-id="'+card+'"]').click();
  assert.equal(await page.locator('#shop-sell').isDisabled(),false);
  await page.locator('#shop-sell').click();
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).click();
  await page.waitForFunction(id=>!JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),card);
  const afterSell=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(afterSell.gp,afterBuy.gp+Math.floor(price/2),
   'WEB-inferred sale policy stays independent of 2004 UI version');
  assert.deepEqual(afterSell.owned,firstOwned);
  assert.deepEqual(errors,[]);
  console.log('R21_2002_2004_REAL_SHOP_MODE_AND_GP_PASS',JSON.stringify({
   engine,nativeAtlas:source.native,era2004:{rows:2,columns:4,rareOriginalMembership:'UNVERIFIED'},
   purchased:card,price,gpBefore,gpAfterBuy:afterBuy.gp,gpAfterSell:afterSell.gp,
   originalPriceArchive:source.priceSource
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('R21_SOURCE_ERA_SHOP_FAILED',e.stack||e);process.exit(1)});
