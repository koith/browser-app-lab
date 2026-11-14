'use strict';
/* Source-backed 2003-01-15 six exact changes, real DOM/card/transaction and
 * persistence on 2002/2004 shop eras. All unrelated date prices stay Jan05
 * archive-attributed (not a fabricated Jan15 EXE server-price database). */
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');
const snapshotCode=fs.readFileSync(path.resolve(__dirname,'../original/market-price-snapshots.js'),'utf8');
const sandbox={window:{}};vm.runInNewContext(snapshotCode,sandbox);
const first=sandbox.window.ORIGINAL_LEAF_SHOP_PRICE_SNAPSHOT_20030105;
const delta=sandbox.window.ORIGINAL_LEAF_SHOP_PRICE_CHANGES_20030115;
const expected={'노포크':[1350,1400],'마르자나':[5100,5500],'자바카스':[1150,1300],
 '크리스티나':[1700,1900],'죠안':[7000,7500],'흑태자':[115000,118000]};
assert.equal(delta.source,'https://4leafmemorial.geld.kr/1454');
assert.equal(delta.verifiedChangedEntries,6);
assert.deepEqual(Object.keys(delta.changes).sort(),Object.keys(expected).sort());
for(const [name,[before,after]] of Object.entries(expected)){
 assert.equal(first.prices[name],before);
 assert.equal(delta.changes[name].before,before);
 assert.equal(delta.changes[name].after,after);
}
(async()=>{
 const mode=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (mode==='webkit'?webkit:chromium).launch({
  headless:true,args:mode==='chromium'?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const readCards=async()=>{
  // Always begin at page one: changing archival dates must not silently
  // change the paging cursor left by the previous full-shop scan.
  await page.locator('#shop .group-tab[data-group="all"]').click();
  const found=new Map();
  for(let turn=0;turn<16;turn++){
   const rows=await page.$$eval('#shop-grid .shop-card:not(.shop-empty)',nodes=>nodes.map(n=>({
    id:n.dataset.cardId,name:n.querySelector('b')?.textContent,price:Number(n.title.match(/([0-9,]+)GP/)?.[1]?.replaceAll(',','')),
    title:n.title
   })));
   for(const r of rows)found.set(r.name,r);
   const next=page.locator('#shop-next');
   if(await next.isDisabled())break;
   await next.click();
  }
  return Object.fromEntries(found);
 };
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_HISTORIC_MARKET__);
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden) #shop-market-date');
  assert.equal(await page.locator('#shop-market-date').inputValue(),'2003-01-05');
  let jan05=await readCards();
  assert.ok(Object.keys(jan05).length>=90,'real source card inventory is rendered');
  for(const [name,[before]] of Object.entries(expected)){
   assert.equal(jan05[name]?.price,before,'Jan05 source price '+name);
   assert.ok(jan05[name].title.includes('2003.01.05 기록 시세'));
  }
  await page.selectOption('#shop-market-date','2003-01-15');
  assert.equal(await page.evaluate(()=>window.__LEAF_HISTORIC_MARKET__.getState().changedPrices),6);
  let jan15=await readCards();
  assert.equal(Object.keys(jan15).length,Object.keys(jan05).length);
  let changes=0;
  for(const [name,older] of Object.entries(jan05)){
   const now=jan15[name];assert.ok(now,'same roster '+name);
   if(older.price!==now.price){
    changes++;assert.equal(now.price,expected[name]?.[1],'only six source-documented changes');
    assert.ok(now.title.includes('2003.01.15 변경 시세'));
   }else{
    assert.ok(!now.title.includes('2003.01.15 변경 시세'),
     'unverified Jan15 price cannot pretend to be proven: '+name);
   }
  }
  assert.equal(changes,6);
  const provenance=await page.locator('#shop-era-provenance').textContent();
  assert.ok(provenance.includes('6종만 확정')&&provenance.includes('미검증'));
  // Use ordinary user-owned and GP data, not test-only mint/purchase APIs.
  await page.evaluate(()=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));
   p.gp=200000;localStorage.setItem('rog_profile',JSON.stringify(p));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_HISTORIC_MARKET__);
  assert.equal(await page.evaluate(()=>window.__LEAF_HISTORIC_MARKET__.getState().date),'2003-01-15');
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  const findCard=async name=>{
   await page.locator('#shop .group-tab[data-group="all"]').click();
   for(let n=0;n<16;n++){
    const card=page.locator('#shop-grid .shop-card:not(.shop-empty)').filter({hasText:name}).first();
    if(await card.count()&&await card.locator('b').textContent()===name)return card;
    const next=page.locator('#shop-next');if(await next.isDisabled())break;
    await next.click();
   }
   throw Error('missing source card: '+name);
  };
  const unowned=await findCard('노포크');
  assert.equal(await unowned.getAttribute('data-owned'),'false');
  await unowned.click();
  const gpBefore=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).gp);
  await page.locator('#shop-buy').click();
  assert.ok((await page.locator('#modal-content').textContent()).includes('1,400GP'));
  // A changing archival date invalidates the original quote; it must not
  // silently debit one GP figure while displaying another price.
  await page.evaluate(()=>window.__LEAF_HISTORIC_MARKET__.setDate('2003-01-05'));
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).gp),gpBefore);
  assert.ok((await page.locator('#modal-content').textContent()).includes('변경'));
  await page.locator('#modal-buttons button').filter({hasText:'확인'}).click();
  await page.selectOption('#shop-market-date','2003-01-15');
  const candidate=await findCard('노포크');const id=await candidate.getAttribute('data-card-id');
  await candidate.click();await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(card=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(card),id);
  const bought=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(bought.gp,gpBefore-1400,'exact 2003-01-15 price actually charged');
  assert.equal(bought.owned.filter(x=>x===id).length,1);
  await page.reload();await page.waitForFunction(()=>window.__LEAF_HISTORIC_MARKET__);
  assert.equal(await page.evaluate(()=>window.__LEAF_HISTORIC_MARKET__.getState().date),'2003-01-15');
  const restored=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(restored.gp,bought.gp);assert.ok(restored.owned.includes(id));
  await page.locator('[data-route="shop"]').first().click();
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),8,'2004 source screenshot 4x2 mode unaffected');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-r24-source-2003-jan15-six-exact-prices-'+mode+'.png'});
  console.log('R24_ORIGINAL_2003_MARKET_LIVE_PASS',JSON.stringify({
   mode,archivalPrices:Object.keys(jan05).length,verifiedChanges:changes,
   beforeGp:gpBefore,spent:1400,afterGp:bought.gp,stored:true,
   oldPriceQuoteRefused:true,eraComparison:'2002-3x3/2004-4x2',rarity2004:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R24_ORIGINAL_MARKET_FAIL',e.stack||e);process.exit(1)});
