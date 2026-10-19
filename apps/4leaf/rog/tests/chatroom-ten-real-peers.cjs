'use strict';
/* Historical chat_ref.jpg real 10/11-person roster acceptance.
 * This creates TEN independent LIVE browsing tabs, not CSS clones,
 * fabricated server occupants, or synthetic fake guest divs.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900},
  serviceWorkers:'block'});
 const pages=[],errors=[];
 try{
  const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  const host=await context.newPage();pages.push(host);
  host.on('pageerror',e=>errors.push('host:'+e.message));
  await host.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await host.goto(base,{waitUntil:'domcontentloaded'});
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  const id=await host.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   return window.__LEAF_SOCIAL__.createRoom('원작 실접속 10명 검증',4,12);
  });
  await host.waitForSelector('#rooms.classic-chat-room');
  assert.equal(await host.locator('.social-avatar').count(),1);
  for(let i=1;i<10;i++){
   const page=await context.newPage();pages.push(page);
   page.on('pageerror',err=>errors.push('peer'+i+':'+err.message));
   await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
   await page.goto(base,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
   await page.evaluate(({id,i})=>{
    document.getElementById('profile-name').textContent='실참가자'+i;
    window.__LEAF_SOCIAL__.openRegion('north');
    window.__ROG_TEST__.go('rooms');
    window.__LEAF_SOCIAL__.joinRoom(id);
   },{id,i});
   if(i===1){
    await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().people.length===2,
     null,{timeout:12000});
    assert.equal(await host.locator('#social-peer-list .social-user-row').count(),2,
     'two genuinely joined live browser tabs, not fake roster rows');
   }
  }
  await host.waitForFunction(()=>{
   const peers=window.__LEAF_SOCIAL__?.getState?.().people||[];
   return peers.length===10&&document.querySelectorAll(
    '#social-avatar-layer .social-avatar').length===10&&
    document.querySelectorAll('#social-peer-list .social-user-row').length===10;
  },null,{timeout:25000});
  const proof=await host.evaluate(()=>{
   const state=window.__LEAF_SOCIAL__.getState();
   const peers=[...document.querySelectorAll('#social-peer-list .social-user-row')]
     .map(row=>row.querySelector('b')?.textContent?.replace(/ \(나\)$/,''));
   const occupants=[...document.querySelectorAll('#social-avatar-layer .social-avatar')]
     .map(x=>({peer:x.dataset.peer,seat:Number(x.dataset.seat),
       img:x.querySelector('img')?.getAttribute('src'),transition:getComputedStyle(x).transitionDuration,
       nativePixels:[x.querySelector('img')?.naturalWidth,
        x.querySelector('img')?.naturalHeight]}));
   const box=document.getElementById('social-peer-list');
   const scroll={height:box.clientHeight,content:box.scrollHeight};
   box.scrollTop=box.scrollHeight;
   return {userCount:state.people.length,rosterCount:peers.length,
    names:peers,ids:state.people.map(p=>p.id),occupants,
    number:document.getElementById('social-native-user-count').textContent,
    nativeUserList:document.getElementById('social-original-userlist').dataset.ready,
    originalHeader:[document.getElementById('social-original-userlist').width,
     document.getElementById('social-original-userlist').height],
    scroll:{...scroll,top:box.scrollTop},
    source:document.getElementById('social-image-frame').style.backgroundImage,
    chatCount:document.querySelectorAll('#social-actor-menu').length};
  });
  assert.equal(proof.userCount,10);
  assert.equal(proof.rosterCount,10);
  assert.equal(new Set(proof.ids).size,10,'all ten people must be distinct genuine connected tabs');
  assert.equal(new Set(proof.names).size,10,'original userlist cannot fabricate ten identical Guest NPC names');
  assert.equal(proof.number,'10명');
  assert.deepEqual(proof.originalHeader,[150,38],'genuine original ChatRoom userlist art');
  assert.ok(proof.nativeUserList==='true','recovered original userlist art actually decoded');
  assert.ok(proof.source.includes('ChatRoom/room4.png'),'original 2004 wood-room source retained');
  assert.equal(proof.occupants.length,10);
  assert.equal(new Set(proof.occupants.map(p=>p.peer)).size,10);
  assert.equal(new Set(proof.occupants.map(p=>p.seat)).size,10,'ten actual users occupy ten distinct source slots');
  assert.ok(proof.occupants.every(p=>p.seat>=0&&p.seat<12&&p.transition==='0s'),
   'real original seats snap immediately, never with tweening');
  assert.ok(proof.occupants.every(p=>p.img?.includes('/original/Registry/')),
   'only real original source Registry avatar bodies are rendered');
  assert.ok(proof.scroll.content>proof.scroll.height&&proof.scroll.top>0,
   'ten authentic names cause native user roster to scroll, not clip');
  assert.equal(proof.chatCount,0,'no synthetic peer menus');
  await host.screenshot({path:'leaf-original-wood-room-ten-real-participants.png'});
  // Real departure must decrement participant list; stale/fake occupants
  // may not remain when nine physical browser tabs close.
  await Promise.all(pages.slice(1).map(page=>page.close()));
  pages.length=1;
  await host.waitForFunction(()=>{
   const social=window.__LEAF_SOCIAL__?.getState?.();
   return social?.people?.length===1&&
    document.querySelectorAll('#social-peer-list .social-user-row').length===1&&
    document.querySelectorAll('#social-avatar-layer .social-avatar').length===1;
  },null,{timeout:25000});
  assert.equal(await host.locator('#social-native-user-count').textContent(),'1명');
  assert.deepEqual(errors,[]);
  console.log('TEN GENUINE 2004 CHATROOM USERS PASS '+JSON.stringify({
   userCount:proof.userCount,rosterCount:proof.rosterCount,
   sourceRoom:proof.source,nativeHeader:proof.originalHeader,
   scroll:proof.scroll,distinctSeats:proof.occupants.length,
   afterRealClientDepart:1,syntheticUsers:0}));
 }finally{
  await Promise.all(pages.map(page=>page.close().catch(()=>{})));
  await browser.close();
 }
})().catch(e=>{console.error('10-PARTICIPANT ORIGINAL ROOM FAILED',e.stack||e);process.exit(1)});
