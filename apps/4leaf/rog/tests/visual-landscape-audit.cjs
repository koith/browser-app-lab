'use strict';
/* One-off public UI visual evidence in CI, before changing CSS again.
   Encodes 932x320 real render screenshots as JPEG to the job log so
   a reviewer can inspect actual screenshots and not trust geometry only.
   No runtime code or live project state is modified by this test. */
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
(async()=>{
 const b=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const opts={...devices['iPhone 13 landscape'],viewport:{width:932,height:320},screen:{width:932,height:430}};
  if(engine!=='webkit')delete opts.defaultBrowserType;
  const ctx=await b.newContext({...opts,serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  const shot=async name=>{
   await page.waitForTimeout(850);
   const meta=await page.evaluate(()=>{
    let keys=['#app','#main','#sky','.leaf-world-viewport','.leaf-world-stage',
      '#dice-channels','#dice-channel-viewport','#dice-channel-stage','#lobby',
      '#dice-lobby-scene','#dice-native-stage','#rooms','.social-image-frame'];
    let o={fit:window.__LEAF_PHONE_FIT__?.getState?.()||null,meta:document.querySelector('meta[name="viewport"]').content,rects:{}};
    for(const k of keys){
     const el=document.querySelector(k);
     if(!el||getComputedStyle(el).display==='none'||!el.getClientRects().length)continue;
     const r=el.getBoundingClientRect();
     o.rects[k]=[r.x,r.y,r.width,r.height].map(v=>+v.toFixed(1));
    }
    o.images=[...document.querySelectorAll('img')].filter(e=>{
     const r=e.getBoundingClientRect();return r.width>30&&r.height>30&&r.x<innerWidth&&r.y<innerHeight&&r.right>0&&r.bottom>0;
    }).slice(0,12).map(i=>({src:i.src.split('/').slice(-2).join('/'),natural:[i.naturalWidth,i.naturalHeight],
     alt:i.alt,box:[i.getBoundingClientRect().width,i.getBoundingClientRect().height].map(Math.round)}));
    return o;
   });
   const jpeg=await page.screenshot({type:'jpeg',quality:55,animations:'disabled'});
   console.log('4LEAF_META_'+name+'='+JSON.stringify(meta));
   console.log('4LEAF_JPEG_'+name+'='+jpeg.toString('base64'));
  };
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_PHONE_FIT__?.getState?.()?.kind==='world-528');
  await shot('WORLD');
  await page.locator('button[data-route="lobby"]').first().click();
  await page.waitForFunction(()=>!document.getElementById('lobby').classList.contains('hidden'));
  await shot('LOBBY');
  await page.locator('#lobby-channel-change').click();
  await page.waitForFunction(()=>!document.getElementById('dice-channels').classList.contains('hidden'));
  await shot('CHANNELS');
  await page.goto(base);
  await page.getByRole('button',{name:/북 하이아칸/}).first().click();
  await page.waitForFunction(()=>!document.getElementById('rooms').classList.contains('hidden'));
  await shot('CHATTOWN');
  await ctx.close();
 }finally{await b.close()}
})().catch(e=>{console.error('VISUAL AUDIT FAILED',e.stack||e);process.exit(1)});
