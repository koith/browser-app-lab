'use strict';
// Historical 196x267 ChatRoom/expdialogbtn.png plus live peer expression,
// never fabricated participants, cloned message windows or fake server events.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const host=await context.newPage(),guest=await context.newPage();
 const errors=[];
 for(const page of [host,guest]){
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 }
 try{
  const BASE=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await host.goto(BASE);
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_NATIVE_EXPRESSIONS__);
  const source=await host.evaluate(async()=>{
   const img=new Image();img.src='./original/ChatRoom/expdialogbtn.png';await img.decode();
   return {natural:[img.naturalWidth,img.naturalHeight],
    exposed:window.__LEAF_NATIVE_EXPRESSIONS__.getState()};
  });
  assert.deepEqual(source.natural,[196,267],'native original expression atlas is 196x267');
  assert.deepEqual(source.exposed.options,['하하','우씨','으앙','좋아','헉','기타'],
   'six genuine original Korean face buttons, not invented emoji');
  const id=await host.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   return window.__LEAF_SOCIAL__.createRoom('원본 표정 두 사람 실시간 검사',4);
  });
  await guest.goto(BASE);
  await guest.evaluate(room=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.joinRoom(room);
  },id);
  await Promise.all([
   host.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,null,{timeout:15000}),
   guest.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,null,{timeout:15000})
  ]);
  assert.equal(await host.locator('.social-original-tool').count(),6,
   'historical toolbar six existing actions remain unaffected');
  const trigger=host.locator('.social-exp-trigger');
  assert.ok(await trigger.isVisible(),'the authentic source expression entry is usable in ChatRoom');
  const style=await trigger.evaluate(el=>getComputedStyle(el).backgroundImage);
  assert.ok(style.includes('original/ChatRoom/expdialogbtn.png'),'button uses the actual source atlas');
  await trigger.click();
  const palette=host.locator('#social-native-expression-palette');
  assert.ok(await palette.isVisible(),'original expression palette opened in the active room');
  assert.equal(await palette.locator('button').count(),6,'real six sprite buttons exist');
  const art=await palette.locator('button').first().evaluate(el=>({
   image:getComputedStyle(el).backgroundImage,
   size:[el.getBoundingClientRect().width,el.getBoundingClientRect().height],
   text:el.getAttribute('aria-label')
  }));
  assert.ok(art.image.includes('original/ChatRoom/expdialogbtn.png'));
  assert.deepEqual(art.size,[66,22],'source face+Korean label kept at native 66x22');
  assert.equal(art.text,'표정 하하');
  await host.screenshot({path:'leaf-original-chatroom-expression-palette.png'});
  await palette.locator('button[data-expression="하하"]').click();
  await Promise.all([
   host.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('[표정] 하하'),null,{timeout:10000}),
   guest.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('[표정] 하하'),null,{timeout:12000})
  ]);
  assert.equal(await host.locator('#social-native-expression-palette').count(),0,'selection closes the native picker');
  const local=await host.locator('.social-avatar.self .social-native-expression').evaluate(el=>({
   name:el.dataset.nativeExpression,
   src:el.dataset.source,
   bg:getComputedStyle(el).backgroundImage,
   position:getComputedStyle(el).backgroundPosition
  }));
  assert.equal(local.name,'하하');
  assert.equal(local.src,'ChatRoom/expdialogbtn.png');
  assert.ok(local.bg.includes('original/ChatRoom/expdialogbtn.png'),'source original face is attached to genuine actor');
  await guest.waitForFunction(()=>document.querySelector('.social-avatar:not(.self) .social-native-expression')?.dataset.nativeExpression==='하하',
   null,{timeout:12000});
  const remote=await guest.locator('.social-avatar:not(.self) .social-native-expression').getAttribute('data-source');
  assert.equal(remote,'ChatRoom/expdialogbtn.png','the second live peer sees the same original source face');
  const hostCount=await host.locator('#social-avatar-layer .social-avatar').count();
  const guestCount=await guest.locator('#social-avatar-layer .social-avatar').count();
  assert.deepEqual([hostCount,guestCount],[2,2],'expressions create no fake NPCs');
  await trigger.click();
  await palette.locator('button').first().focus();
  await host.keyboard.press('Escape');
  assert.equal(await host.locator('#social-native-expression-palette').count(),0,'Escape closes expression tray');
  assert.equal(await trigger.getAttribute('aria-expanded'),'false');
  await host.setViewportSize({width:390,height:844});
  await trigger.click();
  assert.equal(await palette.locator('button').count(),6,'mobile preserves original source palette');
  await palette.locator('button[data-expression="좋아"]').click();
  await guest.waitForFunction(()=>document.querySelector('.social-avatar:not(.self) .social-native-expression')?.dataset.nativeExpression==='좋아',
   null,{timeout:12000});
  await guest.locator('#social-back').click();
  assert.equal(await guest.locator('.social-native-expression').count(),0,'leaving genuine ChatRoom vacates original expression overlay');
  assert.deepEqual(errors,[],'source expressions and two real clients cause no page exceptions');
  console.log('NATIVE CHATROOM EXPRESSION PASS',JSON.stringify({source,local,remote,realPeers:[hostCount,guestCount]}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE CHATROOM EXPRESSION FAILED',e.stack||e);process.exit(1)});
