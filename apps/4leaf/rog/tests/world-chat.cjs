const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('path');
(async()=>{
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const a=await browser.newContext({viewport:{width:1280,height:800}});
 // Offline visual QA deliberately uses inter-tab transport.
 // Real server behavior has independent central-browser.cjs E2E tests.
 await a.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const host=await a.newPage(),guest=await a.newPage(); // same browser storage partition: actual peer tabs
 const errors=[],missingAssets=[];
 for(const [who,page] of [['host',host],['guest',guest]]){
   page.on('pageerror',e=>{errors.push(who+': '+e.stack);console.error('PAGE ERROR',who,e.stack)});
   page.on('console',m=>{if(m.type()==='error')console.log('PAGE LOG ERROR',who,m.text())});
   page.on('response',res=>{if(res.status()===404){console.log('RESOURCE 404',who,res.url());if(/\/original\//.test(res.url()))missingAssets.push(who+': '+res.url())}});
 }
 await Promise.all([host.goto(url),guest.goto(url)]);
 await Promise.all([
  host.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000}),
  guest.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000})
 ]);
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'original WorldMap first');
 // Native 4LEAF MainFrame title bitmap replaces fabricated textual logo.
 const nativeFrame=await host.evaluate(()=>{
  const title=document.querySelector('#app>.titlebar');
  const style=getComputedStyle(title);
  return {height:title.getBoundingClientRect().height,
   image:style.backgroundImage,logo:getComputedStyle(title.querySelector('.win-logo')).display,
   fakeTitle:getComputedStyle(title.querySelector('b')).display,
   buttons:[...title.querySelectorAll('.window-buttons span')].map(el=>getComputedStyle(el).backgroundImage)};
 });
 assert.equal(nativeFrame.height,54,'desktop 4LEAF title uses original 54px native art height');
 assert.ok(nativeFrame.image.includes('original/MainFrame/title.png'),'native source logo, not fake text rendering');
 assert.equal(nativeFrame.logo,'none','hide the invented duplicate clover logo');
 assert.equal(nativeFrame.fakeTitle,'none','source bitmap already contains native 4LEAF wordmark');
 assert.ok(nativeFrame.buttons.every(x=>x.includes('original/MainFrame/borderbtn.png')),
  'native source window-button atlas is used');


 // Every native WorldMap four-frame region was measured against the original
 // 796x528 WorldMapBack source bitmap, not against a manually staged screenshot.
 await host.waitForFunction(()=>{
  const background=document.querySelector('#leaf-world-stage .world-backdrop');
  const sprites=[...document.querySelectorAll('#leaf-world-stage canvas.world-sprite')];
  return background?.dataset.ready==='true'&&sprites.length===6
    &&sprites.every(c=>c.dataset.ready==='true');
 },null,{timeout:19000});
 const worldSourceRegistration=await host.evaluate(()=>{
  const stage=document.querySelector('#leaf-world-stage');
  const bg=stage.querySelector('.world-backdrop');
  const reference=document.createElement('canvas');reference.width=bg.naturalWidth;
  reference.height=bg.naturalHeight;
  const bx=reference.getContext('2d',{willReadFrequently:true});
  bx.drawImage(bg,0,0);
  const full=bx.getImageData(0,0,reference.width,reference.height).data;
  const expected=[
   {name:'street',x:265,y:33,w:203,h:112},
   {name:'knights',x:144,y:96,w:203,h:218},
   {name:'north',x:305,y:113,w:268,h:140},
   {name:'south',x:200,y:205,w:239,h:139},
   {name:'dice',x:383,y:280,w:198,h:133},
   {name:'my4leaf',x:500,y:162,w:138,h:147}
  ];
  return [...stage.querySelectorAll('canvas.world-sprite')].map((canvas,i)=>{
   const want=expected[i],left=parseFloat(canvas.style.left),top=parseFloat(canvas.style.top);
   const pixels=canvas.getContext('2d',{willReadFrequently:true}).getImageData(0,0,canvas.width,canvas.height).data;
   let n=0,diff=0,transparent=0;
   for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++){
    const p=(y*canvas.width+x)*4;
    if(pixels[p+3]<12){transparent++;continue}
    const q=((top+y)*reference.width+left+x)*4;
    for(let k=0;k<3;k++){diff+=Math.abs(pixels[p+k]-full[q+k]);n++}
   }
   return {name:want.name,x:left,y:top,w:canvas.width,h:canvas.height,
    expected:want,meanError:diff/n,visiblePixels:n/3,transparent};
  });
 });
 assert.equal(worldSourceRegistration.length,6,'all six independently rendered native WorldMap sprites');
 for(const measured of worldSourceRegistration){
  const {expected,...actual}=measured;
  assert.deepEqual(
   [actual.x,actual.y,actual.w,actual.h],
   [expected.x,expected.y,expected.w,expected.h],
   measured.name+' exact native 796x528 backdrop pixel registration');
  assert.ok(measured.meanError<12&&measured.visiblePixels>1500&&measured.transparent>500,
   measured.name+' matches native bitmap without mismatched chroma-key: '+JSON.stringify(measured));
 }


 // The archived WorldMap/notice.png (184×61) contains the original winged
 // "Notice" panel. Verify green chroma key removal and native text hitbox,
 // not a fabricated CSS tooltip or an unrelated modern caption.
 await host.waitForFunction(()=>[...document.querySelectorAll('#sky .world-location-tip')].length===6
  &&[...document.querySelectorAll('#sky .world-location-tip')].every(t=>t.dataset.ready==='true'),
  null,{timeout:15000});
 const nativeNotice=await host.evaluate(async()=>{
  const tip=document.querySelector('#sky .world-location-tip');
  const background=tip.style.backgroundImage;
  const png=background.slice(5,-2);
  const img=new Image();img.src=png;await img.decode();
  const pixels=document.createElement('canvas');pixels.width=img.naturalWidth;pixels.height=img.naturalHeight;
  const ctx=pixels.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
  const alpha=ctx.getImageData(0,0,1,1).data[3];
  const style=getComputedStyle(tip);
  return {source:tip.dataset.source,bitmap:[img.naturalWidth,img.naturalHeight],
   cornerAlpha:alpha,width:parseFloat(style.width),height:parseFloat(style.height),
   background:background.startsWith('url("data:image/png;base64,'),
   caption:document.querySelector('#sky .world-map-caption')?getComputedStyle(document.querySelector('#sky .world-map-caption')).display:'none'};
 });
 assert.equal(nativeNotice.source,'WorldMap/notice.png','original winged Notice sprite is used for world region hints');
 assert.deepEqual(nativeNotice.bitmap,[184,61],'native Notice sprite is kept at original 184×61 size');
 assert.equal(nativeNotice.cornerAlpha,0,'pure-green chroma key is removed rather than shown on world art');
 assert.deepEqual([nativeNotice.width,nativeNotice.height],[184,61],'hover panel geometry is source-native');
 assert.ok(nativeNotice.background,'chroma-keyed sprite is composed into a real RGBA image');
 assert.equal(nativeNotice.caption,'none','invented WorldMap reconstruction caption must not overlay source art');

 // The original ChatRoom/header is a separate source sprite, not decorative
 // text. It must load from PAK, key out transparent green and remain legible.
 await host.waitForFunction(()=>document.querySelector('#social-original-userlist')?.dataset.ready==='true',null,{timeout:12000});
 const originalListHeader=await host.evaluate(()=>{
  const c=document.getElementById('social-original-userlist');
  const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let transparent=0,visible=0,leakedGreen=0;
  for(let i=0;i<data.length;i+=4){
   if(data[i+3]===0)transparent++;else{
    visible++;if(data[i+1]>220&&data[i]<65&&data[i+2]<90)leakedGreen++;
   }
  }
  return {width:c.width,height:c.height,transparent,visible,leakedGreen};
 });
 assert.deepEqual([originalListHeader.width,originalListHeader.height],[150,38],'original userlist bitmap dimensions');
 assert.ok(originalListHeader.transparent>200&&originalListHeader.visible>200,'userlist is properly keyed but source artwork preserved');
 assert.equal(originalListHeader.leakedGreen,0,'no chroma-key green in visible userlist pixels');

 assert.equal(await host.locator('#leaf-world-stage .world-backdrop').getAttribute('src'),'./original/WorldMap/worldmapback.png');
 assert.equal(await host.locator('#leaf-world-stage .world-sprite').count(),6,'six genuine four-frame region sprites');
 assert.equal(await host.locator('#leaf-world-stage .world-location').count(),6,'six active world regions');
 // Every source location must have a visible resting sprite without requiring hover.
 await host.waitForFunction(()=>[...document.querySelectorAll('#leaf-world-stage .world-sprite')].every(c=>{
   try{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
     for(let i=3;i<d.length;i+=4)if(d[i]>0)return true;
   }catch{}return false;
 }),null,{timeout:12000});
 await host.locator('[data-region="street"]').hover();
 await host.locator('#world-zoom-in').hover();
 assert.ok(await host.evaluate(()=>[...document.querySelectorAll('#leaf-world-stage .world-sprite')].every(c=>{
   const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
   for(let i=3;i<d.length;i+=4)if(d[i])return true;
   return false;
 })),'all original locations remain rendered after pointer leaves');
 await host.screenshot({path:'leaf-original-world.png',fullPage:true});
 await host.locator('[data-region="street"]').click();
 assert.ok(await host.locator('#city:not(.hidden) #street-viewport').isVisible(),'original Keltica MainStreet opens from the real map');
 assert.equal(await host.locator('#street-track .street-artwork').getAttribute('src'),'./original/MainStreet/back.png');
 // The original MainStreet scene was assembled from back.png plus SEVEN
 // original per-business sprites. Pixel compositing must remove their green
 // chroma key, and building buttons must remain interactive.
 await host.waitForFunction(()=>{
  const tiles=[...document.querySelectorAll('.street-building-art')];
  return tiles.length===7&&tiles.every(c=>c.dataset.ready==='true');
 },null,{timeout:16000});
 const streetArtwork=await host.evaluate(()=>[...document.querySelectorAll('.street-building-art')].map(c=>{
  const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let transparent=0,painted=0,greenLeak=0;
  for(let i=0;i<d.length;i+=4){
   if(d[i+3]===0)transparent++;
   else{painted++;if(d[i+1]>205&&d[i]<92&&d[i+2]<100&&d[i+1]>d[i]*1.65&&d[i+1]>d[i+2]*1.55)greenLeak++}
  }
  return {file:c.dataset.source,w:c.width,h:c.height,painted,transparent,greenLeak};
 }));
 assert.deepEqual(streetArtwork.map(x=>x.file),['dress','event','card','hair','accessory','dandymodern','office'],'all seven actual MainStreet source buildings, not proxy illustrations');
 assert.ok(streetArtwork.every(x=>x.painted>200&&x.transparent>100),'every native shop sprite contains artwork and transparent green key');
 assert.ok(streetArtwork.every(x=>x.greenLeak===0),'no unreplaced source bright green regions');
 assert.deepEqual(streetArtwork.map(x=>[x.w,x.h]),[[230,196],[190,229],[183,266],[199,178],[152,136],[212,222],[215,238]],'pixel dimensions agree with extracted PAK manifest');
 // MainStreet source sprites were incorrectly scattered across unrelated
 // buildings. Check absolute source-space position AND real pixel correlation
 // against native back.png (not merely sprite dimensions).
 const streetRegistration=await host.evaluate(()=>{
  const bg=document.querySelector('#street-track .street-artwork');
  const ref=document.createElement('canvas');ref.width=bg.naturalWidth;ref.height=bg.naturalHeight;
  const ctx=ref.getContext('2d',{willReadFrequently:true});ctx.drawImage(bg,0,0);
  const full=ctx.getImageData(0,0,ref.width,ref.height).data;
  return [...document.querySelectorAll('.street-building-art')].map(canvas=>{
   const parent=canvas.closest('.street-location');
   const x=Math.round(parseFloat(parent.style.left)),y=Math.round(parseFloat(parent.style.top));
   const pixels=canvas.getContext('2d',{willReadFrequently:true})
    .getImageData(0,0,canvas.width,canvas.height).data;
   let ab=0,aa=0,bb=0,count=0;
   for(let iy=0;iy<canvas.height;iy+=2)for(let ix=0;ix<canvas.width;ix+=2){
    const a=(iy*canvas.width+ix)*4;
    if(pixels[a+3]<200)continue;
    const b=((iy+y)*ref.width+x+ix)*4;
    for(let k=0;k<3;k++){
     const c=pixels[a+k],d=full[b+k];ab+=c*d;aa+=c*c;bb+=d*d;count++;
    }
   }
   return {asset:canvas.dataset.source,x,y,width:canvas.width,height:canvas.height,
    count,similarity:ab/Math.sqrt(aa*bb)};
  });
 });
 const nativeStreetLocations=[
  {asset:'dress',x:1102,y:135},{asset:'event',x:354,y:39},
  {asset:'card',x:633,y:63},{asset:'hair',x:164,y:128},
  {asset:'accessory',x:1765,y:207},{asset:'dandymodern',x:1315,y:157},
  {asset:'office',x:884,y:7}
 ];
 assert.deepEqual(streetRegistration.map(({asset,x,y})=>({asset,x,y})),nativeStreetLocations,
  'all seven native street sprites must be registered against source backdrop');
 assert.ok(streetRegistration.every(x=>x.similarity>0.965&&x.count>2500),
  'Keltica buildings match their actual native backdrop pixels: '+JSON.stringify(streetRegistration));
 assert.equal(await host.locator('[data-street="court"]').getAttribute('aria-label'),'실키필 · 헤어샵',
  'native left-hand hair salon is Silkyfill, not a fabricated name');
 assert.equal(await host.locator('[data-street="gallery"]').getAttribute('aria-label'),'캐즈팝 · 잡화점',
  'native right-hand accessory shop is KazPop');
 assert.equal(await host.locator('[data-street="magic"]').getAttribute('aria-label'),'매직카덴 · 카드샵','original card shop identification');
 await host.locator('[data-street="magic"]').evaluate(el=>el.click());
 assert.ok(await host.locator('#shop:not(.hidden)').isVisible(),'native MainStreet card building enters working Magic Carden shop');
 // CardShop/cardshopback.png is a 794x404 native screen. Uniform scaling
 // must leave the original card backs visible beneath accessible controls.
 await host.waitForFunction(()=>Number(document.querySelector('#shop-native-stage')?.dataset.scale)>0,null,{timeout:9000});
 const nativeShop=await host.evaluate(()=>{
  const viewport=document.querySelector('#shop .shop-scene'),stage=document.getElementById('shop-native-stage');
  const a=viewport.getBoundingClientRect(),b=stage.getBoundingClientRect();
  const card=document.querySelector('#shop-grid .shop-card');
  return {width:stage.clientWidth,height:stage.clientHeight,
   scaledWidth:b.width,scaledHeight:b.height,
   availableWidth:a.width,availableHeight:a.height,
   background:getComputedStyle(stage).backgroundImage,
   overlay:getComputedStyle(card).backgroundColor,
   cardCount:document.querySelectorAll('#shop-grid .shop-card').length,
   source:stage.dataset.source};
 });
 assert.deepEqual([nativeShop.width,nativeShop.height],[794,404],'source CardShop frame is native 794x404');
 assert.ok(nativeShop.background.includes('original/CardShop/cardshopback.png'),'genuine native CardShop background retained');
 assert.equal(nativeShop.source,'CardShop/cardshopback.png');
 assert.ok(Math.abs(nativeShop.scaledWidth/nativeShop.scaledHeight-794/404)<0.001,
  'Magic Carden background is never non-uniformly stretched');
 assert.ok(nativeShop.scaledWidth<=nativeShop.availableWidth+2&&nativeShop.scaledHeight<=nativeShop.availableHeight+2,
  'native shop bitmap letterboxes rather than cropping off card slots');
 assert.equal(nativeShop.overlay,'rgba(0, 0, 0, 0)','nine overlay buttons no longer repaint native card backs');
 assert.equal(nativeShop.cardCount,9,'all original card positions remain independently interactive');
 await host.locator('#shop-grid .shop-card').nth(1).evaluate(el=>el.click());
 assert.ok((await host.locator('#shop-selected').textContent()).length>0,
  'native card-slot interaction still selects and describes a real item');
 // Native CardShop PAK button atlas is a real 500x510 atlas, not placeholder
 // lettering over the permanent nine 4LEAF card backs.
 const shopSprite=await host.evaluate(()=>{
  const stage=document.getElementById('shop-native-stage');
  const selected=document.querySelector('#shop-grid .shop-card.selected');
  const unselected=[...document.querySelectorAll('#shop-grid .shop-card')].find(el=>el.dataset.owned==='false'&&!el.classList.contains('selected')&&!el.classList.contains('shop-empty'));
  const ownedVisible=[...document.querySelectorAll('#shop-grid .shop-card[data-owned="true"]')];
  const buy=document.getElementById('shop-buy');
  const prev=document.getElementById('shop-prev'),next=document.getElementById('shop-next');
  const info=document.getElementById('shop-selected');
  const toggler=document.getElementById('shop-owned-toggle');
  const css=el=>getComputedStyle(el);
  const rect=el=>{const r=el.getBoundingClientRect(),b=stage.getBoundingClientRect(),scale=Number(stage.dataset.scale);
    return {x:(r.x-b.x)/scale,y:(r.y-b.y)/scale,w:r.width/scale,h:r.height/scale}};
  return {
   selected:css(selected).backgroundImage,selectedRank:selected.dataset.rank,
   selectedArtOpacity:css(selected.querySelector('.card-art')).opacity,
   untouched:css(unselected).backgroundImage,
   ownedVisible:ownedVisible.length,
   ownedNativeFaces:ownedVisible.filter(el=>css(el).backgroundImage.includes('original/CardShop/cardshopbutton.png')).length,
   ownedPortraits:ownedVisible.filter(el=>css(el.querySelector('.card-art')).opacity==='1').length,
   inventoryCount:document.querySelectorAll('#shop-owned-list .shop-owned-entry').length,
   inventoryPortraits:document.querySelectorAll('#shop-owned-list .shop-owned-portrait').length,
   selectedRect:rect(selected),
   buy:css(buy).backgroundImage,buyRect:rect(buy),
   prev:css(prev).backgroundImage,next:css(next).backgroundImage,
   ownedPanelDisplay:css(document.querySelector('#shop .shop-equipped')).display,
   drawerToggle:!!toggler,infoRect:rect(info),
   filterDisplay:css(document.querySelector('#shop .tabline')).backgroundColor
  };
 });
 assert.ok(shopSprite.selected.includes('original/CardShop/cardshopbutton.png'),
  'selected card uses real colored 73x91 source sprite frame');
 assert.equal(shopSprite.untouched,'none','other cards still show untouched background card backs');
 assert.equal(shopSprite.selectedArtOpacity,'1','selected source frame contains actual independent chessman portrait');
 assert.ok(Math.abs(shopSprite.selectedRect.w-73)<0.1&&Math.abs(shopSprite.selectedRect.h-91)<0.1,
  'independent source frame uses native 73x91 pixel dimensions');
 assert.ok(shopSprite.buy.includes('original/CardShop/cardshopbutton.png')
  &&shopSprite.prev.includes('original/CardShop/cardshopbutton.png')
  &&shopSprite.next.includes('original/CardShop/cardshopbutton.png'),
  'purchase and page arrows are recovered source sprite atlas, not Unicode/CSS gradients');
 assert.ok(Math.abs(shopSprite.buyRect.w-98)<0.1&&Math.abs(shopSprite.buyRect.h-21)<0.1,
  'original purchase action uses 98x21 source frame');
 assert.equal(shopSprite.ownedPanelDisplay,'flex','2003 CardShop photograph shows the native right-hand owned-item list open');
 assert.ok(shopSprite.ownedVisible>=2&&shopSprite.ownedNativeFaces===shopSprite.ownedVisible,
  'owned cards expose individual recovered card frames simultaneously, not only the chosen card');
 assert.equal(shopSprite.ownedPortraits,shopSprite.ownedVisible,
  'all owned-card portraits are visible inside original source frames');
 assert.ok(shopSprite.inventoryCount>=2&&shopSprite.inventoryCount===shopSprite.inventoryPortraits,
  'each right-hand item has a real recovered chessman icon; not a fake text-only panel');
 assert.equal(shopSprite.drawerToggle,true,'original 장비 sign has accessible interactive inventory hotspot');
 assert.ok(shopSprite.infoRect.x>=15&&shopSprite.infoRect.x<35
   &&shopSprite.infoRect.y>=320&&shopSprite.infoRect.y<344,
  'selected card details live inside original source 카드정보 box');
 assert.equal(shopSprite.filterDisplay,'rgba(0, 0, 0, 0)',
  'Normal/Valuable signs are the genuine backdrop, not opaque web filter bar');
 const originalAll=await host.locator('#shop .group-tab[data-group="all"]').evaluate(el=>{
  const box=el.getBoundingClientRect(),stage=document.querySelector('#shop-native-stage').getBoundingClientRect(),
    scale=Number(document.querySelector('#shop-native-stage').dataset.scale);
  return {x:(box.x-stage.x)/scale,y:(box.y-stage.y)/scale,
   background:getComputedStyle(el).backgroundColor,
   duplicate:getComputedStyle(el,'::after').content};
 });
 assert.deepEqual([Math.round(originalAll.x),Math.round(originalAll.y)],[14,302],
  'all-card hot area belongs to existing original 카드정보 caption');
 assert.equal(originalAll.duplicate,'none','no invented doubled 전체 label over the source character');
 assert.equal(await host.locator('#shop-owned-toggle').getAttribute('aria-expanded'),'true',
  'the original right-hand owned list is open when entering Magic Carden');
 await host.locator('#shop-owned-toggle').click();
 assert.equal(await host.locator('#shop-owned-toggle').getAttribute('aria-expanded'),'false');
 assert.ok(!(await host.locator('#shop .shop-equipped').isVisible()),
  'original 장비 sign closes only the list, retaining actual shop artwork');
 await host.locator('#shop-owned-toggle').click();
 assert.ok(await host.locator('#shop .shop-equipped').isVisible(),
  'original 장비 sign reopens real owned-card list');
 await host.keyboard.press('Escape');
 assert.equal(await host.locator('#shop-owned-toggle').getAttribute('aria-expanded'),'false');
 assert.ok(!(await host.locator('#shop .shop-equipped').isVisible()),
  'inventory drawer closes on keyboard Escape');
 await host.locator('#shop-owned-toggle').click();
 await host.locator('#shop .group-tab[data-group="valuable"]').click();
 assert.ok(await host.locator('#shop-grid .shop-card[data-rank="valuable"]').count()>0,
  'original Valuable counter filters real catalog without inventing new card data');
 await host.locator('#shop .group-tab[data-group="normal"]').click();
 assert.ok(await host.locator('#shop-grid .shop-card[data-rank="normal"]').count()>0,
  'original Normal counter restores actual normal cards');
 await host.locator('#shop .group-tab[data-group="all"]').click();
 await host.screenshot({path:'leaf-original-cardshop-native.png'});


 await host.evaluate(()=>window.__ROG_TEST__.go('city'));
 assert.ok(await host.locator('#city:not(.hidden)').isVisible(),'shop to MainStreet return route works');

 const sx1=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 await host.locator('#street-right').click();
 const sx2=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 assert.ok(sx2>sx1,'street pans right across 1938px original source artwork');
 await host.locator('#street-left').click();
 await host.waitForTimeout(350);
 console.log('STREET GEOMETRY',JSON.stringify(await host.evaluate(()=>{
   const info=id=>{const el=document.getElementById(id);if(!el)return null;const rect=el.getBoundingClientRect();return {x:Math.round(rect.x),y:Math.round(rect.y),width:Math.round(rect.width),height:Math.round(rect.height),transform:getComputedStyle(el).transform}};
   return {viewport:info('street-viewport'),track:info('street-track'),state:window.__LEAF_STREET__.getState()}
 })));
 await host.screenshot({path:'leaf-original-mainstreet.png'});
 await host.locator('#street-back').click();
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'street returns to WorldMap');

 // Actual 794x404 KnightTown source region MUST precede generic bulletin UI.
 await host.locator('[data-region="knights"]').click();
 await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='knighttown',null,{timeout:5000});
 assert.equal(await host.locator('.knight-district-hotspot').count(),6,'six authentic 0.9 Recordable districts');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage))
   .includes('original/KnightTown/knightback.png'),'source KnightTown backdrop used');
 assert.equal(await host.locator('.recordable-board').count(),0,'no fake bulletin hides native region selection');
 assert.equal(await host.locator('#social-image-frame').evaluate(el=>el.style.height),'404px',
  'original KnightTown scene is exactly 794x404, not the 794x528 ChatRoom canvas');
 await host.screenshot({path:'leaf-original-knighttown-six-regions.png'});
 await host.locator('[data-knight-area="sea01"]').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().knightDistrict),'모험의 바다');
 assert.ok(await host.locator('.recordable-board').isVisible(),'original district opens real working web bulletin');
 await host.locator('#recordable-create').click();
 await host.locator('.recordable-compose [name="title"]').fill('원작 포리프 기사단 게시글');
 await host.locator('.recordable-compose [name="body"]').fill('실제 게시글 보존과 다른 탭 공유 기능 확인');
 await host.locator('.recordable-compose button[type="submit"]').click();
 assert.equal(await host.locator('#recordable-rows .recordable-row').count(),1);
 await guest.locator('[data-region="knights"]').click();
 assert.equal(await guest.locator('.knight-district-hotspot').count(),6);
 await guest.locator('[data-knight-area="sea01"]').click();
 await guest.waitForFunction(()=>document.querySelector('#recordable-rows')?.textContent.includes('원작 포리프 기사단 게시글'),null,{timeout:5000});
 await guest.locator('#recordable-rows .recordable-row').first().click();
 assert.ok((await guest.locator('.recordable-article').textContent()).includes('실제 게시글 보존'));
 await guest.locator('.social-modal-title button').click();
 await host.screenshot({path:'leaf-original-recordable-board.png'});
 await host.locator('#social-back').click();
 await guest.locator('#social-back').click();
 assert.equal(await host.locator('.knight-district-hotspot').count(),6,'back from bulletin returns to native Recordable areas');
 await host.locator('#social-back').click();
 await guest.locator('#social-back').click();
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'back from source KnightTown returns to world');


 // Native geography must never mix the two source subsystems:
 // WorldMap North/South Haiacan open their corresponding ChatTown backdrops;
 // the Genesis World dice island alone opens Region/TOWN SELECT.
 await host.locator('[data-region="north"]').click();
 assert.ok(await host.locator('#rooms:not(.hidden)').isVisible(),'north Haiacan enters chat town, not dice');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'north');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/northback.png'),'north Haiacan uses native ChatTown artwork');

 // ChatTown source art is 794×404; ChatRoom interiors are 794×528.
 // Verify the town uses its own source coordinate system with no fabricated
 // 124px bottom caption or room-only user list stealing horizontal space.
 const nativeTown=await host.evaluate(()=>{
  const scene=document.getElementById('rooms'),frame=document.getElementById('social-image-frame');
  const stage=document.getElementById('social-stage');
  const rect=frame.getBoundingClientRect(),bound=stage.getBoundingClientRect();
  return {className:scene.className,width:parseFloat(getComputedStyle(frame).width),
   height:parseFloat(getComputedStyle(frame).height),display:getComputedStyle(scene.querySelector('.social-user-panel')).display,
   footer:getComputedStyle(frame,'::after').content,
   rectWidth:rect.width,rectHeight:rect.height,stageWidth:bound.width,stageHeight:bound.height};
 });
 assert.ok(nativeTown.className.includes('native-town-scene'),'ChatTown uses its own original layout class');
 assert.deepEqual([nativeTown.width,nativeTown.height],[794,404],'real north ChatTown source is 794×404, not 794×528');
 assert.equal(nativeTown.display,'none','unrelated room-only participant list cannot shrink original ChatTown art');
 assert.ok(nativeTown.footer==='none'||nativeTown.footer==='normal',
  'fabricated caption beneath native town bitmap must be removed');
 assert.ok(Math.abs(nativeTown.rectWidth/nativeTown.rectHeight-794/404)<.002,
  'native ChatTown image must be uniformly scaled');
 assert.ok(nativeTown.rectWidth<=nativeTown.stageWidth+2&&nativeTown.rectHeight<=nativeTown.stageHeight+2,
  'entire source scene fits view without crop');
 assert.equal(await host.locator('.social-district-hotspot').count(),8,'eight original native town signs remain clickable');

 assert.ok(await host.locator('#dice-channels.hidden').count()===1,'dice TOWN SELECT not shown during north chat');
 await host.locator('[data-route="sky"]').first().click();
 await host.locator('[data-region="south"]').click();
 assert.ok(await host.locator('#rooms:not(.hidden)').isVisible(),'south Haiacan enters chat town');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/southback.png'),'south Haiacan uses its distinct original ChatTown art');
 assert.equal(await host.locator('#social-image-frame').evaluate(el=>parseFloat(getComputedStyle(el).height)),404,'south Haiacan uses same native 794×404 coordinate space');
 await host.locator('[data-route="sky"]').first().click();

 await host.locator('[data-region="dice"]').click();
 assert.ok(await host.locator('#dice-channels:not(.hidden)').isVisible(),'Genesis World dice entrance opens native TOWN SELECT');
 assert.ok(await host.locator('#rooms.hidden').count()===1,'dice TOWN SELECT is not a chat room');
 assert.equal(await host.locator('#dice-channels .dice-channel-hotspot').count(),28,'seven native dice character channels with four numbered slots each');
 assert.ok((await host.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('Region/regionback.png'),'only dice channel menu uses Region/regionback.png');
 assert.equal(await host.locator('#dice-channels [data-channel="tichiel:4"]').getAttribute('aria-label'),'주사위의 잔영 · Tichiel 4번 채널');
 await host.screenshot({path:'leaf-original-town-select-dice.png'});
 await host.locator('#dice-channels [data-channel="ispin:1"]').click();
 assert.ok(await host.locator('#lobby:not(.hidden)').isVisible(),'dice channel selects Genesis World room list');
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:1');
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'genesis','dice channel namespace is never north or south chatting town');
 assert.ok((await host.locator('#lobby .scene-banner').textContent()).includes('Ispin 1채널'),'lobby names independent dice channel');
 assert.ok(!(await host.locator('#lobby .scene-banner').textContent()).includes('하이아칸'),'dice channel label must not falsely associate with chat geography');
 await host.locator('#lobby-channel-change').click();
 assert.ok(await host.locator('#dice-channels:not(.hidden)').isVisible(),'room list can reselect its dice channel');
 await host.locator('#dice-channels [data-channel="tichiel:2"]').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'tichiel:2');
 await host.locator('#lobby-channel-change').click();
 await host.locator('#dice-channel-back').click();
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'dice channel BACK returns to world map');
 // ChatTown remains independently reachable directly from the real world map.
 await host.locator('[data-region="north"]').click();
 assert.ok(await host.locator('#rooms:not(.hidden)').isVisible(),'world map north reenters chat town after dice selection');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
 assert.equal(await host.locator('.social-district-hotspot').count(),8,'original north ChatTown eight signs');
 assert.equal(await host.locator('.social-district-hotspot').nth(2).getAttribute('aria-label'),'퓨어 시티 채팅 지역');
 assert.equal(await host.locator('.social-district-hotspot[data-sprite]').count(),8,'all eight source ChatTown buttons have matching original art');
 // Compare actual CSS-composited sprite origins to the original 794x404
 // backing bitmap; cross-correlation of all 16 source patches was >0.96.
 const originalSignAnchors=[[85,63],[265,104],[448,88],[625,69],
                            [48,199],[239,244],[588,203],[417,295]];
 const assertNativeSignPixels=async label=>{
  const positions=await host.locator('.social-district-hotspot').evaluateAll(els=>els.map(el=>{
   const pseudo=getComputedStyle(el,'::after');
   return {
    x:Math.round(parseFloat(el.style.left)+parseFloat(pseudo.left)),
    y:Math.round(parseFloat(el.style.top)+parseFloat(pseudo.top)),
    width:pseudo.width,height:pseudo.height,
    border:getComputedStyle(el).borderTopWidth
   };
  }));
  assert.deepEqual(positions.map(p=>[p.x,p.y]),originalSignAnchors,label+' artwork overlays exactly the recovered native bitmap coordinates');
  assert.ok(positions.every(p=>p.width==='142px'&&p.height==='74px'&&p.border==='0px'),
   label+' sign frames retain native 142x74 proportions and no offsetting interaction border');
 };
 await assertNativeSignPixels('North Haiacan');
 // Quantitative source-asset registration: compare each unselected sprite
 // directly against the original ChatTown background's matching pixels.
 // This detects incorrect labels, rows, scales and offsets independently of CSS.
 const assertNativeArtMatch=async region=>{
  const samples=await host.locator('.social-district-hotspot').evaluateAll(async (els,region)=>{
   const cache=new Map();
   const read=async path=>{
    if(cache.has(path))return cache.get(path);
    const img=new Image();img.src=path;await img.decode();
    const cv=document.createElement('canvas');cv.width=img.naturalWidth;cv.height=img.naturalHeight;
    const cx=cv.getContext('2d',{willReadFrequently:true});cx.drawImage(img,0,0);
    const obj={data:cx.getImageData(0,0,cv.width,cv.height).data,width:cv.width,height:cv.height};
    cache.set(path,obj);return obj;
   };
   const bg=await read('./original/ChatTown/'+region+'back.png');
   const values=[];
   for(const el of els){
    const sprite=await read('./original/ChatTown/'+el.dataset.sprite+'.png');
    const row=Number(el.dataset.spriteRow);
    const top=Math.round(parseFloat(el.style.top)+parseFloat(getComputedStyle(el,'::after').top));
    const left=Math.round(parseFloat(el.style.left)+parseFloat(getComputedStyle(el,'::after').left));
    let n=0,sx=0,sy=0,sxx=0,syy=0,sxy=0;
    for(let y=0;y<74;y+=2)for(let x=0;x<142;x+=2){
     const ia=4*((row*74+y)*sprite.width+x),ib=4*((top+y)*bg.width+left+x);
     for(let c=0;c<3;c++){
      const a=sprite.data[ia+c],b=bg.data[ib+c];n++;sx+=a;sy+=b;sxx+=a*a;syy+=b*b;sxy+=a*b;
     }
    }
    const score=(sxy-sx*sy/n)/Math.sqrt((sxx-sx*sx/n)*(syy-sy*sy/n));
    values.push({name:el.ariaLabel,score:+score.toFixed(4)});
   }
   return values;
  },region);
  assert.ok(samples.every(x=>x.score>0.95),region+' original backdrop aligns with every correct native sign frame: '+JSON.stringify(samples));
 };
 await assertNativeArtMatch('north');
 assert.equal(await host.locator('.social-district-hotspot').nth(2).getAttribute('data-sprite'),'snowbtn','Pure City uses recovered SnowBtn strip');
 await host.locator('.social-district-hotspot').nth(2).hover();
 const pureHover=await host.locator('.social-district-hotspot').nth(2).evaluate(el=>{
  const style=getComputedStyle(el,'::after');
  return {image:style.backgroundImage,pos:style.backgroundPosition,opacity:style.opacity};
 });
 assert.ok(pureHover.image.includes('original/ChatTown/snowbtn.png'),'native source artwork is used for town hover');
 assert.ok(pureHover.pos.includes('-142px')&&pureHover.pos.includes('-148px'),'snow button frame/row are extracted source sprite coordinates');
 assert.equal(pureHover.opacity,'1','original sprite hover state replaces invented yellow glow');
 await host.locator('.social-district-hotspot').nth(2).click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().district),'퓨어 시티');
 await host.locator('#social-back').click();
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('northback.png'));
 await host.screenshot({path:'leaf-original-north-chat-town.png'});
 await host.locator('#social-chat-south').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south','chat region switch stays within the actual chat module');
 assert.equal(await host.locator('.social-district-hotspot').count(),8);
 assert.equal(await host.locator('.social-district-hotspot').nth(0).getAttribute('data-sprite'),'seabtn','south sapphire town uses native SeaBtn art');
 assert.equal(await host.locator('.social-district-hotspot').nth(3).getAttribute('data-sprite'),'plainbtn','south forest town uses native PlainBtn art');
 await assertNativeSignPixels('South Haiacan');
 await assertNativeArtMatch('south');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('southback.png'));
 await host.screenshot({path:'leaf-original-south-chat-town.png'});
 await host.locator('#social-chat-north').click();
 await host.locator('.social-district-hotspot').nth(3).click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory');
 assert.equal(await host.locator('.social-directory-row[data-permanent="true"]').count(),8,
  'eight genuine server-side permanently joinable slots exist in this ChatTown district');
 assert.equal(await host.locator('.social-public-room').count(),0,
  'real server-backed permanent rooms are ordinary functional room buttons, not fake static props');
 assert.ok((await host.locator('.social-directory-row[data-permanent="true"] .social-room-users').allTextContents())
  .every(text=>text==='0/12명'),'unoccupied permanent rooms must never show pretend human users');
 const directoryShot=await host.locator('#social-image-frame').screenshot({type:'jpeg',quality:65,
  animations:'disabled',timeout:16000});
 console.log('SOURCE_PERMANENT_ROOM_DIRECTORY_JPEG_BASE64 '+directoryShot.toString('base64'));
 const emptyTerrain=await host.locator('#social-map-plane').evaluate(el=>({
  type:el.dataset.terrain,image:getComputedStyle(el).backgroundImage
 }));
 assert.equal(emptyTerrain.type,'unverified','exact historical ChatTown room-map terrain is unknown');
 assert.equal(emptyTerrain.image,'none','do not paint unrelated Dice bgtile on ChatTown');
 const nativeDirectory=await host.evaluate(()=>{
  const bg=document.getElementById('social-image-frame');
  const p=bg.querySelector('.social-directory'),b=p.getBoundingClientRect();
  const actual=bg.getBoundingClientRect();
  const roomButtons=[...bg.querySelectorAll('.social-directory-row')];
  return {background:getComputedStyle(bg).backgroundImage,
   projectedMap:!!p.classList.contains('web-estate-open'),
   list:roomButtons.map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.width,r.height]}),
   panel:[b.x,b.y,b.width,b.height],frame:[actual.width,actual.height],
   visibleSourceRatio:1-(b.width*b.height)/(actual.width*actual.height)};
 });
 assert.ok(nativeDirectory.background.includes('original/ChatTown/northback.png'),
  'permanent-room selector must expose recovered native ChatTown landscape');
 assert.equal(nativeDirectory.projectedMap,false,
  'unknown historical estate coordinates must NOT replace the source art by default');
 assert.ok(nativeDirectory.panel[2]<=350&&nativeDirectory.panel[3]<=330&&
  nativeDirectory.visibleSourceRatio>.7,
  'original town background must occupy most of its native frame');
 assert.ok(nativeDirectory.list.every(r=>r[2]>180&&r[3]>=34),
  'eight actual room links are readable full-width instead of tiny scattered gray cards');
 assert.equal(await host.locator('#social-web-estate-toggle').getAttribute('aria-pressed'),'false');
 await host.locator('#social-web-estate-toggle').click();
 assert.equal(await host.locator('#social-web-estate-toggle').getAttribute('aria-pressed'),'true',
  'inferred web-map is an accessible opt-in, never mistaken for original geography');
 const mapBefore=await host.locator('#social-map-plane').evaluate(el=>el.style.transform);
 await host.locator('#social-map-viewport').focus();
 await host.keyboard.press('ArrowRight');
 const horizontalPan=await host.locator('#social-map-plane').evaluate(el=>el.style.transform);
 assert.notEqual(horizontalPan,mapBefore,'direction keys pan the estate horizontally');
 await host.keyboard.press('ArrowDown');
 const mapAfter=await host.locator('#social-map-plane').evaluate(el=>el.style.transform);
 assert.notEqual(mapAfter,horizontalPan,'direction keys pan the estate vertically');
 const actualRoomId=await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('실제 개설 채팅방',2,12));
 assert.ok(actualRoomId,'room created by a genuine participant');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'room');
 assert.equal(await host.locator('.social-avatar').count(),1,'room contains only actual participants');
 assert.equal(await host.locator('#social-image-frame').evaluate(el=>parseFloat(getComputedStyle(el).height)),528,
  'entering an original ChatRoom restores its independent 794×528 scene');
 // Actual recovered player screenshots chat_ref.jpg and chat.jpg place BOTH
 // components INSIDE 794x528 ChatRoom art: real edit/log at upper-left,
 // live occupancy roster upper-right (not adjacent columns shrinking art).
 const overlay=await host.evaluate(()=>{
  const frame=document.getElementById('social-image-frame');
  const img=frame.getBoundingClientRect(),scale=img.width/794;
  const place=id=>{
   const b=document.querySelector(id).getBoundingClientRect();
   return {x:(b.x-img.x)/scale,y:(b.y-img.y)/scale,w:b.width/scale,h:b.height/scale};
  };
  return {state:window.__LEAF_NATIVE_ROOM_PANELS__?.getState(),
   message:place('.messenger'),roster:place('#social-peer-panel'),
   input:place('#chat-form'),sourceImage:getComputedStyle(frame).backgroundImage,
   peers:document.querySelectorAll('#social-peer-list .social-user-row').length};
 });
 assert.equal(overlay.state?.overlay,true,'actual messenger and list are mounted inside original ChatRoom pixels');
 assert.equal(overlay.state?.messengerParent,'social-image-frame','real conversation log is a child of the source scene');
 assert.equal(overlay.state?.rosterParent,'social-image-frame','genuine online participants overlay source art');
 assert.deepEqual([overlay.state?.messageFormCount,overlay.state?.rosterCount],[1,1],'no dummy chat or fake roster layers');
 assert.ok(Math.abs(overlay.message.x-16)<1.5&&Math.abs(overlay.message.y)<1.5,'archival screen: chat at upper-left scene coordinate');
 assert.ok(Math.abs(overlay.roster.x-(794-13-158))<1.5&&Math.abs(overlay.roster.y-9)<1.5,'archival screen: native participant list at upper-right scene coordinate');
 assert.ok(Math.abs(overlay.input.w-407)<1.5&&overlay.input.y>80,'native source edit frame remains independent from visible scrollable chat lines');
 assert.equal(overlay.peers,1,'only genuine self user appears in overlay, never sample NPCs');

 await host.waitForFunction(()=>{const img=document.querySelector('#social-avatar-layer .social-avatar.self img');return img?.complete&&img.naturalWidth===75&&img.naturalHeight===141},{timeout:12000});
 const nativeAvatarFeet=await host.evaluate(()=>{
  const frame=document.getElementById('social-image-frame');
  const figure=document.querySelector('#social-avatar-layer .social-avatar.self');
  const sprite=figure.querySelector('img');
  const room=frame.getBoundingClientRect(),paint=sprite.getBoundingClientRect();
  const seatBaseline=room.top+Number.parseFloat(figure.style.top)*room.height/100;
  return {native:[sprite.naturalWidth,sprite.naturalHeight],
   imageBottom:paint.bottom,seatBaseline,
   movement:getComputedStyle(figure).transitionDuration};
 });
 assert.deepEqual(nativeAvatarFeet.native,[75,141],'use the exact recovered 75×141 Registry character frame');
 assert.ok(Math.abs(nativeAvatarFeet.imageBottom-nativeAvatarFeet.seatBaseline)<2.5,
  'native avatar feet must snap to the target seat without the previous 19px offset');
 assert.ok(nativeAvatarFeet.movement.split(',').every(v=>parseFloat(v)===0),
  'room seats teleport instantly without a linear walk tween');

 assert.equal(await host.locator('#social-native-user-count').textContent(),'1명','the original userlist title field reflects actual room occupants');
 assert.ok(overlay.sourceImage.includes('/original/ChatRoom/room'),'still uses native source room bitmap');
 await host.screenshot({path:'leaf-original-overlay-chatroom-desktop.png'});
 // The archived ChatRoom/exitbtn.png lower strip is four original 66×25
 // EXIT states. The existing real room-back action is the hit target.
 await host.waitForFunction(()=>document.querySelector('#rooms.classic-chat-room #social-back')
  ?.dataset.nativeExitReady==='true',null,{timeout:12000});
 const sourceExit=await host.evaluate(async()=>{
  const button=document.getElementById('social-back');
  const imageUrl=button.style.backgroundImage.slice(5,-2);
  const img=new Image();img.src=imageUrl;await img.decode();
  const computed=getComputedStyle(button);
  return {source:[img.naturalWidth,img.naturalHeight],
   width:parseFloat(computed.width),height:parseFloat(computed.height),
   frame:button.dataset.nativeFrame,cssImage:computed.backgroundImage.startsWith('url("data:image/png;base64,')};
 });
 assert.deepEqual(sourceExit.source,[66,25],'native ChatRoom EXIT button is a 66×25 source frame');
 assert.deepEqual([sourceExit.width,sourceExit.height],[66,25],'room back button uses native 66×25 hitbox');
 assert.equal(sourceExit.frame,'0','initial ChatRoom EXIT uses first bitmap state');
 assert.ok(sourceExit.cssImage,'EXIT decoration is a real chroma-keyed source frame');
 await host.locator('#social-back').hover();
 assert.equal(await host.locator('#social-back').getAttribute('data-native-frame'),'1',
  'ChatRoom EXIT hover changes to original second state');

 assert.notEqual(await host.locator('#rooms .social-user-panel').evaluate(el=>getComputedStyle(el).display),'none',
  'native user list belongs to ChatRoom interior, not the town selector');

 // The archived ChatRoom text-entry atlas contains the nickname field, long
 // input field and send bubble in a single exact 407×21 source bitmap.
 // The real form must remain keyboard and pointer accessible.
 const nativeEntry=await host.evaluate(async()=>{
  const form=document.getElementById('chat-form');
  const image=new Image();image.src='./original/ChatRoom/chatbaredit.png';
  await image.decode();
  const source=document.createElement('canvas');source.width=image.naturalWidth;source.height=image.naturalHeight;
  const canvas=source.getContext('2d',{willReadFrequently:true});canvas.drawImage(image,0,0);
  const alpha=canvas.getImageData(0,0,1,1).data[3];
  return {w:form.getBoundingClientRect().width,h:form.getBoundingClientRect().height,
   bg:getComputedStyle(form).backgroundImage,
   name:getComputedStyle(document.getElementById('nick')).backgroundColor,
   edit:getComputedStyle(document.getElementById('message')).backgroundColor,
   send:document.querySelector('#chat-form button').getAttribute('aria-label'),
   original:[image.naturalWidth,image.naturalHeight],cornerAlpha:alpha,
   roomScale:document.querySelector('#social-image-frame').getBoundingClientRect().width/794};
 });
 assert.deepEqual(nativeEntry.original,[407,21],'native ChatRoom input art has original source size');
 assert.equal(nativeEntry.cornerAlpha,0,'native source input is transparent at corner; no invented opaque frame');
 assert.ok(Math.abs(nativeEntry.w/nativeEntry.roomScale-407)<2&&Math.abs(nativeEntry.h/nativeEntry.roomScale-21)<1,
  'working chat edit control retains 407×21 original bitmap geometry inside the scaled ChatRoom art');
 assert.ok(nativeEntry.bg.includes('original/ChatRoom/chatbaredit.png'),
  'native sprite supplies actual nickname/input/send frames');
 assert.equal(nativeEntry.name,'rgba(0, 0, 0, 0)','native nickname frame remains visible');
 assert.equal(nativeEntry.edit,'rgba(0, 0, 0, 0)','native text frame remains visible');
 assert.equal(nativeEntry.send,'채팅 메시지 보내기','native source speech-bubble send hitbox is accessible');
 assert.equal(await host.locator('#social-close-room').count(),1,'room creator may close their own room');
 const exitHit=await host.evaluate(()=>{
  const frame=document.getElementById('social-image-frame');
  const exit=document.getElementById('social-back');
  const panel=document.getElementById('social-peer-panel');
  const hit=(el)=>{const b=el.getBoundingClientRect(),c=getComputedStyle(el);
   return {x:b.x,y:b.y,w:b.width,h:b.height,z:c.zIndex,position:c.position,
    parent:el.parentElement?.id,overflow:c.overflow,display:c.display}};
  const b=exit.getBoundingClientRect();
  const node=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);
  return {frame:hit(frame),exit:hit(exit),roster:hit(panel),list:hit(document.getElementById('social-peer-list')),
   clickedNode:node?.outerHTML.slice(0,210),closestExit:!!node?.closest('#social-back')};
 });
 console.log('ORIGINAL_ROOM_EXIT_POINTER_GEOMETRY '+JSON.stringify(exitHit));
 const screenshot=await host.locator('#social-image-frame').screenshot({type:'jpeg',quality:70,timeout:12000});
 console.log('ORIGINAL_ROOM_SOURCE_LIVE_JPEG_BASE64 '+screenshot.toString('base64'));
 await host.locator('#social-back').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_NATIVE_ROOM_PANELS__?.getState().messengerParent),'main','leaving source room returns exact same real chat input to main');
 assert.equal(await host.locator('#social-peer-panel').evaluate(el=>el.parentElement.classList.contains('social-layout')),true,'the single real roster returns to its ordinary town layout');
 assert.equal(await host.locator('.social-public-room').count(),0,'no fabricated preset rooms after leaving');
 assert.equal(await host.locator('.social-directory-row').count(),9,'eight permanent server rooms plus the actual user-created room persist');
 const realMarker=await host.locator('.social-directory-row[data-permanent="false"]').first().evaluate(el=>({
  x:Number.parseFloat(el.style.left),y:Number.parseFloat(el.style.top),count:el.querySelector('.social-room-users').textContent
 }));
 assert.ok(realMarker.x>=70&&realMarker.x<=1380&&realMarker.y>=70&&realMarker.y<=1050,
  'actual room has a distinct spatial position (not claimed as original)');
 assert.equal(realMarker.count,'0/12명','leaving a real room clears its occupancy');
 assert.equal(await host.locator('#social-map-plane').evaluate(el=>el.style.transform),mapAfter,'the original room terrain camera resumes its prior position after returning from a room');
 await host.locator('#social-new-room').click();
 assert.equal(await host.locator('#social-modal [name="background"] option').count(),6,'six source ChatRoom backgrounds remain selectable');
 // Recovered ChatRoom/ownerdialog uses a visible source-native Cancel
 // button; the generic HTML title's X is intentionally hidden here.
 await host.locator('#social-modal .social-owner-native-cancel').click();
 await host.screenshot({path:'leaf-original-room-directory.png'});
 const roomId=await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원작 채팅 테스트',3));
 assert.ok(roomId.length>=10,'new real room id');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('room3.png'));
 assert.equal(await host.locator('.social-avatar').count(),1,'zero fabricated NPC users');
 const faceBefore=await host.locator('.social-avatar.self img').evaluate(el=>el.style.transform);
 const glow=await host.locator('.social-avatar.self').evaluate(el=>({figure:getComputedStyle(el).filter,portrait:getComputedStyle(el.querySelector('img')).filter}));
 assert.equal(glow.figure,'none','character has no artificial silhouette shadow');
 assert.equal(glow.portrait,'none','character has no self-selection glow');
 await host.locator('.social-avatar.self').click();
 assert.equal(await host.locator('#social-modal').count(),0,'clicking character turns it rather than opening avatar changer');
 const faceAfter=await host.locator('.social-avatar.self img').evaluate(el=>el.style.transform);
 assert.notEqual(faceAfter,faceBefore,'clicking avatar flips its horizontal direction');
 await host.locator('.social-avatar.self').click();
 assert.equal(await host.locator('.social-avatar.self img').evaluate(el=>el.style.transform),faceBefore,'second click restores original facing');
 assert.equal(await host.locator('.social-original-tool').count(),6,'six working source-art toolbar actions');
 assert.equal(await host.locator('#social-close-room').count(),1,'owner can close room from the window chrome');
 assert.equal(await host.locator('.social-interior-controls').count(),0,'no artificial blue control buttons cover original scene');
 await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
 assert.ok(await host.locator('.social-avatar-chooser').isVisible(),'authentic toolbar avatar icon opens working character picker');
 await host.locator('.social-modal-title button').click();
 // The native client shipped a MainFrame toolbar icon sprite sheet.
 // Do not substitute generic emoji controls: the icon crop and functional
 // actions must be present in the real room.
 assert.equal(await host.locator('.social-classic-toolbar .social-original-tool').count(),6,'recovered native ChatRoom toolbar controls are visible');
 assert.equal(await host.locator('.social-original-tool').first().evaluate(e=>getComputedStyle(e).backgroundImage.includes('original/MainFrame/toolbarbtn.png')),true,'original 120x270 sprite sheet is used');
 assert.equal(await host.locator('.social-original-tool[aria-label="월드맵으로 돌아가기"]').evaluate(e=>getComputedStyle(e).backgroundPositionY),'-240px','the correct original exit sprite row is used');
 assert.ok(await host.locator('.social-classic-toolbar').isVisible(),'toolbar has a visible second header row');
 await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
 assert.ok(await host.locator('#social-modal .social-avatar-chooser').isVisible(),'original avatar button opens the chooser');
 await host.locator('#social-modal .social-modal-title button').click();

 // Original ChatRoom.pak contains an independent red-key foreground table
 // for room3; it must sit between the rear and front avatar seats.
 await host.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',null,{timeout:16000});
 const depth=await host.evaluate(()=>{
  const c=document.querySelector('.social-room-foreground');
  const p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let visible=0,redLeak=0,transparent=0;
  for(let i=0;i<p.length;i+=4){
   if(p[i+3]>0){visible++;if(p[i]>242&&p[i+1]<18&&p[i+2]<18)redLeak++}else transparent++;
  }
  const me=document.querySelector('.social-avatar.self');
  return {source:c.dataset.source,visible,redLeak,transparent,avatarZ:Number(me.style.zIndex),foregroundZ:Number(c.style.zIndex),room:document.querySelector('#social-image-frame').style.backgroundImage};
 });
 assert.equal(depth.source,'room3t','room3 original furniture sprite was loaded');
 assert.ok(depth.visible>500,'table pixels are painted');
 assert.ok(depth.transparent>500,'original bitmap red chroma key is transparent');
 assert.equal(depth.redLeak,0,'no red chroma-key fringe remains');
 assert.ok(depth.room.includes('room3.png'),'native room backdrop and independent furniture are composited');
 assert.equal(await host.locator('#social-image-frame .social-room-title').count(),0,'no invented room title banner over native art');
 const avatarAlpha=await host.evaluate(async()=>{
  const img=document.querySelector('.social-avatar.self img');
  await img.decode();const c=document.createElement('canvas');
  c.width=img.naturalWidth;c.height=img.naturalHeight;
  const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
  const d=ctx.getImageData(0,0,c.width,c.height).data;
  return {cornerAlpha:d[3],corner:[d[0],d[1],d[2]],width:c.width,height:c.height};
 });
 console.log('ORIGINAL REGISTRY AVATAR ALPHA',JSON.stringify(avatarAlpha));
 assert.equal(avatarAlpha.width,75,'original Registry sprites use 75px source width');
 assert.equal(avatarAlpha.height,141,'original Registry sprites use 141px source height');
 assert.equal(avatarAlpha.cornerAlpha,0,'avatar background is transparent, not chroma-green');
 assert.equal(await host.locator('.social-avatar.self img').evaluate(el=>getComputedStyle(el).width),'75px','rendered avatar retains native 75px frame width');
 // Adjacent source 75×141 character sprites may overlap. A huge proxy button
 // and another user's nametag must not steal clicks from the visible torso.
 const torsoTarget=await host.locator('.social-avatar.self').evaluate(button=>{
  const name=button.querySelector('.social-avatar-name'),image=button.querySelector('img');
  return {width:parseFloat(getComputedStyle(button).width),
   height:parseFloat(getComputedStyle(button).height),
   picture:[parseFloat(getComputedStyle(image).width),parseFloat(getComputedStyle(image).height)],
   namePointer:getComputedStyle(name).pointerEvents,
   imagePointer:getComputedStyle(image).pointerEvents};
 });
 assert.deepEqual([torsoTarget.width,torsoTarget.height],[58,94],
  'hit target hugs native character torso without covering the next 75×141 avatar');
 assert.deepEqual(torsoTarget.picture,[75,141],'original Registry sprite size stays unchanged');
 assert.equal(torsoTarget.namePointer,'none','neighboring nametags never intercept another avatar click');
 assert.equal(torsoTarget.imagePointer,'none','image paint itself delegates clicks to avatar button body');

 const stage=host.locator('.social-interior');
 const frontBack=async(x,y)=>{
  await stage.evaluate((el,coords)=>{
   const box=el.getBoundingClientRect();
   el.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:box.left+box.width*coords.x/100,clientY:box.top+box.height*coords.y/100}));
  },{x,y});
  return await host.locator('.social-avatar.self').evaluate(el=>({seat:Number(el.dataset.seat),z:Number(el.style.zIndex),transition:getComputedStyle(el).transitionDuration}));
 };
 const behind=await frontBack(38,72);
 assert.ok(behind.z<depth.foregroundZ,'rear chair is hidden behind original tabletop');
 assert.equal(behind.transition,'0s','rear-seat change has no walking animation');
 const inFront=await frontBack(24,94);
 assert.ok(inFront.z>depth.foregroundZ,'front chair is drawn in front of original tabletop');
 assert.notEqual(inFront.seat,behind.seat,'front and rear clicks choose different native scene anchors');

 await host.screenshot({path:'leaf-original-chat-room.png'});

 await guest.evaluate(()=>{
  window.__LEAF_SOCIAL__.openRegion('north');
  window.__ROG_TEST__.go('rooms');
 });
 assert.equal(await guest.locator('.social-district-hotspot').count(),8,'second browser chat access does not require a dice channel');
 await guest.locator('.social-district-hotspot').nth(3).click();
 await guest.waitForFunction(id=>document.querySelector('.social-directory-row[data-room="'+id+'"]'),roomId,{timeout:6500});
 await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),roomId);
 await Promise.all([
  host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000}),
  guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000})
 ]);
 assert.equal(await host.locator('#social-online-count').textContent(),'2명');
 assert.ok(await host.locator('#social-original-userlist').isVisible(),'original participant list header remains visible during real chat');
 assert.equal(await guest.locator('#social-online-count').textContent(),'2명');
 assert.equal(await host.locator('#social-native-user-count').textContent(),'2명','source participant badge follows true host/guest peers');
 assert.equal(await guest.locator('#social-native-user-count').textContent(),'2명','remote 2-user roster count updates without fabricated members');

 // The exact recovered 104x330 ChatRoom/ringbtn.png has four 26px-wide
 // interaction states and fifteen 22px icon rows. Historical chat_ref.jpg
 // shows a short vertical action strip beside a selected actor. Use ONLY
 // the actual other browser's avatar, never fabricated profile fixtures.
 const selectedPeer=host.locator('#social-avatar-layer .social-avatar:not(.self)');
 assert.equal(await selectedPeer.count(),1,'a real second tab provides the native character menu subject');
 await selectedPeer.evaluate(el=>el.click());
 assert.equal(await host.locator('#social-actor-menu .social-native-ring-action').count(),4,
  'selected real participant opens genuine original 4-control ringbtn strip');
 const ringSource=await host.evaluate(async()=>{
  const original=new Image();original.src='./original/ChatRoom/ringbtn.png';await original.decode();
  const menu=document.getElementById('social-actor-menu');
  const frame=document.getElementById('social-image-frame');
  const buttons=[...menu.querySelectorAll('button')];
  return {
   source:[original.naturalWidth,original.naturalHeight],
   peer:menu.dataset.peer,
   menu:menu.getBoundingClientRect().toJSON(),
   frame:frame.getBoundingClientRect().toJSON(),
   actions:buttons.map(el=>{
    const css=getComputedStyle(el);
    return {image:css.backgroundImage,
     pos:css.backgroundPosition,
     dimensions:[parseFloat(css.width),parseFloat(css.height)],
     row:el.dataset.ringRow,accessible:el.getAttribute('aria-label')};
   })
  };
 });
 assert.deepEqual(ringSource.source,[104,330],'native original ChatRoom actor atlas is exactly 104x330');
 assert.deepEqual(ringSource.actions.map(x=>x.row),['4','5','7','8'],'source graphic rows for the original screenshot-style action column');
 assert.ok(ringSource.actions.every(x=>x.dimensions[0]===26&&x.dimensions[1]===22),
  'all menu buttons are native 26x22 independently clickable hitboxes');
 assert.ok(ringSource.actions.every(x=>x.image.includes('original/ChatRoom/ringbtn.png')),
  'no invented emoji: every action directly uses original archived ring icon art');
 assert.ok(ringSource.menu.x>=ringSource.frame.x-2&&ringSource.menu.right<=ringSource.frame.right+2,
  'source action strip is positioned inside original scaled 794x528 room image');
 await host.screenshot({path:'leaf-source-ringbtn-live-peer-menu.png'});
 await host.keyboard.press('Escape');
 assert.equal(await host.locator('#social-actor-menu').count(),0,'Escape dismisses native player menu without moving actor');
 assert.equal(await host.locator('#social-avatar-layer .social-avatar:not(.self)').evaluate(el=>document.activeElement===el),true,
  'native menu restores keyboard focus to real selected participant');

 await selectedPeer.evaluate(el=>el.click());
 await host.locator('#social-actor-menu [aria-label="캐릭터 정보 보기"]').click();
 assert.ok(await host.locator('#social-modal').isVisible(),'original icon opens the existing live peer information, not a fabricated member');
 await host.locator('.social-modal-title button').click();
 assert.equal(await host.locator('#social-actor-menu').count(),0,'information action closes original sprite menu');
 await selectedPeer.evaluate(el=>el.click());
 await host.locator('#social-actor-menu [aria-label="채팅 입력에 닉네임 넣기"]').click();
 assert.ok((await host.locator('#message').inputValue()).startsWith('@'),
  'source icon inserts actual peer name into real chat input without sending a fake message');
 await host.locator('#message').fill('');

 const originSeat=await host.locator('.social-avatar.self').evaluate(el=>el.dataset.seat);
 await selectedPeer.evaluate(el=>el.click());
 await host.locator('#social-actor-menu [aria-label="이 캐릭터 근처 빈 자리로 이동"]').click();
 assert.equal(await host.locator('#social-actor-menu').count(),0,'choosing native near-seat action closes menu');
 const movedSeat=await host.locator('.social-avatar.self').evaluate(el=>({
  seat:el.dataset.seat,transition:getComputedStyle(el).transitionDuration,
  left:el.style.left,top:el.style.top
 }));
 assert.equal(movedSeat.transition,'0s','selected peer approach instantly snaps to discrete ChatRoom seat');
 assert.ok(Number.isInteger(Number(movedSeat.seat)),'peer approach uses actual archived room-layout seat IDs');
 assert.ok((await host.locator('.social-avatar').count())===2,'no fabricated participant was created by peer commands');
 await guest.waitForFunction(p=>[...document.querySelectorAll('.social-avatar:not(.self)')]
   .some(el=>el.style.left===p.left&&el.style.top===p.top),movedSeat,{timeout:7500});
 await selectedPeer.evaluate(el=>el.click());
 await host.locator('#social-actor-menu [aria-label="캐릭터 메뉴 닫기"]').click();
 assert.equal(await host.locator('#social-actor-menu').count(),0,'red original X glyph closes only the context strip');

 await host.locator('#message').fill('원본 하이아칸 실시간 채팅 테스트');
 await host.locator('#message').press('Enter');
 await guest.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('원본 하이아칸 실시간 채팅 테스트'),null,{timeout:7000});
 assert.ok(await guest.locator('.social-speech').count()>=1,'real speech bubble above sender avatar');
 // Historical 47x100 sprite: real ChatRoom balloon is assembled from
 // nine separately cropped corners/sides/center plus an independent 12x15
 // downward tail. The DOM contains real transmitted text, never a bitmap
 // of a fabricated canned chat message.
 await guest.waitForFunction(()=>{
  const balloon=document.querySelector('.social-speech');
  return window.__LEAF_NATIVE_TALKBOX__?.getState().ready
   &&balloon?.dataset.nativeTalkboxReady==='true';
 },null,{timeout:9000});
 const nativeTalk=await guest.locator('.social-speech').first().evaluate(el=>{
  const c=el.querySelector('canvas.native-talkbox-canvas');
  const ctx=c.getContext('2d');
  const ratio=c.width/parseFloat(c.style.width);
  const sample=(x,y)=>[...ctx.getImageData(Math.floor(x*ratio),Math.floor(y*ratio),1,1).data];
  return {source:el.dataset.nativeSource,text:el.textContent,
   dataSource:c.dataset.source,renderWidth:parseFloat(c.style.width),
   renderHeight:parseFloat(c.style.height),
   clientW:el.offsetWidth,clientH:el.offsetHeight,
   corner:sample(0,0),
   fill:sample(el.offsetWidth/2,Math.min(12,el.offsetHeight/2)),
   tail:sample(el.offsetWidth/2,el.offsetHeight+3),
   oldPseudo:getComputedStyle(el,'::after').display,
   atlas:window.__LEAF_NATIVE_TALKBOX__?.getState()};
 });
 assert.deepEqual([nativeTalk.atlas.width,nativeTalk.atlas.height],[47,100],
  'recover actual 47x100 ChatRoom/talkbox.png, not CSS border art');
 assert.equal(nativeTalk.source,'ChatRoom/talkbox.png');
 assert.equal(nativeTalk.dataSource,'ChatRoom/talkbox.png');
 assert.ok(nativeTalk.text.includes('원본 하이아칸 실시간 채팅 테스트'),
  'source-generated balloon contains genuine remote message');
 assert.equal(nativeTalk.corner[3],0,
  'red chroma-key source pixels become transparent corners');
 assert.ok(nativeTalk.fill[3]>0&&nativeTalk.fill[0]>150,
  'real source white speech panel center is drawn inside nine-slice');
 assert.ok(nativeTalk.renderHeight>=nativeTalk.clientH+14,
  'original tail is drawn below nine-slice body');
 assert.equal(nativeTalk.oldPseudo,'none','invented CSS speech triangle is removed');
 await guest.screenshot({path:'leaf-original-native-47x100-speech.png'});

 await guest.locator('#message').fill('두 번째 브라우저의 실제 응답');
 await guest.locator('#message').press('Enter');
 await host.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('두 번째 브라우저의 실제 응답'),null,{timeout:7000});
 // Original 2001 era chat toys use the regular, real participant channel.
 await host.evaluate(()=>{
  const old=Math.random;Math.random=()=>0.73;
  try{window.__LEAF_SOCIAL__.send('/주사위')}finally{Math.random=old}
 });
 await guest.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('⚄ 주사위 5'),null,{timeout:7000});
 assert.ok(await host.locator('.social-speech').allTextContents().then(xs=>xs.some(x=>x.includes('⚄ 주사위 5'))),'original dice command produces a speech bubble');
 for(const [command,output] of [['/묵','✊ 묵'],['/찌','✌ 찌'],['/빠','✋ 빠']]){
  await guest.locator('#message').fill(command);
  await guest.locator('#message').press('Enter');
  await host.waitForFunction(result=>document.querySelector('#chat-log')?.textContent.includes(result),output,{timeout:7000});
 }
 assert.ok((await guest.locator('#chat-log').textContent()).includes('✋ 빠'),'period rock/paper/scissors chat is transmitted without fabricated win/loss');


 // Clicking a standing area must snap instantly to a discrete slot, without walking interpolation.
 const before=await guest.locator('.social-avatar.self').evaluate(el=>({left:el.style.left,top:el.style.top}));
 // A legitimate random spawn can ALREADY occupy the previously hard-coded
 // target. Try distinct actual standing areas to avoid false failures.
 let immediate;
 for(const [x,y] of [[78,68],[20,93],[58,79]]){
  immediate=await guest.locator('.social-interior').evaluate((frame,point)=>{
   const rect=frame.getBoundingClientRect();
   frame.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+rect.width*point.x/100,clientY:rect.top+rect.height*point.y/100}));
   const el=frame.querySelector('.social-avatar.self');
   return {left:el.style.left,top:el.style.top,transition:getComputedStyle(el).transitionDuration,seat:el.dataset.seat};
  },{x,y});
  if(immediate.left!==before.left||immediate.top!==before.top)break;
 }
 assert.notDeepEqual({left:immediate.left,top:immediate.top},before,'click changes the occupied slot without requiring a different random spawn');
 assert.equal(immediate.transition,'0s','local avatar teleports without CSS interpolation');
 assert.ok(Number.isInteger(Number(immediate.seat)),'avatar is assigned a discrete seat');
 await host.waitForFunction(pos=>[...document.querySelectorAll('.social-avatar')].some(el=>el.style.left===pos.left&&el.style.top===pos.top),{left:immediate.left,top:immediate.top},{timeout:7000});
 assert.equal(await host.locator('.social-avatar').first().evaluate(el=>getComputedStyle(el).transitionDuration),'0s','remote avatar also teleports without interpolation');
 await host.screenshot({path:'leaf-two-live-chat-users.png'});
 // Each recovered roomXt foreground is selected by the actual room's
 // background style, not by a fabricated public-room number.
 await host.locator('#social-back').click();
 for(const [background,source] of [[5,'room5t'],[4,'room4t']]){
  await host.evaluate(bg=>window.__LEAF_SOCIAL__.createRoom('원본 배경 '+bg+' 테스트',bg),background);
  await host.waitForFunction(expected=>document.querySelector('.social-room-foreground')?.dataset.source===expected&&document.querySelector('.social-room-foreground')?.dataset.ready==='true',source,{timeout:16000});
  assert.equal(await host.locator('.social-room-foreground').count(),1,'one genuine foreground per room');
  await host.screenshot({path:'leaf-original-'+source+'.png'});
  await host.locator('#social-back').click();
 }
 await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원본 서재 배경 검증',2));
 assert.equal(await host.locator('.social-room-foreground').count(),0,'room2 has no fabricated overlay sprite');

 // Native archive has six distinct room bitmaps. In particular room0 must
 // not silently become room2 when the browser converts the string "0".
 await host.locator('#social-back').click();
 await host.locator('#social-new-room').click();
 await host.locator('#social-modal [name="name"]').fill('숲속 광장 2인 채팅');
 await host.locator('#social-modal [name="background"]').selectOption('0');
 await host.locator('#social-modal [name="capacity"]').selectOption('2');
 await host.locator('#social-modal button[type="submit"]').click();
 const limitedRoom=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
 assert.ok(limitedRoom,'two-person room created through real UI');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId)?.background),0,'original room0 selected without Number(0) fallback error');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId)?.capacity),2,'special two-person room carries a persisted capacity');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('room0.png'));
 assert.equal(await host.locator('.social-room-foreground').count(),0,'original room0 has no invented foreground table');
 await guest.locator('#social-back').click();
 await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),limitedRoom,{timeout:8000});
 await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),limitedRoom);
 await host.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='2명',null,{timeout:8000});
 // Third actual tab must observe 2/2 in the directory and be refused.
 const third=await a.newPage();
 third.on('pageerror',e=>errors.push('third: '+e.stack));
 await third.goto(url);
 await third.waitForFunction(()=>!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000});
 await third.evaluate(()=>{
  window.__LEAF_SOCIAL__.openRegion('north');
  window.__ROG_TEST__.go('rooms');
 });
 await third.locator('.social-district-hotspot').nth(3).click();
 await third.waitForFunction(id=>{
   const row=[...document.querySelectorAll('.social-directory-row')].find(x=>x.dataset.room===id);
   return row?.querySelector('.social-room-users')?.textContent==='2/2명';
 },limitedRoom,{timeout:8000});
 assert.ok(await third.locator('.social-directory-row.social-room-full').count()>0,'full room is marked in the directory');
 await third.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),limitedRoom);
 assert.ok(await third.locator('#social-modal').isVisible(),'third participant is shown a full-room warning');
 assert.equal(await third.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory','third participant cannot enter a two-person room');
 await third.locator('.social-modal-title button').click();
 await third.close();
 await host.screenshot({path:'leaf-original-room0-two-person.png'});
 // Leaving a room for the shop must vacate it; returning restores presence.
 await host.locator('#social-image-frame .social-original-tool[aria-label="매직카덴"]').click();
 await guest.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='1명',null,{timeout:8000});
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().scope),'away:shop','shop visitors no longer count as chat occupants');
 await host.locator('[data-route="rooms"]').first().click();
 await guest.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='2명',null,{timeout:8000});
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId),limitedRoom,'return from shop preserves the current chat room');
 // Both tabs use the same visible Guest nickname: the guest must not acquire
 // the host's room-owner privileges from this coincidental display-name match.
 assert.equal(await guest.locator('#social-close-room').count(),0,'same nickname cannot impersonate room owner');
 assert.equal(await host.locator('#social-close-room').count(),1,'true room owner retains controls');
 const owned=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId));
 assert.ok(owned.ownerId&&owned.capacity===2,'owner identity and participant limit travel with the room');
 await host.locator('#social-close-room').click();
 await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().view==='directory'&&!window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),limitedRoom,{timeout:8000});
 assert.equal(await guest.locator('.social-directory-row[data-room="'+limitedRoom+'"]').count(),0,'closed room disappears from other browser');


 await guest.setViewportSize({width:390,height:844});
 // The archived ChatRoom has a real participant list. A small screen may
 // temporarily overlap it but must never silently remove the list entirely.
 await guest.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('모바일 참가자 목록 검증',2));
 assert.equal(await guest.locator('#rooms.classic-chat-room').count(),1,'actual ChatRoom on mobile');
 assert.equal(await guest.evaluate(()=>window.__LEAF_NATIVE_ROOM_PANELS__?.getState().overlay),false,'small screens use full-size usable input, never tiny scaled 407px text');
 assert.equal(await guest.evaluate(()=>window.__LEAF_NATIVE_ROOM_PANELS__?.getState().messengerParent),'main','mobile chat form remains outside transformed room art');
 assert.equal(await guest.locator('#social-peers-toggle').isVisible(),true,'mobile original roster is accessible');
 assert.equal(await guest.locator('#social-peers-toggle').getAttribute('aria-expanded'),'false');
 assert.equal(await guest.locator('#social-peer-panel').isVisible(),false,'mobile roster starts collapsed');
 assert.equal(await guest.locator('.social-avatar.self').evaluate(el=>getComputedStyle(el).transitionDuration),'0s','mobile avatar teleports without interpolation');
 await guest.locator('.social-avatar.self').evaluate(el=>
  el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true})));
 assert.equal(await guest.locator('#social-actor-menu button').count(),4,
  'mobile right-click/long-touch equivalent exposes source ringbtn menu');
 await guest.locator('#social-actor-menu button').last().click();
 assert.equal(await guest.locator('#social-actor-menu').count(),0,'mobile original X closes character actions');

 await guest.locator('#social-peers-toggle').click();
 assert.equal(await guest.locator('#social-peers-toggle').getAttribute('aria-expanded'),'true');
 assert.equal(await guest.locator('#social-peer-panel').isVisible(),true,'roster opens in the original room');
 assert.equal(await guest.locator('#social-peer-list .social-user-row').count(),1,'only the real participant is listed');
 assert.equal(await guest.locator('#social-native-user-count').textContent(),'1명','original participant count stays factual on mobile');
 await guest.waitForFunction(()=>document.querySelector('#social-original-userlist')?.dataset.ready==='true',null,{timeout:10000});
 assert.deepEqual(await guest.locator('#social-original-userlist').evaluate(el=>[el.width,el.height]),[150,38],'original ChatRoom userlist remains 150×38');
 await guest.screenshot({path:'leaf-native-mobile-roster-open.png'});
 await guest.locator('#social-peers-toggle').focus();
 await guest.keyboard.press('Escape');
 assert.equal(await guest.locator('#social-peers-toggle').getAttribute('aria-expanded'),'false','Escape closes the roster');
 assert.equal(await guest.locator('#social-peer-panel').isVisible(),false,'the source room is fully exposed again');
 await guest.locator('#social-peers-toggle').click();
 const mobileExit=await guest.evaluate(()=>{
  const exit=document.getElementById('social-back'),button=exit.getBoundingClientRect();
  const panel=document.getElementById('social-peer-panel').getBoundingClientRect();
  const node=document.elementFromPoint(button.x+button.width/2,button.y+button.height/2);
  return {exit:[button.x,button.y,button.width,button.height],
   roster:[panel.x,panel.y,panel.width,panel.height],
   hit:node?.tagName,top:node?.id,canClick:!!node?.closest('#social-back')};
 });
 console.log('MOBILE_NATIVE_CHAT_EXIT_HIT '+JSON.stringify(mobileExit));
 assert.ok(mobileExit.canClick,'source EXIT must never be covered by optional mobile participant roster');
 await guest.locator('#social-back').click();
 assert.equal(await guest.locator('#social-peers-toggle').isVisible(),false,'ChatTown never inherits ChatRoom roster controls');
 assert.equal(await guest.locator('#rooms.social-peers-open').count(),0,'room exit resets the mobile roster');
 await guest.screenshot({path:'leaf-chat-mobile.png'});
 assert.ok(await guest.locator('#message').isVisible(),'mobile chat input');
 assert.ok(await guest.locator('#social-back').isVisible(),'mobile navigation');
 assert.deepEqual(errors,[],'no JS exceptions');
 assert.deepEqual(missingAssets,[],'all requested original art assets load without 404');
 await browser.close();
 console.log('4LEAF WORLD + CHAT PASS: original map, north/south boards, 6 interiors, real room creation, two users, cross-tab messages and speech bubbles, mobile');
})().catch(e=>{console.error('WORLD+CHAT E2E FAILED',e.stack||e);process.exit(1)});