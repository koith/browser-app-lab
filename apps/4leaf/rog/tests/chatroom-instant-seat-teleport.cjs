'use strict';
/* Native ChatRoom seat clicks must teleport immediately in a real browser.
 * This tests live hit targets, not a synthetic click or a fake 2002 user.
 * Historical exact seat map and pixel equivalence remain independently open. */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,
  ...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:15000});
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원본 좌석 즉시 이동 검증',4,12);
  });
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden) .social-avatar.self');
  // Choose a genuine pointer-reachable background pixel away from UI/art actors.
  const target=await page.evaluate(()=>{
   const frame=document.getElementById('social-image-frame'),actor=frame?.querySelector('.social-avatar.self');
   if(!frame||!actor)return null;
   const f=frame.getBoundingClientRect(),a=actor.getBoundingClientRect();
   for(const [px,py] of [[.13,.92],[.27,.88],[.12,.73],[.78,.91],[.8,.74],[.32,.8]]){
    const x=f.left+px*f.width,y=f.top+py*f.height,under=document.elementFromPoint(x,y);
    if(!under||!frame.contains(under)||
       under.closest('button,a,input,form,.social-classic-toolbar,#social-actor-menu'))continue;
    if(Math.hypot(x-(a.left+a.width/2),y-(a.top+a.height/2))<110)continue;
    return {x,y};
   }
   return null;
  });
  assert.ok(target,'source room background must have a physically reachable target');
  const before=await page.evaluate(()=>document.querySelector('.social-avatar.self')?.dataset.seat);
  await page.mouse.click(target.x,target.y);
  const capture=()=>page.evaluate(()=>{
   const actor=document.querySelector('#rooms.classic-chat-room .social-avatar.self');
   const css=getComputedStyle(actor),b=actor.getBoundingClientRect();
   return {seat:actor.dataset.seat,left:actor.style.left,top:actor.style.top,
    x:b.x,y:b.y,transition:css.transitionDuration,animation:css.animationDuration};
  });
  const immediately=await capture();
  assert.notEqual(immediately.seat,before,'real background click must select a different slot');
  assert.ok(immediately.transition.split(',').every(x=>Number.parseFloat(x)===0),
   'source ChatRoom actors must not interpolate');
  assert.ok(immediately.animation.split(',').every(x=>Number.parseFloat(x)===0),
   'source ChatRoom actors must not animate when changing seats');
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const frame2=await capture();
  await page.waitForTimeout(260);
  const settled=await capture();
  for(const snapshot of [frame2,settled]){
   assert.equal(snapshot.seat,immediately.seat,'slot cannot change later');
   assert.equal(snapshot.left,immediately.left,'no delayed horizontal tween');
   assert.equal(snapshot.top,immediately.top,'no delayed vertical tween');
   assert.ok(Math.abs(snapshot.x-immediately.x)<.6&&Math.abs(snapshot.y-immediately.y)<.6,
    'visible character must not glide after instant click');
  }
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>{
   const css=getComputedStyle(document.querySelector('#rooms .social-avatar.self'));
   return {transition:css.transitionDuration,
    inputVisible:!!document.getElementById('message')?.getClientRects().length};
  });
  assert.ok(mobile.transition.split(',').every(x=>Number.parseFloat(x)===0),
   'iPhone-sized ChatRoom must still teleport');
  assert.ok(mobile.inputVisible,'mobile input must remain usable');
  assert.deepEqual(errors,[],'no browser errors');
  console.log('CHATROOM_NATIVE_INSTANT_SEAT_PASS',JSON.stringify({
   engine:process.env.FOURLEAF_BROWSER||'chromium',before,after:immediately.seat,mobile}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHATROOM NATIVE SEAT FAILED',e.stack||e);process.exit(1)});
