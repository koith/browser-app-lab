'use strict';
/* Real 2002/2004 ChatRoom source acceptance:
 * six original 794x528 room backdrops, two ACTUAL browser participants,
 * instant seat teleportation, native Registry/ChatRoom sprites, distinct
 * user seats and no synthetic NPCs. Seat anchor coordinates are
 * WEB-INFERRED pending historic EXE seat table; do not claim 1:1 origin.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const host=await context.newPage(),guest=await context.newPage();
 const errors=[],proof=[];
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 for(const page of [host,guest]){
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:12000});
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
  });
 }
 try{
  for(let background=0;background<6;background++){
   const rid=await host.evaluate(bg=>{
    window.__LEAF_SOCIAL__.openDirectory();
    return window.__LEAF_SOCIAL__.createRoom('원본 여섯 방 실제 좌석 '+bg,bg,12);
   },background);
   await guest.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
   await guest.waitForFunction(id=>
    window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),
    rid,{timeout:15000});
   await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),rid);
   await Promise.all([host,guest].map(page=>page.waitForFunction(id=>{
    const state=window.__LEAF_SOCIAL__.getState();
    const people=document.querySelectorAll('#social-avatar-layer .social-avatar');
    return state.roomId===id && people.length===2 &&
      [...people].every(el=>el.querySelector('img')?.complete&&
       el.querySelector('img')?.naturalWidth===75);
   },rid,{timeout:15000})));
   const before=await host.evaluate(bg=>{
    const scene=document.querySelector('#social-image-frame');
    const fig=document.querySelector('#social-avatar-layer .social-avatar.self');
    const guest=document.querySelector('#social-avatar-layer .social-avatar:not(.self)');
    const backdrop=getComputedStyle(scene).backgroundImage;
    const img=fig.querySelector('img');
    const ir=img.getBoundingClientRect(),fr=scene.getBoundingClientRect();
    return {native:[img.naturalWidth,img.naturalHeight],
     room:[scene.offsetWidth,scene.offsetHeight],
     bg:backdrop,seat:Number(fig.dataset.seat),peerSeat:Number(guest.dataset.seat),
     transition:getComputedStyle(fig).transitionDuration,
     footError:Math.abs(ir.bottom-(fr.top+fr.height*parseFloat(fig.style.top)/100)),
     foreground:scene.querySelector('.social-room-foreground')?.dataset.source||null,
     names:[...scene.querySelectorAll('.social-avatar-name')].map(x=>x.textContent)};
   },background);
   assert.deepEqual(before.native,[75,141],'native full-size Registry original body in each room');
   assert.deepEqual(before.room,[794,528],'real original 794x528 room frame');
   assert.ok(before.bg.includes('/original/ChatRoom/room'+background+'.png'),
    'wrong source room painted: '+JSON.stringify(before));
   assert.notEqual(before.seat,before.peerSeat,'two real people may never occupy the same source seat');
   assert.equal(before.transition,'0s','no invented walking animation between original room seats');
   assert.ok(before.footError<3,'actual original 75x141 avatar feet touch seat anchor');
   if(background>=3)assert.equal(before.foreground,'room'+background+'t','correct actual foreground source art');
   else assert.equal(before.foreground,null,'never invent missing native foreground artwork');
   const move=await host.evaluate(()=>{
    const fig=document.querySelector('#social-avatar-layer .social-avatar.self');
    const prev=Number(fig.dataset.seat);
    const frame=document.querySelector('#social-image-frame');
    const r=frame.getBoundingClientRect();
    // Previous real presence persists across rooms. The opposite corner
    // can be occupied or map onto the same source slot in rooms 3/4.
    // Try other genuine click targets: no test-only mutation of positions.
    const candidates=prev>=6?[
     {x:19,y:63},{x:76,y:66},{x:39,y:78},{x:21,y:92}
    ]:[
     {x:75,y:96},{x:19,y:63},{x:76,y:66},{x:39,y:78}
    ];
    let next=null,attempts=0;
    for(const choose of candidates){
     attempts++;
     frame.dispatchEvent(new MouseEvent('click',{bubbles:true,
      clientX:r.left+r.width*choose.x/100,
      clientY:r.top+r.height*choose.y/100}));
     next=document.querySelector('#social-avatar-layer .social-avatar.self');
     if(Number(next?.dataset.seat)!==prev)break;
    }
    return {prev,seat:Number(next?.dataset.seat),attempts,
     transition:getComputedStyle(next).transitionDuration,
     x:parseFloat(next.style.left),y:parseFloat(next.style.top),
     other:Number(document.querySelector('#social-avatar-layer .social-avatar:not(.self)').dataset.seat)};
   });
   assert.notEqual(move.seat,move.prev,'a genuine room-scene click must teleport to a different native slot');
   assert.notEqual(move.seat,move.other,'real guest seat is occupied, never displace them');
   assert.equal(move.transition,'0s','slot changes are instant, without interpolated CSS tween');
   await guest.waitForFunction(({seat})=>
    Number(document.querySelector('#social-avatar-layer .social-avatar:not(.self)')?.dataset.seat)===seat,
    {seat:move.seat},{timeout:12000});
   const guestSeat=await guest.locator('.social-avatar:not(.self)').getAttribute('data-seat');
   assert.equal(Number(guestSeat),move.seat,
    'actual remote browser sees the changed native slot, not an independent simulation');
   const face=await host.locator('.social-avatar.self img').evaluate(el=>el.style.transform);
   await host.locator('.social-avatar.self').click({timeout:5500});
   assert.notEqual(await host.locator('.social-avatar.self img').evaluate(el=>el.style.transform),
    face,'real click flips native Registry actor facing in every original room');
   assert.equal(await host.locator('#social-avatar-layer .social-avatar').count(),2);
   const buttons=await host.locator('.social-original-tool').count();
   assert.equal(buttons,6,'all original MainFrame tool actions must still exist');
   if(background===4)await host.screenshot({path:'leaf-source-sixroom-real-twopeers-room4.png'});
   proof.push({room:background,native:before.native,actors:2,seatFrom:move.prev,
    seatTo:move.seat,remoteVerified:true,foreground:before.foreground});
   await guest.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
   await host.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
  }
  assert.deepEqual(errors,[],'no browser exceptions navigating six source rooms');
  console.log('SIX ORIGINAL CHATROOM REAL 2-PEER SEATS PASS '+JSON.stringify(proof));
 }finally{await browser.close()}
})().catch(e=>{console.error('SIX ORIGINAL CHATROOM QA FAILED',e.stack||e);process.exit(1)});
