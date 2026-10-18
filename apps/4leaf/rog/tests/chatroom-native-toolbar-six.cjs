'use strict';
/* Real 2002 source MainFrame toolbar actor collision acceptance across ALL
 * six independently archived 794x528 ChatRoom backdrops.
 * DO NOT invent NPC participants: one genuine local browser session
 * enters each real room. Desktop Chromium AND WebKit run the same test.
 * An alternate toolbar hit location is a WEB inferred intervention, never
 * an assertion about exact 2004 historical toolbar coordinates.
 */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
async function run(engine){
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,...(engine==='chromium'?{args:['--no-sandbox']}:{})
 });
 try{
  const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
  const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  const results=[];
  for(let background=0;background<6;background++){
   await page.evaluate(bg=>{
    window.__LEAF_SOCIAL__.openRegion('north');
    window.__ROG_TEST__.go('rooms');
    window.__LEAF_SOCIAL__.createRoom('실제 원본 방 입력 검사 '+bg,bg,12);
   },background);
   await page.waitForFunction(bg=>{
    const frame=document.querySelector('#social-image-frame');
    return frame?.classList.contains('social-interior')&&
     getComputedStyle(frame).backgroundImage.includes('/original/ChatRoom/room'+bg+'.png')&&
     frame.querySelectorAll('.social-avatar.self').length===1&&
     frame.querySelectorAll('.social-classic-toolbar .social-original-tool').length===6;
   },background,{timeout:15000});
   const hit=await page.evaluate(bg=>{
    const room=document.querySelector('#social-image-frame');
    const bar=room.querySelector('.social-classic-toolbar');
    const actors=[...room.querySelectorAll('.social-avatar')];
    const tools=[...bar.querySelectorAll('.social-original-tool')];
    const check=element=>{
     const r=element.getBoundingClientRect();
     const elementAt=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
     return {ok:elementAt===element||element.contains(elementAt),
      intercepted:elementAt?.className||null,rect:[r.x,r.y,r.width,r.height]};
    };
    return {background:bg,roomSource:getComputedStyle(room).backgroundImage,
      nativeToolbar:getComputedStyle(tools[0]).backgroundImage,
      toolbarPoints:tools.map(check),
      selfPoint:check(actors.find(el=>el.classList.contains('self'))),
      authenticActors:actors.length,
      font:tools[0].getAttribute('aria-label'),
      alternate:bar.dataset.webPositionInferred,
      unavailableHits:Number(bar.dataset.nativeToolHitCollisions||-1)};
   },background);
   assert.equal(hit.authenticActors,1,'never invent peers to fill 2004 screenshot room');
   assert.ok(hit.roomSource.includes('original/ChatRoom/room'+background+'.png'),
    'room source PNG must be the independently extracted genuine backdrop');
   assert.ok(hit.nativeToolbar.includes('original/MainFrame/toolbarbtn.png'));
   assert.equal(hit.toolbarPoints.length,6,'six independently live source toolbar controls');
   assert.ok(hit.toolbarPoints.every(p=>p.ok),
    'all six real source tool buttons must be physically pointer-clickable on room'+background+': '+JSON.stringify(hit));
   assert.ok(hit.selfPoint.ok,
    'user must still physically interact with actual seated source Registry avatar room'+background+': '+JSON.stringify(hit));
   assert.equal(hit.unavailableHits,0,'collision avoidance must not leave source toolbar buttons covered');
   results.push({room:background,seat:'initial',alternate:hit.alternate});
   // Move the ACTUAL logged-in user via the application's original
   // clickable-floor teleport handler to two occupied source seat regions,
   // including the historic room3 toolbar collision (#3 and #9).
   // This never fabricates peers nor edits hidden game state directly.
   const seatPairs=[
    [[73,66],[39,92]],[[76,64],[40,91]],[[73,63],[39,92]],
    [[81,83],[77,69]],[[61,72],[29,97]],[[74,66],[39,93]]
   ];
   for(const [index,point] of [3,9].map((seat,i)=>[seat,seatPairs[background][i]])){
    await page.evaluate(([x,y])=>{
     const frame=document.querySelector('#social-image-frame'),r=frame.getBoundingClientRect();
     frame.dispatchEvent(new MouseEvent('click',{
      bubbles:true,cancelable:true,
      clientX:r.left+r.width*x/100,clientY:r.top+r.height*y/100
     }));
    },point);
    await page.waitForFunction(seat=>
      document.querySelector('#social-image-frame .social-avatar.self')?.dataset.seat===String(seat),
      index,{timeout:3000});
    const moved=await page.evaluate(()=>{
     const frame=document.getElementById('social-image-frame');
     const bar=frame.querySelector('.social-classic-toolbar');
     const actions=[...bar.querySelectorAll('.social-original-tool')];
     const sprite=frame.querySelector('.social-avatar.self');
     const actual=el=>{
      const r=el.getBoundingClientRect();
      const target=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
      return target===el||el.contains(target);
     };
     return {hits:actions.map(actual),actor:actual(sprite),
      seat:sprite.dataset.seat,collision:bar.dataset.nativeToolHitCollisions,
      relocated:bar.dataset.webPositionInferred};
    });
    assert.equal(moved.seat,String(index),'floor click actually teleports real user to requested vacant source slot');
    assert.ok(moved.hits.every(Boolean)&&moved.actor,
      'all 7 actual mouse targets must work when real source participant stands at seat '+index+
      ' in original room '+background+': '+JSON.stringify(moved));
    assert.equal(moved.collision,'0');
    results.push({room:background,seat:index,alternate:moved.relocated});
   }
  }
  assert.deepEqual(errors,[],'no browser errors for six real ChatRoom environments');
  await page.screenshot({path:'leaf-chatroom-six-native-input-'+engine+'.png'});
  console.log('ALL SIX SOURCE CHATROOM TOOLBAR HIT PASSED',JSON.stringify({engine,results}));
 }finally{await browser.close()}
}
(async()=>{
 if(process.env.FOURLEAF_ONLY_WEBKIT!=='1')await run('chromium');
 if(process.env.FOURLEAF_SKIP_WEBKIT!=='1')await run('webkit');
})().catch(e=>{console.error('SIX ROOM REAL SOURCE TOOL INPUT FAILURE',e.stack||e);process.exit(1)});
