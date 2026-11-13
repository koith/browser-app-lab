'use strict';
/* SHOP-02 source vs web-price test: exact Jan 5, 2003 public newspaper
 * market snapshot, no invented prices for 14 unmatched source CHR names
 * and no conflation with separate serial-code redemption resale rules. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'original/market-price-snapshots.js'),'utf8');
const sandbox={window:{}};vm.runInNewContext(source,sandbox);
const snapshot=sandbox.window.ORIGINAL_LEAF_SHOP_PRICE_SNAPSHOT_20030105;
const chessmen=JSON.parse(fs.readFileSync(path.join(root,'original/chessmen.json'),'utf8'));
assert.equal(snapshot.date,'2003-01-05');
assert.equal(snapshot.source,'https://4leafmemorial.geld.kr/1451');
assert.equal(snapshot.historicalExeRetailTableExtracted,false);
assert.equal(Object.keys(snapshot.prices).length,97);
const matched=chessmen.filter(c=>Object.hasOwn(snapshot.prices,c.name));
assert.equal(chessmen.length,98);assert.equal(matched.length,84);
assert.equal(snapshot.prices['마르자나'],5100);
assert.equal(snapshot.prices['살라딘'],37000);
assert.equal(snapshot.prices['흑태자'],115000);
assert.equal(snapshot.prices['솔져'],50);
assert.equal(snapshot.serializedCardResale2003Jan15GP,1000);
assert.equal(snapshot.serializedCardResaleAppliesToNormalBoughtCards,false);
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_SHOP_PRICE_SNAPSHOT_20030105);
  await page.evaluate(()=>window.__ROG_TEST__.go('shop'));
  await page.waitForSelector('#shop:not(.hidden) #shop-grid');
  const observed=[],seen=new Set();
  for(let pageNo=0;pageNo<15;pageNo++){
   const rows=await page.$$eval('#shop-grid .shop-card:not(.shop-empty)',nodes=>nodes.map(n=>({
    card:n.dataset.cardId,name:n.querySelector('b')?.textContent,
    title:n.title,priceText:n.title.match(/([0-9,]+)GP/)?.[1]
   })));
   for(const row of rows){
    assert.ok(!seen.has(row.card),'shop page iteration must not duplicate original source cards');
    seen.add(row.card);observed.push(row);
    if(Object.hasOwn(snapshot.prices,row.name)){
     assert.equal(Number(row.priceText.replaceAll(',','')),snapshot.prices[row.name],
      'real shop must use historical 2003 price for '+row.name);
     assert.ok(row.title.includes('2003.01.05 기록 시세'));
    }else assert.ok(row.title.includes('웹 추정가격'),'unknown historic price must stay labeled');
   }
   const next=page.locator('#shop-next');
   if(await next.isDisabled())break;
   await next.click();
  }
  assert.ok(observed.length>=80,'traverse full source shop stock, not first 9 alone');
  assert.ok(observed.some(r=>r.name==='마르자나'&&r.priceText==='5,100'));
  assert.ok(observed.some(r=>r.name==='흑태자'&&r.priceText==='115,000'));
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-r20-historic-market-shop.png'});
  console.log('R20_REAL_2003_MAGIC_CARDEN_97_PRICES_PASS',JSON.stringify({
   archivalEntries:Object.keys(snapshot.prices).length,matchedByExactName:matched.length,
   renderedItems:observed.length,source:snapshot.source,
   historicSerialRedemptionResale:'1000GP/serial-only',generalResale:'WEB-INFERRED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R20_HISTORICAL_2003_SHOP_PRICES_FAIL',e.stack||e);process.exit(1)});
