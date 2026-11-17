'use strict';
/* M02 end-to-end source screen acceptance.
 * UI only: World -> Keltica -> real Magic Carden source building
 * -> original 2004 4x2 shop -> real GP trade -> return to street.
 * All 2004 positions are normalized to the source 794x404 canvas and
 * traced against assets/shop_ref.png (not compared to a fake web screenshot).
 */
const {chromium,webkit,devices}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>window.LEAF_CENTRAL_API_URL='');
  await page.goto(base);
  // Fixture changes only the isolated browser test profile, never the app's
  // starting GP or any real user's account.
  await page.evaluate(()=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));
   p.gp=1000000;
   localStorage.setItem('rog_profile',JSON.stringify(p));
   localStorage.removeItem('4leaf-original-shop-era');
  });
  await page.reload();
  await page.locator('button[data-route="city"]').first().click();
  await page.locator('#city:not(.hidden)').waitFor();
  const street=page.locator('.street-location[data-street="magic"]');
  await street.waitFor();
  await street.click();
  await page.locator('#shop:not(.hidden)').waitFor({timeout:10000});
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9,
   'original 2002 PAK shop must remain the default');
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  const before=await page.evaluate(()=>{
   const stage=document.getElementById('shop-native-stage');
   const rect=stage.getBoundingClientRect(),scale=rect.width/794;
   const geometry=(selector)=>{
    const el=document.querySelector(selector);if(!el)return null;
    const r=el.getBoundingClientRect();
    return [(r.left-rect.left)/scale,(r.top-rect.top)/scale,r.width/scale,r.height/scale]
     .map(n=>+n.toFixed(2));
   };
   return {
    era:window.__LEAF_SHOP_ERA__?.getState?.(),
    count:document.querySelectorAll('#shop-grid .shop-card').length,
    source:stage.dataset.source,art:window.__LEAF_SHOP_STAGE__?.getState?.(),
    geometry:{
     normal:geometry('#shop .group-tab[data-group="normal"]'),
     valuable:geometry('#shop .group-tab[data-group="valuable"]'),
     rare:geometry('#shop .group-tab[data-group="rare"]'),
     first:geometry('#shop-grid .shop-card:first-child'),
     fourth:geometry('#shop-grid .shop-card:nth-child(4)'),
     fifth:geometry('#shop-grid .shop-card:nth-child(5)'),
     detail:geometry('#shop .shop-detail'),
     gp:geometry('#shop .money'),
     buy:geometry('#shop-buy'),sell:geometry('#shop-sell'),
     owned:geometry('#shop .shop-equipped')
    },
    cardInfo:document.querySelector('#shop-selected')?.innerText||'',
    toolbarOutside:!stage.contains(document.querySelector('#shop-era-toggle')),
    visibleTrade:[...document.querySelectorAll('#shop-buy,#shop-sell')].every(e=>{
     const r=e.getBoundingClientRect(),c=getComputedStyle(e);
     return r.width>25&&r.height>10&&c.visibility!=='hidden'&&
      r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;
    })
   };
  });
  assert.equal(before.source,'CardShop/cardshopback.png');
  assert.equal(before.era.era,'2004','2004 screenshot chosen by default');
  assert.equal(before.count,8,'4x2 source layout, not 2002 3x3');
  assert.equal(before.toolbarOutside,true,'web-only timeline controls never obscure original shop art');
  assert.equal(before.visibleTrade,true,'source buy/sell sprites are visible');
  assert.match(before.cardInfo,/Card Info/);
  const target={
   normal:[32,14],valuable:[134,14],rare:[233,14],
   first:[47,56],fourth:[299,56],fifth:[47,147],
   detail:[32,260],gp:[402,294],buy:[400,331],sell:[503,331],owned:[402,32]
  };
  for(const [key,xy]of Object.entries(target)){
   const actual=before.geometry[key];
   assert.ok(actual&&Math.abs(actual[0]-xy[0])<13&&Math.abs(actual[1]-xy[1])<13,
    '2004 screenshot landmark '+key+': '+JSON.stringify({source:actual,reference:xy}));
  }
  const dir='apps/4leaf/rog/tests/.m02-screenshots';
  fs.mkdirSync(dir,{recursive:true});
  const shot=await page.screenshot({path:dir+'/'+engine+'-magic-carden-2004.jpg',type:'jpeg',quality:75});
  if(process.env.M02_IMAGE_LOG==='1')console.log('M02_SCREEN_B64='+shot.toString('base64'));
  // Verify original header controls switch to the distinct recovered 2002 PAK.
  await page.locator('#shop-era-toggle button[data-era="2002"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),9);
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),8);
  await page.locator('#shop .group-tab[data-group="valuable"]').click();
  assert.ok(await page.locator('#shop-grid .shop-card[data-rank="valuable"]').count()>0);
  await page.locator('#shop .group-tab[data-group="normal"]').click();
  const purchase=page.locator('#shop-grid .shop-card[data-owned="false"]').first();
  assert.ok(await purchase.count(),'select a real CardData card');
  const id=await purchase.getAttribute('data-card-id');
  await purchase.click();
  assert.equal(await page.locator('#shop-buy').isDisabled(),false);
  const gpBefore=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')).gp);
  await page.locator('#shop-buy').click();
  await page.locator('#modal-buttons button').filter({hasText:'구매'}).click();
  await page.waitForFunction(id=>JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),id);
  const bought=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.ok(bought.gp<gpBefore,'real purchase deducts GP');
  assert.ok(bought.owned.includes(id),'real purchase persists source chessman');
  const sourcePrice=Number((await page.locator('.source-cardinfo-price').textContent()).replace(/[^0-9]/g,''));
  const resale=Number(await page.locator('#shop-sell').getAttribute('data-resale-gp'));
  const status=await page.locator('#shop-sell').getAttribute('data-resale-status');
  assert.equal(resale,Math.floor(sourcePrice/4),
   '2004 archived non-serial resale uses historically recorded 25% rate');
  assert.equal(status,'historical-retrospective-25pct-not-exe-verified',
   'secondary evidence is never falsely labelled verified original EXE');
  await page.locator('#shop-sell').click();
  await page.locator('#modal-buttons button').filter({hasText:'판매'}).click();
  await page.waitForFunction(id=>!JSON.parse(localStorage.getItem('rog_profile')).owned.includes(id),id);
  const sold=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(sold.gp,bought.gp+resale,
   'normal 2004 CardShop resale adds the exact selected historic quote');
  // Original official 2003-09 operation notice: only a REDEEMED serial card
  // is exchanged for 1,000GP. Exercise that separate provenance path using
  // an isolated profile fixture, not a fabricated public user inventory.
  await page.evaluate(id=>{
   const p=JSON.parse(localStorage.getItem('rog_profile'));
   p.owned.push(id);p.serialRedeemed.push(id);
   localStorage.setItem('rog_profile',JSON.stringify(p));
  },id);
  await page.reload();
  await page.locator('button[data-route="shop"]').first().click();
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  await page.locator('#shop .group-tab[data-group="normal"]').click();
  const serialCard=page.locator('#shop-grid .shop-card[data-card-id="'+id+'"]');
  if(await serialCard.count())await serialCard.click();
  else await page.locator('#shop-owned-list .shop-owned-entry[data-card-id="'+id+'"]').click();
  assert.equal(Number(await page.locator('#shop-sell').getAttribute('data-resale-gp')),1000,
   'only actually serial-redeemed cards earn the verified 1000GP source sale');
  await page.locator('button[data-route="city"]').first().click();
  await page.locator('#city:not(.hidden)').waitFor();
  await street.waitFor({state:'visible'});
  assert.equal(errors.filter(e=>!/Fetch API cannot load|Failed to fetch|Load failed/.test(e)).length,0,
   'no shop runtime errors: '+errors.join(';'));
  console.log('M02 SOURCE SHOP 2004 E2E PASS '+engine,JSON.stringify({id,geometry:before.geometry,from:'Keltica original door',to:'Keltica after buy/sell'}));
  await context.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('M02 SOURCE SHOP 2004 E2E FAILED',e.stack||e);process.exit(1)});
