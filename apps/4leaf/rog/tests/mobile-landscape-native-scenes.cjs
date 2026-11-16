'use strict';
/* Regression from 2026-11-17 user Safari screenshots:
 * [1] WorldMap was a tiny floating 800x600 box.
 * [2] Region TOWN SELECT was split: caption LEFT, native art RIGHT.
 * [3] Native 794x404 ROOM SELECT had invented navy top/bottom stripes.
 * Run on real app with Playwright Chromium/WebKit and phone landscape size.
 */
const assert=require('node:assert/strict');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(
  engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const phone={...devices['iPhone 13 landscape'],viewport:{width:932,height:320},screen:{width:932,height:430}};
  if(engine!=='webkit')delete phone.defaultBrowserType;
  const ctx=await browser.newContext({...phone,serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(base);
  const measure=()=>page.evaluate(()=>{
   const box=id=>{
    const el=document.querySelector(id);if(!el)return null;
    const r=el.getBoundingClientRect();
    return {x:r.x,y:r.y,w:r.width,h:r.height,r:r.right,b:r.bottom,
      display:getComputedStyle(el).display,
      flexDirection:getComputedStyle(el).flexDirection};
   };
   return {fit:window.__LEAF_PHONE_FIT__?.getState?.()||null,
    app:box('#app'),world:box('#sky'),region:box('#dice-channels'),
    regionView:box('#dice-channel-viewport'),regionArt:box('#dice-channel-stage'),
    lobby:box('#lobby'),lobbyView:box('#dice-lobby-scene'),
    lobbyArt:box('#dice-native-stage'),
    width:innerWidth,height:innerHeight};
  });
  const viewIs=kind=>page.waitForFunction(kind=>
   window.__LEAF_PHONE_FIT__?.getState?.()?.kind===kind,kind,{timeout:10000});
  const whole=(r,within,label)=>{
   assert.ok(r&&within,label+' element missing');
   assert.ok(r.x>=within.x-3&&r.r<=within.r+3&&
    r.y>=within.y-3&&r.b<=within.b+3,label+
    ' frame cropped: '+JSON.stringify({r,within}));
  };
  const frame=(m,kind)=>{
   assert.equal(m.fit.kind,kind,'correct scene dimensions: '+JSON.stringify(m.fit));
   assert.equal(m.fit.method,'per-scene-native-contain');
   assert.ok(m.app.w>=m.width*.94,'MainFrame fills available landscape width');
   whole(m.app,{x:0,y:0,r:m.width,b:m.height},'outer MainFrame');
  };
  await viewIs('world-528');
  const world=await measure();
  frame(world,'world-528');
  await page.locator('button[data-route="lobby"]').first().click();
  await viewIs('genesis-404');
  const lobby=await measure();
  frame(lobby,'genesis-404');
  assert.equal(lobby.lobby.flexDirection,'column','ROOM SELECT children vertical');
  assert.ok(lobby.lobbyView.h>=lobby.app.h*.8,
   'ROOM SELECT fills source height instead of top/bottom navy bars');
  whole(lobby.lobbyArt,lobby.lobbyView,'native ROOM SELECT');
  await page.locator('#lobby-channel-change').click();
  await page.waitForFunction(()=>!document.getElementById('dice-channels').classList.contains('hidden'));
  await viewIs('genesis-404');
  const region=await measure();
  frame(region,'genesis-404');
  assert.equal(region.region.flexDirection,'column','TOWN SELECT must not become side-by-side flex ROW');
  assert.ok(region.regionView.h>=region.app.h*.8,'TOWN SELECT art fills content height');
  whole(region.regionArt,region.regionView,'original TOWN SELECT');
  const cx=r=>r.x+r.w/2;
  assert.ok(Math.abs(cx(region.regionArt)-cx(region.regionView))<4,
   'TOWN SELECT art must be centered, not pushed right');
  await page.locator('#dice-channel-stage .dice-channel-hotspot').first().click();
  await page.waitForFunction(()=>!document.getElementById('lobby').classList.contains('hidden'));
  await viewIs('genesis-404');
  frame(await measure(),'genesis-404');
  console.log('PASS',engine,JSON.stringify({world:world.fit,lobby:lobby.fit,region:region.fit,
    sourceRegionW:region.regionArt.w,fullScreenW:region.app.w}));
  await ctx.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('LANDSCAPE SCENE REGRESSION',e.stack||e);process.exit(1)});
