'use strict';
/* CHT-02: archived 2002 Korean CP949 display-byte fixture -> actual modern
 * interactive chat input and transmitted Korean text. CP949 byte provenance
 * is verified for this fixture only: never claim 2004 server protocol. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  const cp949=Uint8Array.from([0xc7,0xd1,0xb1,0xdb]);
  const decoded=new TextDecoder('euc-kr',{fatal:true}).decode(cp949);
  assert.equal(decoded,'한글','archived Korean CP949 bytes decode exactly');
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('2004 한글 입력 검증',4,12);
  });
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden) #message');
  const input=page.locator('#message');
  const message=decoded+' 실제 전송·표시 회귀 123';
  await input.fill(message);
  await input.press('Enter');
  await page.waitForFunction(text=>document.getElementById('chat-log')?.textContent.includes(text),message,{timeout:15000});
  const status=await page.evaluate(()=>{
   const frame=document.querySelector('#social-image-frame').getBoundingClientRect();
   const form=document.querySelector('#chat-form').getBoundingClientRect();
   const room=document.querySelector('#social-image-frame');
   return {room:[room.offsetWidth,room.offsetHeight],inputTop:Math.round(form.top-frame.top),
    text:document.getElementById('chat-log').textContent,
    source:getComputedStyle(room).backgroundImage,
    userCount:document.querySelectorAll('.social-avatar').length};
  });
  assert.deepEqual(status.room,[794,528]);
  assert.ok(status.source.includes('original/ChatRoom/room4.png'));
  assert.equal(status.userCount,1,'never invent screenshot occupants');
  assert.ok(status.text.includes(message),'Korean text round-trips through real room log');
  assert.ok(Math.abs(status.inputTop-97)<=3,'2004 photographic white input-band anchor must be preserved');
  assert.deepEqual(errors,[]);
  console.log('CHT02_CP949_KOREAN_DISPLAY_INPUT_PASS',JSON.stringify({engine:engine.name(),status:{...status,text:message},originalCP949ServerProtocol:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHT02_CP949_KOREAN_DISPLAY_INPUT_FAIL',e.stack||e);process.exit(1)});
