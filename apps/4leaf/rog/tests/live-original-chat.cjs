// Production-only verification. Run after GitHub Pages finishes deployment.
// It opens the PUBLIC URL, not a local HTTP server or a PR build.
'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const BASE='https://koith.github.io/browser-app-lab/apps/4leaf/rog/';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const ctx=await browser.newContext({viewport:{width:1280,height:800}});
 const host=await ctx.newPage(),guest=await ctx.newPage();
 const errors=[],missing=[];
 for(const [name,page] of [['host',host],['guest',guest]]){
  page.on('pageerror',err=>errors.push(name+': '+String(err)));
  page.on('response',res=>{
   if(res.status()>=400&&res.url().includes('/apps/4leaf/rog/original/'))missing.push(name+': '+res.status()+' '+res.url());
  });
 }
 try{
  for(const page of [host,guest]){
   const response=await page.goto(BASE+'?qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:45000});
   assert.ok(response?.ok(),'public 4LEAF app must return HTTP 200');
   await page.waitForFunction(()=>!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:18000});
  }
  await host.locator('[data-region="north"]').click();
  await host.locator('.social-district-hotspot').nth(3).click();
  assert.equal(await host.locator('.social-directory-row').count(),0,'public server room list must not show six invented template rooms');
  assert.ok(await host.locator('.social-directory-empty').isVisible());
  await host.locator('#social-new-room').click();
  assert.equal(await host.locator('#social-modal [name="background"] option').count(),6,'all six original backgrounds remain available');
  await host.locator('#social-modal [name="name"]').fill('운영 배포 채팅 복원 검증');
  await host.locator('#social-modal [name="background"]').selectOption('3');
  await host.locator('#social-modal button[type="submit"]').click();
  await host.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',null,{timeout:20000});
  assert.equal(await host.locator('.social-avatar.self img').evaluate(e=>getComputedStyle(e).width),'75px','native sprite width on production');
  const buttons=host.locator('.social-classic-toolbar .social-original-tool');
  assert.equal(await buttons.count(),6,'native MainFrame toolbar must deploy');
  assert.ok(await buttons.first().evaluate(el=>getComputedStyle(el).backgroundImage.includes('original/MainFrame/toolbarbtn.png')),'original toolbar sprite loaded');
  assert.equal(await host.locator('.social-room-foreground').getAttribute('data-source'),'room3t');
  const alpha=await host.locator('.social-room-foreground').evaluate(canvas=>{
   const data=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
   let clear=0,painted=0;
   for(let i=3;i<data.length;i+=4){if(data[i]===0)clear++;else painted++}
   return {clear,painted};
  });
  assert.ok(alpha.clear>200&&alpha.painted>200,'foreground has both transparency and furniture pixels');
  const move=async(x,y)=>host.locator('.social-interior').evaluate((frame,p)=>{
   const rect=frame.getBoundingClientRect();
   frame.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+rect.width*p.x/100,clientY:rect.top+rect.height*p.y/100}));
   const avatar=frame.querySelector('.social-avatar.self');
   return {left:avatar.style.left,top:avatar.style.top,transition:getComputedStyle(avatar).transitionDuration};
  },{x,y});
  const first=await move(21,92),second=await move(66,72);
  assert.notDeepEqual({x:first.left,y:first.top},{x:second.left,y:second.top},'click must teleport between discrete standing slots');
  assert.equal(second.transition,'0s','movement must not interpolate');
  await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
  assert.ok(await host.locator('.social-avatar-chooser').isVisible(),'original toolbar control must work');
  await host.locator('.social-modal-title button').click();
  await guest.locator('[data-region="north"]').click();
  await guest.locator('.social-district-hotspot').nth(3).click();
  const roomId=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
  await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(room=>room.id===id),roomId,{timeout:10000});
  await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),roomId);
  await Promise.all([host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:10000}),guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:10000})]);
  await host.locator('#message').fill('운영 서버 실시간 동작 검증');
  await host.locator('#message').press('Enter');
  await guest.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('운영 서버 실시간 동작 검증'),null,{timeout:10000});
  assert.ok(await guest.locator('.social-speech').count()>0,'remote user sees an authentic chat bubble');
  await guest.setViewportSize({width:390,height:844});
  assert.ok(await guest.locator('#message').isVisible(),'mobile chat input accessible');
  await host.screenshot({path:'leaf-live-original-chat-desktop.png'});
  await guest.screenshot({path:'leaf-live-original-chat-mobile.png'});
  assert.deepEqual(errors,[],'no page runtime errors');
  assert.deepEqual(missing,[],'all original graphic assets load from Pages');
  console.log('LIVE ORIGINAL CHATROOM PASS',JSON.stringify({base:BASE,roomId,foreground:'room3t',toolbarButtons:6,originalAvatar:'75x141',chat:'cross-tab',deployment:'public-pages'}));
 }finally{await browser.close()}
})().catch(err=>{console.error('LIVE ORIGINAL CHATROOM FAILED:',err.stack||err);process.exit(1)});
