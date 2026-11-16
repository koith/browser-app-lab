'use strict';
/* Validate landscape/portrait viewport, overlays and desktop non-regression
 * on the real application, not a mocked local shell. */
const assert=require('node:assert/strict');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const cases=[
   ['desktop',{viewport:{width:1280,height:850}},null],
   ['iphone-landscape',{...devices['iPhone 13 landscape']},'landscape'],
   ['iphone-portrait',{...devices['iPhone 13']},'portrait']
  ];
  for(const [name,opts,expected] of cases){
   if(engine!=='webkit')delete opts.defaultBrowserType;
   const ctx=await browser.newContext({...opts,serviceWorkers:'block'});
   const page=await ctx.newPage(), errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(base);
   const state=await page.evaluate(()=>{
    const root=document.documentElement;
    const f=window.__LEAF_PHONE_FIT__?.getState?.()??null;
    return {attr:root.getAttribute('data-leaf-phone-fit'),fit:f,
     width:innerWidth,height:innerHeight,
     chat:getComputedStyle(document.getElementById('leaf-phone-chat-toggle')).display,
     rotate:getComputedStyle(document.getElementById('leaf-phone-rotate')).display};
   });
   assert.equal(state.attr,expected,name+' mode');
   if(expected==='landscape'){
    assert.ok(state.fit&&state.fit.landscape&&state.height>=600,
     name+' desktop design viewport on phone '+JSON.stringify(state));
    assert.notEqual(state.chat,'none','phone chat overlay toggle exists');
    await page.locator('#leaf-phone-chat-toggle').click();
    assert.equal(await page.locator('html').getAttribute('data-leaf-chat-open'),'true');
    await page.locator('#leaf-phone-chat-toggle').click();
    assert.equal(await page.locator('html').getAttribute('data-leaf-chat-open'),'false');
    assert.equal(state.rotate,'none','rotation prompt must be hidden in landscape');
   }else if(expected==='portrait'){
    assert.ok(state.fit&&!state.fit.landscape&&state.width>=800,'portrait design viewport');
    assert.notEqual(state.rotate,'none','portrait rotation prompt visible');
    assert.equal(state.chat,'none','no landscape chat toggle in portrait');
   }else{
    assert.equal(state.fit,null,'desktop viewport must remain native');
    assert.equal(state.chat,'none');
    assert.equal(state.rotate,'none');
   }
   assert.deepEqual(errors,[],name+' unhandled errors');
   console.log(name,JSON.stringify(state));
   await ctx.close();
  }
  console.log('PHONE FRAME SMOKE PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('PHONE FRAME SMOKE FAILED',e.stack||e);process.exit(1)});
