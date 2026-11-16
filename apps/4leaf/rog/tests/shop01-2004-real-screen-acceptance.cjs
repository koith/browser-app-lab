'use strict';
/* Historical 2004 4LEAF shop_ref.png visual anchors, NOT guessed user
 * graphics. A surviving image is a 541x402 scaled version of the original
 * 794px client; native 794x404 shop starts about screenshot y=44.
 * Pixel anchors were hand traced from the reference source, not from
 * our CSS. Never count exact CardData face/sales rules as restored.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const source=fs.readFileSync(path.resolve(__dirname,'../../assets/shop_ref.png'));
assert.equal(source.subarray(0,8).toString('hex'),'89504e470d0a1a0a','source must be unmodified archival screenshot');
const sourceSize=[source.readUInt32BE(16),source.readUInt32BE(20)];
assert.deepEqual(sourceSize,[541,402],'surviving 4LEAF historical shop screen resolution changed');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const approx=(got,want,name,tol=4)=>assert.ok(Math.abs(got-want)<=tol, name+' native traced landmark '+got+' is not '+want+' ±'+tol);
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__&&window.__LEAF_SHOP_STAGE__&&window.__ROG_TEST__);
  await page.evaluate(()=>{
   const raw=JSON.parse(localStorage.getItem('rog_profile'));
   const owned=window.ORIGINAL_LEAF_CHESSMEN.filter(c=>c.move>=1&&c.move<=2&&c.atk>=1&&c.def>=1)
    .slice(0,23).map(c=>'c_'+c.id);
   raw.owned=[...new Set([...raw.owned,...owned])];
   raw.gp=1000000;
   localStorage.setItem('rog_profile',JSON.stringify(raw));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__&&window.__LEAF_SHOP_STAGE__&&window.__ROG_TEST__);
  await page.locator('[data-route="shop"]').first().click();
  await page.locator('#shop:not(.hidden)').waitFor();
  await page.waitForFunction(()=>window.__LEAF_SHOP_STAGE__.getState().scale>0.05);
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__.getState().era==='2004');
  const landmark=await page.evaluate(()=>{
   const stage=document.querySelector('#shop-native-stage'),sr=stage.getBoundingClientRect();
   const factor=sr.width/794;
   const relative=el=>{
    if(!el)return null;const r=el.getBoundingClientRect();
    return {x:Math.round((r.left-sr.left)/factor),y:Math.round((r.top-sr.top)/factor),
     w:Math.round(r.width/factor),h:Math.round(r.height/factor)};
   };
   const $=s=>stage.querySelector(s),cards=[...stage.querySelectorAll('#shop-grid .shop-card')];
   return {stageSource:stage.dataset.source,era:stage.dataset.era,screenSize:[794,404],
    tabs:['normal','valuable','rare'].map(g=>relative($('.group-tab[data-group="'+g+'"]'))),
    cards:cards.map(relative),cardIds:cards.map(c=>c.dataset.cardId),
    grid:relative($('#shop-grid')),inventory:relative($('.shop-equipped')),detail:relative($('.shop-detail')),
    money:relative($('.shop-keeper .money')),buy:relative($('#shop-buy')),sell:relative($('#shop-sell')),
    ownedScroll:$('#shop-owned-list').scrollHeight,ownedBox:$('#shop-owned-list').clientHeight,
    ownedRealRows:$('#shop-owned-list').querySelectorAll('.shop-owned-entry').length,
    gp:$('#shop-gp').textContent,rare:$('.group-tab[data-group="rare"]').disabled,
    originalBitmap:getComputedStyle(stage).backgroundImage};
  });
  assert.equal(landmark.stageSource,'CardShop/cardshopback.png');
  assert.equal(landmark.era,'2004');
  assert.equal(landmark.cards.length,8);
  assert.equal(new Set(landmark.cards.slice(0,4).map(c=>c.y)).size,1);
  assert.equal(new Set(landmark.cards.slice(4).map(c=>c.y)).size,1);
  assert.equal(new Set(landmark.cards.slice(0,4).map(c=>c.x)).size,4);
  // First row screenshot begins (32,82), source stage top-left offset (0,44),
  // screenshot physical pixels map to 794 / 541 = 1.468 native units.
  const x=k=>Math.round(k*794/541),y=k=>Math.round((k-44)*794/541);
  [['Normal',landmark.tabs[0],22],['Valuable',landmark.tabs[1],91],['Rare',landmark.tabs[2],159]]
   .forEach(([name,r,px])=>{approx(r.x,x(px),name+' x');approx(r.y,y(54),name+' y')});
  [32,89,146,203].forEach((sx,i)=>approx(landmark.cards[i].x,x(sx),'historical 4x2 col '+i,4));
  approx(landmark.cards[0].y,y(82),'historical first card y');
  approx(landmark.cards[4].y,y(144),'historical second card row y');
  for(const [label,r,sx,sy] of [
   ['original equipment list',landmark.inventory,275,66],
   ['original card info',landmark.detail,22,221],
   ['original GP',landmark.money,274,245],
   ['original BUY',landmark.buy,274,271],
   ['original SELL',landmark.sell,344,271]
  ]){approx(r.x,x(sx),label+' x',5);approx(r.y,y(sy),label+' y',6)}
  assert.ok(landmark.ownedRealRows>=20,'real inventory must have all original owned CHR labels');
  assert.ok(landmark.ownedScroll>landmark.ownedBox,'the screenshot item window must scroll with more real items');
  assert.equal(landmark.rare,false,'2004 source screenshot has an actual Rare tab');
  assert.equal(landmark.gp,'1,000,000','native GP field is live currency, not screenshot');
  await page.screenshot({path:'leaf-shop01-historical-2004-trace-'+engine.name()+'.png'});
  // Both native authentic era modes must remain individually interactive.
  await page.locator('#shop .group-tab[data-group="valuable"]').click();
  const valuable=await page.evaluate(()=>[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')]
   .map(b=>({id:b.dataset.cardId,rank:b.dataset.rank})));
  assert.ok(valuable.length>0&&valuable.every(c=>c.rank==='valuable'));
  await page.locator('#shop .group-tab[data-group="normal"]').click();
  const normal=await page.evaluate(()=>[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')]
   .map(b=>({id:b.dataset.cardId,rank:b.dataset.rank})));
  assert.ok(normal.length>0&&normal.every(c=>c.rank==='normal'));
  await page.locator('#shop .group-tab[data-group="rare"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card:not(.shop-empty)').count(),0,
   'historical issued Rare roster must not be fabricated');
  assert.equal(await page.locator('#shop-buy').isDisabled(),true);
  await page.locator('#shop .group-tab[data-group="all"]').click();
  const beforeGP=await page.locator('#shop-gp').textContent();
  const first=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
  assert.ok(await first.count(),'need a real unowned source actor in 8 slots');
  const cardId=await first.getAttribute('data-card-id');
  const price=Number((await first.getAttribute('title')).match(/([0-9,]+)GP/)[1].replaceAll(',',''));
  await first.click();
  const selected=await page.evaluate(()=>({
   id:document.querySelector('#shop-grid .shop-card.selected')?.dataset.cardId,
   details:document.querySelector('#shop-selected')?.textContent,
   currency:document.querySelector('#shop-gp')?.textContent,
   source:document.querySelector('#shop-native-stage')?.dataset.era
  }));
  assert.equal(selected.id,cardId);assert.ok(selected.details.length>15);
  assert.equal(selected.currency,beforeGP);assert.equal(selected.source,'2004');
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(id=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),cardId);
  const bought=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(bought.gp,1000000-price);
  await page.locator('#shop-prev').evaluate(el=>el.scrollIntoView());
  await page.locator('#shop-next').click();
  assert.match(await page.locator('#shop-page').textContent(),/^2 \/ /);
  await page.locator('#shop-prev').click();
  assert.match(await page.locator('#shop-page').textContent(),/^1 \/ /);
  const list=page.locator('#shop-owned-list');
  await list.evaluate(el=>el.scrollTop=el.scrollHeight);
  assert.ok(await list.evaluate(el=>el.scrollTop)>0,'genuine populated list must be wheel/scroll compatible');
  await page.locator('#shop-era-toggle button[data-era="2002"]').click();
  await page.waitForFunction(()=>window.__LEAF_SHOP_ERA__.getState().era==='2002');
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9);
  const preserved=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.deepEqual(preserved.owned,bought.owned);
  assert.equal(preserved.gp,bought.gp);
  assert.deepEqual(errors,[]);
  console.log('SHOP01_HISTORICAL_2004_SOURCE_LANDMARK_AND_LIVE_TRANSACTION_PASS '+JSON.stringify({
   engine:engine.name(),historical:sourceSize,traceScale:'794/541',native:[794,404],
   tabs:landmark.tabs,cards:landmark.cards.map(c=>[c.x,c.y]),
   inventory:landmark.inventory,detail:landmark.detail,GP:landmark.money,
   buy:landmark.buy,sell:landmark.sell,realOwned:landmark.ownedRealRows,
   sourceActorsOnly:true,rareMembership:'no-issued-source-actors',
   cardId,price,purchaseSaved:true,originalCardDataFaceMap:'still-unverified'
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('SHOP01_SOURCE_TRACE_FAILED',e.stack||e);process.exit(1)});
