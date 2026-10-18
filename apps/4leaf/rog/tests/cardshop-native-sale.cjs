'use strict';
/* Native 2002 CardShop actual buy/sell GUI and stateful GP transaction QA.
 * Source authenticity is limited to source atlas button pixels and 9
 * card backs. 50% resale is explicitly INFERRED WEB economy policy.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SHOP_NATIVE__);
  // Local source-based test account, never credit GP to a real online user.
  await page.evaluate(()=>{
   const raw=JSON.parse(localStorage.getItem('rog_profile'));
   raw.gp=1000000;
   localStorage.setItem('rog_profile',JSON.stringify(raw));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SHOP_NATIVE__);
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9,
   'source CardShop/cardshopback.png has 3 columns by 3 rows, do not mistakenly replace with different-version 4x2 screenshot');
  const oldOwned=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).owned);
  const first=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
  assert.ok(await first.count(),'at least one purchasable unowned archive chessman appears');
  const cardId=await first.getAttribute('data-card-id');
  await first.click();
  const before=await page.evaluate(()=>({
   source:new URL('./original/CardShop/cardshopbutton.png',location.href).pathname,
   button:getComputedStyle(document.querySelector('#shop-sell')).backgroundImage,
   pos:getComputedStyle(document.querySelector('#shop-sell')).backgroundPosition,
   old:Number(JSON.parse(localStorage.getItem('rog_profile')).gp),
   disabled:document.querySelector('#shop-sell').disabled,
   title:document.querySelector('#shop-sell').title,
   scene:document.querySelector('#shop-native-stage').dataset.source
  }));
  assert.equal(before.disabled,true,'cannot sell a card not owned');
  assert.ok(before.button.includes('original/CardShop/cardshopbutton.png'));
  assert.equal(before.pos,'-294px -481px','source original disabled 판매하기 98x21 frame');
  assert.equal(before.scene,'CardShop/cardshopback.png');
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).first().click();
  await page.waitForFunction(id=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),cardId);
  const afterBuy=await page.evaluate(()=>({
   p:JSON.parse(localStorage.getItem('rog_profile')),
   enabled:!document.getElementById('shop-sell').disabled,
   sellGp:Number(document.getElementById('shop-sell').dataset.resaleGp),
   known:document.getElementById('shop-sell').dataset.resaleStatus,
   pos:getComputedStyle(document.getElementById('shop-sell')).backgroundPosition,
   clickTarget:(()=>{
    const el=document.getElementById('shop-sell'),r=el.getBoundingClientRect();
    return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.id;
   })()
  }));
  assert.ok(afterBuy.p.owned.includes(cardId),'real chessman added to saved inventory');
  assert.equal(afterBuy.enabled,true,'newly purchased un-equipped card may be sold');
  assert.equal(afterBuy.known,'inferred-web-price-not-original',
   'never misrepresent 50% resale as confirmed original rule');
  assert.equal(afterBuy.pos,'0px -481px','genuine 판매하기 original first-frame atlas');
  assert.equal(afterBuy.clickTarget,'shop-sell',
   'source sale button must be physically clickable below open inventory');
  assert.ok(afterBuy.p.gp<before.old,'purchase reduces actual GP');
  await page.locator('#shop-sell').click();
  assert.ok((await page.locator('#modal-content').textContent()).includes('원작 재판매 가격 규칙 미확인'));
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).first().click();
  await page.waitForFunction(id=>!JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),cardId);
  const afterSell=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(afterSell.gp,afterBuy.p.gp+afterBuy.sellGp,'confirmed sale GP credited exactly once');
  assert.deepEqual(afterSell.owned,oldOwned,'one buy and one sale restore original inventory');
  assert.ok(afterSell.team.every(id=>afterSell.owned.includes(id)),
   'sale must not delete a currently equipped original chessman');
  await page.reload();
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  const persisted=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(persisted.gp,afterSell.gp,'after reload GP still matches');
  assert.deepEqual(persisted.owned,oldOwned,'after reload source roster still matches');
  // An actor participating in the current party is never removed.
  const protectedId=persisted.team[0];
  const ownedItem=page.locator('#shop-owned-list .shop-owned-entry[data-card-id="'+protectedId+'"]');
  assert.ok(await ownedItem.count(),'equipped source chessman selectable in real owned list');
  await ownedItem.click();
  assert.equal(await page.locator('#shop-sell').isDisabled(),true,
   'cannot sell equipped card while a user party uses it');
  await page.screenshot({path:'leaf-original-cardshop-buy-sell-native.png'});
  assert.deepEqual(errors,[],'real shop resale causes no browser exceptions');
  console.log('ORIGINAL SOURCE CARDSHOP BUY/SELL PASS',JSON.stringify({
   source:'CardShop/cardshopbutton.png',grid:'3x3-native-atlas',
   buyCard:cardId,protectedCard:protectedId,resalePolicy:'WEB-inferred-50-percent',
   gpBefore:before.old,gpAfterBuy:afterBuy.p.gp,
   gpAfterSell:afterSell.gp,saleCredit:afterBuy.sellGp,
   sameInventoryAfterRoundtrip:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE SOURCE CARDSHOP BUY/SELL FAILED',e.stack||e);process.exit(1)});
