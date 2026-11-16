'use strict';
/* Click-through user flow: WorldMap -> district -> 4x2 room map -> room chat
 * -> exit. Runs on desktop and both iPhone orientations (Chromium or WebKit).
 * Room geometry is asserted before trying to click anything. */
const assert=require('node:assert/strict');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const VIEWS=[['desktop',{viewport:{width:1280,height:850}}],
 ['iphone-portrait','iPhone 13'],['iphone-landscape','iPhone 13 landscape']];
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  for(const [name,spec] of VIEWS){
   const opts=typeof spec==='string'?{...devices[spec]}:spec;
   if(engine!=='webkit')delete opts.defaultBrowserType;
   const ctx=await browser.newContext({...opts,serviceWorkers:'block'});
   const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   if(name==='iphone-portrait'){
    await page.goto(base);
    await page.locator('#leaf-phone-rotate').waitFor({state:'visible'});
    assert.equal(await page.locator('html').getAttribute('data-leaf-phone-fit'),'portrait');
    console.log(name,'orientation guidance shown; real-use click path is landscape-only');
    await ctx.close();continue;
   }
   await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
   await page.goto(base);
   await page.getByRole('button',{name:/북 하이아칸/}).first().click();
   await page.locator('.social-district-hotspot').first().waitFor({state:'visible',timeout:10000});
   await page.locator('.social-district-hotspot').nth(2).click();
   await page.locator('.social-map-rooms>button').first().waitFor({state:'visible',timeout:10000});
   await page.waitForTimeout(300);
   const map=await page.evaluate(()=>{
    const vp=document.getElementById('social-map-viewport').getBoundingClientRect();
    const cards=[...document.querySelectorAll('.social-map-rooms>button')].map(b=>{
     const r=b.getBoundingClientRect();
     const inside=r.left>=vp.left-1&&r.right<=vp.right+1&&r.top>=vp.top-1&&r.bottom<=vp.bottom+1;
     const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
     const labels=[...b.querySelectorAll('.social-room-number,b,.social-room-users')].every(l=>{
      const q=l.getBoundingClientRect();return q.left>=r.left-1&&q.right<=r.right+1&&q.top>=r.top-1&&q.bottom<=r.bottom+1});
     return {l:r.left,t:r.top,r:r.right,b:r.bottom,inside,
      hit:inside&&(t===b||b.contains(t)),labels,bg:getComputedStyle(b).backgroundColor};
    });
    let overlaps=0;
    for(let i=0;i<cards.length;i++)for(let j=i+1;j<cards.length;j++){
     const a=cards[i],b=cards[j];
     if(Math.min(a.r,b.r)-Math.max(a.l,b.l)>1&&Math.min(a.b,b.b)-Math.max(a.t,b.t)>1)overlaps++;
    }
    return {count:cards.length,overlaps,inside:cards.filter(c=>c.inside).length,
     hittable:cards.filter(c=>c.hit).length,labelsInside:cards.every(c=>c.labels),
     opaque:cards.every(c=>!/rgba\(0, 0, 0, 0\)|transparent/.test(c.bg)),
     partlyCut:cards.filter(c=>!c.inside&&c.r>vp.left&&c.l<vp.right&&c.b>vp.top&&c.t<vp.bottom).length};
   });
   assert.ok(map.count>=4,name+' rooms listed on map '+JSON.stringify(map));
   assert.equal(map.overlaps,0,name+' cards overlap '+JSON.stringify(map));
   assert.ok(map.labelsInside&&map.opaque,name+' room labels/visibility');
   if(name==='desktop'){assert.equal(map.inside,map.count);assert.equal(map.partlyCut,0)}
   else assert.ok(map.hittable>=2,name+' tappable rooms in first view');
   await page.locator('.social-map-rooms>button').first().click();
   await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='room',null,{timeout:10000});
   await page.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===1,null,{timeout:10000});
   const message='지도 입장 점검 '+name;
   await page.locator('#message').fill(message);await page.locator('#message').press('Enter');
   await page.waitForFunction(t=>document.getElementById('chat-log').textContent.includes(t),message,{timeout:5000});
   const back=page.locator('#social-back');await back.scrollIntoViewIfNeeded();await back.click();
   await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='directory',null,{timeout:8000});
   await page.locator('.social-map-rooms>button').first().waitFor({state:'visible',timeout:8000});
   assert.deepEqual(errors,[]);
   console.log(name,JSON.stringify(map));
   await ctx.close();
  }
  console.log('REALUSE CHAT MAP PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('REALUSE CHAT MAP FAILED',e.stack||e);process.exit(1)});
