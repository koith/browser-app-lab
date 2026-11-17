'use strict';
/* Real 4LEAF mobile fit regression: no viewport rewriting, scene clipping,
 * or zoom on device rotation, plus unchanged desktop behavior. */
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
   const page=await ctx.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(base);
   const get=()=>page.evaluate(()=>{
    const html=document.documentElement;
    const f=window.__LEAF_PHONE_FIT__?.getState?.()??null;
    const a=document.getElementById('app').getBoundingClientRect();
    const vv=window.visualViewport;
    return {
     mode:html.getAttribute('data-leaf-phone-fit'),
     fit:f,width:innerWidth,height:innerHeight,
     visualWidth:vv?.width||innerWidth,visualHeight:vv?.height||innerHeight,
     viewportMeta:document.querySelector('meta[name="viewport"]').content,
     app:{x:a.x,y:a.y,width:a.width,height:a.height,right:a.right,bottom:a.bottom},
     chatDetached:!!document.getElementById('leaf-phone-chat-toggle'),
     rotate:getComputedStyle(document.getElementById('leaf-phone-rotate')).display
    };
   });
   const verify=(s,mode)=>{
    assert.equal(s.mode,mode,name+' orientation mode');
    assert.match(s.viewportMeta,/width=device-width/,name+' no synthetic meta zoom');
    if(!mode){
     assert.equal(s.fit,null,'desktop unaffected');
     assert.equal(s.chatDetached,false,'do not add invented global chat control');
     assert.equal(s.rotate,'none');
     return;
    }
    assert.ok(s.fit&&s.fit.layoutWidth>=800&&s.fit.layoutHeight>=440&&s.fit.layoutHeight<=600,
      name+' source-preserving per-scene layout kept');
    assert.equal(s.fit.method,'per-scene-native-contain');
    assert.ok(s.fit.scale>0&&s.fit.scale<=1.5,
      name+' source image scales only to available height, never cropped');
    assert.ok(s.app.x>=-2&&s.app.right<=s.width+2&&
      s.app.y>=-2&&s.app.bottom<=s.height+2,
      name+' entire frame within actual device '+JSON.stringify(s));
    assert.ok(Math.abs(s.app.width-s.fit.layoutWidth*s.fit.scale)<2&&
      Math.abs(s.app.height-s.fit.layoutHeight*s.fit.scale)<2,
      name+' uniform aspect ratio '+JSON.stringify(s));
    assert.equal(s.fit.landscape,mode==='landscape');
    if(mode==='portrait')assert.notEqual(s.rotate,'none');
    else assert.equal(s.rotate,'none');
   };
   const s=await get();
   verify(s,expected);
   if(expected==='landscape'){
    assert.equal(s.chatDetached,false,'original MainFrame toolbar must not be hidden by an invented global chat toggle');
    // WebKit device emulation keeps its original orientation even after a
    // viewport-size mutation; independent portrait/landscape contexts above
    // test both real configurations. Do not claim live WebKit rotation tested.
    if(engine!=='webkit'){
    // Rotate the SAME live page, then rotate back without reload.
    await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>document.documentElement.getAttribute('data-leaf-phone-fit')==='portrait');
    verify(await get(),'portrait');
    await page.setViewportSize({width:844,height:390});
    await page.waitForFunction(()=>document.documentElement.getAttribute('data-leaf-phone-fit')==='landscape');
    const after=await get();
    verify(after,'landscape');
    assert.ok(after.fit.scale<=Math.min((after.visualWidth-3)/800,(after.visualHeight-3)/after.fit.layoutHeight)+.0001,
      name+' returning to landscape must never overfill its current visible viewport '+JSON.stringify({before:s.fit,after:after.fit}));
    }else{
     console.log('webkit orientation: separate phone contexts validated; live device rotation requires hardware QA');
    }
   }
   const unrelatedErrors=errors.filter(e=>!(/fourleaf-central-chat-free\.onrender\.com\/api\/session/.test(e)&&/Fetch API cannot load/.test(e)));
   assert.deepEqual(unrelatedErrors,[],name+' viewport-induced JavaScript errors');
   console.log(name,JSON.stringify({mode:s.mode,scale:s.fit?.scale,device:[s.width,s.height],app:s.app}));
   await ctx.close();
  }
  console.log('PHONE FIT ROTATION PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('PHONE FIT ROTATION FAILED',e.stack||e);process.exit(1)});
