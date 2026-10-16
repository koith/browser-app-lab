'use strict';
// VERIFIABLE: MainFrame.pak toolbarbtn.png 120x270 = 4 frames × 9 rows of 30px.
// Existing routes remain real HTML events. Their exact historical icon-to-
// route mappings are not proven from the old executable, and are documented
// as a web restoration, never claimed to be recovered handlers.
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.waitForFunction(()=>document.querySelector('#leaf-world-stage .world-backdrop')?.dataset.ready==='true',null,{timeout:18000});
  const originals=await page.evaluate(async()=>{
   const src=async file=>{
    const image=new Image();image.src='./original/MainFrame/'+file+'.png';
    await image.decode();
    return [image.naturalWidth,image.naturalHeight];
   };
   return {
    toolbar:await src('toolbarbtn'),panel:await src('pannel'),title:await src('title')
   };
  });
  assert.deepEqual(originals.toolbar,[120,270],'genuine 4 states × 9 rows sprite');
  assert.deepEqual(originals.panel,[323,124],'genuine MainFrame tile panel source');
  assert.deepEqual(originals.title,[680,54],'genuine unchanged native 4LEAF wordmark');

  const native=await page.evaluate(()=>{
   const bar=document.querySelector('#app > nav.toolbar');
   const frame=getComputedStyle(bar),title=getComputedStyle(document.querySelector('#app>.titlebar'));
   return {barHeight:bar.getBoundingClientRect().height,art:frame.backgroundImage,
    title:title.backgroundImage,
    buttons:[...bar.querySelectorAll(':scope > button')].map(button=>{
     const st=getComputedStyle(button),r=button.getBoundingClientRect();
     return {id:button.id||button.dataset.route,source:st.backgroundImage,
      backgroundSize:st.backgroundSize,position:st.backgroundPosition,
      size:[r.width,r.height],row:button.dataset.nativeIconRow,
      label:button.getAttribute('aria-label'),innerText:button.textContent,
      actualFontSize:st.fontSize,tag:button.tagName};
    }),
    originalWorld:document.querySelectorAll('#leaf-world-stage canvas.world-sprite').length
   };
  });
  assert.ok(native.art.includes('/original/MainFrame/pannel.png'),'original pannel tiles the real navigation backdrop');
  assert.ok(native.title.includes('/original/MainFrame/title.png'),'existing genuine wordmark remains intact');
  assert.equal(native.barHeight,36,'reduce fake 49px emoji bar to source-native 30px cells + 6px chrome');
  assert.equal(native.buttons.length,8,'all existing live route/utility controls preserved');
  assert.deepEqual(native.buttons.map(x=>x.id),['sky','city','rooms','shop','lobby','rename','audio','help']);
  assert.deepEqual(native.buttons.map(x=>Number(x.row)),[0,2,3,4,1,6,5,7]);
  assert.ok(native.buttons.every(x=>x.source.includes('/original/MainFrame/toolbarbtn.png')),
   'every navigation/utility button paints independent real MainFrame source sprite');
  assert.ok(native.buttons.every(x=>x.backgroundSize==='120px 270px'),
   'sprite sheet retains exact native source pixel scale');
  assert.ok(native.buttons.every(x=>x.size[0]===30&&x.size[1]===30),
   'all eight real clickable original button frames are exactly 30x30');
  assert.ok(native.buttons.every(x=>x.actualFontSize==='0px'&&x.label),
   'old emoji icons are never repainted over the source atlas, live buttons remain accessible');
  assert.equal(native.originalWorld,6,'original interactive WorldMap region canvases are preserved');
  await page.screenshot({path:'leaf-original-mainframe-toolbar-world.png'});

  // Confirm real CSS atlas frames change on hover and active route instead of
  // a fabricated gradient/turquoise halo or a cloned screenshot.
  await page.locator('#app > nav.toolbar [data-route="city"]').hover();
  const hover=await page.locator('#app > nav.toolbar [data-route="city"]').evaluate(b=>({
   x:getComputedStyle(b).backgroundPositionX,
   y:getComputedStyle(b).backgroundPositionY,
   glow:getComputedStyle(b).boxShadow
  }));
  assert.equal(hover.x,'-30px','hover selects the original second frame');
  assert.equal(hover.y,'-60px','Keltica live nav uses independently extracted third row');
  assert.equal(hover.glow,'none','invented highlighted navbar box-shadow is removed');
  await page.locator('#app > nav.toolbar [data-route="city"]').click();
  assert.ok(await page.locator('#city:not(.hidden) #street-viewport').isVisible(),
   'source atlas icon still opens seven-source Keltica walking street');
  await page.locator('#app > nav.toolbar [data-route="shop"]').click();
  assert.ok(await page.locator('#shop:not(.hidden)').isVisible(),
   'source atlas shop icon opens real Magic Carden');
  await page.locator('#app > nav.toolbar [data-route="sky"]').click();
  await page.locator('.world-location[data-region="north"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
  assert.equal(await page.locator('#social-image-frame').evaluate(el=>parseInt(getComputedStyle(el).height,10)),404);
  await page.locator('#app > nav.toolbar [data-route="rooms"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'live ChatTown route preserved');
  await page.locator('#app > nav.toolbar [data-route="lobby"]').click();
  assert.ok(await page.locator('#lobby:not(.hidden),#dice-channels:not(.hidden)').count()>0,
   'Genesis Dice navigation remains distinct from north/south ChatTown');
  await page.locator('#app > nav.toolbar #help').click();
  assert.ok(await page.locator('#help-screen:not(.hidden)').isVisible(),'source question mark icon opens genuine help');
  await page.locator('#app > nav.toolbar #rename').click();
  assert.ok(await page.locator('#modal:not(.hidden) #modal-content input').isVisible(),
   'source chrome does not break live account nickname editor');
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  await page.locator('#app > nav.toolbar [data-route="sky"]').click();

  await page.setViewportSize({width:390,height:844});
  const phone=await page.evaluate(()=>{
   const bar=document.querySelector('#app>nav.toolbar'),rect=bar.getBoundingClientRect();
   const buttons=[...bar.querySelectorAll(':scope > button')];
   const last=buttons.at(-1).getBoundingClientRect();
   return {barHeight:rect.height,viewportWidth:document.documentElement.clientWidth,
    rightmost:last.right,buttons:buttons.map(b=>b.getBoundingClientRect().width),
    labels:buttons.map(b=>b.getAttribute('aria-label')),
    location:getComputedStyle(document.getElementById('where')).display,
    toolbarArt:getComputedStyle(bar).backgroundImage};
  });
  assert.equal(phone.barHeight,34,'touch client source toolbar remains compact');
  assert.ok(phone.rightmost<=phone.viewportWidth+1,
   'every live source icon, including question-mark help, remains within phone viewport');
  assert.ok(phone.buttons.every(n=>Math.abs(n-30)<.02),'phone never stretches extracted original pixels: '+JSON.stringify(phone));
  assert.equal(phone.location,'none','responsive original toolbar does not crop icons for invented text banner');
  await page.locator('#app > nav.toolbar [data-route="shop"]').click();
  assert.ok(await page.locator('#shop:not(.hidden)').isVisible(),'source atlas icons remain touch-sized and usable');
  await page.screenshot({path:'leaf-original-mainframe-toolbar-mobile.png'});
  assert.deepEqual(errors,[],'original toolbar restoration emits no browser exceptions');
  console.log('MAINFRAME NATIVE TOOLBAR PASS',JSON.stringify({originals,native,hover,phone}));
 }finally{await browser.close()}
})().catch(e=>{console.error('MAINFRAME NATIVE TOOLBAR FAILED:',e.stack||e);process.exit(1)});
