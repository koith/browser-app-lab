'use strict';
/* Original 2002 Dice IMG 80x16 bitmap; test ACTUAL user chat history,
   source up/down button hold and focussed keyboard paging. Native input
   gesture timing is a WEB reconstruction, not reverse-engineered FPS. */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',err=>errors.push(String(err)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_NATIVE_DICE_CHAT_SCROLL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const input=document.getElementById('message'),form=document.getElementById('chat-form');
   for(let i=0;i<38;i++){
    input.value='원본 주잔 채팅 장기 이력 '+String(i).padStart(2,'0')+
     ' · 실제 플레이어 입력과 스크롤 '+('대화 '.repeat(5));
    form.requestSubmit();
   }
  });
  await page.waitForFunction(()=>document.getElementById('chat-log').scrollHeight-
   document.getElementById('chat-log').clientHeight>400);
  const early=await page.evaluate(()=>{
   const el=document.getElementById('chat-log'),source=window.__LEAF_NATIVE_DICE_CHAT_SCROLL__;
   const img=getComputedStyle(document.querySelector('.leaf-dice-chat-scroll')).backgroundImage;
   return {source:source.getState(),image:img,overflow:el.scrollHeight-el.clientHeight,
    count:el.children.length,focusable:el.tabIndex};
  });
  assert.ok(early.image.includes('/original/IMG/scrollbutton.png'),'2002 original bitmap on playable native arrows');
  assert.ok(early.count>=35&&early.overflow>400,'only real submitted chat log messages');
  assert.equal(early.focusable,0,'keyboard original chat history is accessible');
  const log=page.locator('#chat-log');
  await log.focus();
  await page.keyboard.press('Home');
  await page.waitForFunction(()=>document.getElementById('chat-log').scrollTop<2);
  await page.keyboard.press('PageDown');
  const paged=await log.evaluate(el=>el.scrollTop);
  assert.ok(paged>5,'focussed original transcript PageDown moves real history');
  await page.keyboard.press('PageUp');
  await page.waitForFunction(()=>document.getElementById('chat-log').scrollTop<2);
  await page.keyboard.press('End');
  await page.waitForFunction(()=>{
   const l=document.getElementById('chat-log');return l.scrollHeight-l.clientHeight-l.scrollTop<2;
  });
  if(!mobile){
   const up=page.locator('.messenger .leaf-dice-chat-scroll[data-direction="up"]');
   await up.waitFor();assert.ok(await up.isEnabled());
   await up.hover();await page.mouse.down();
   await page.waitForTimeout(850);
   const holding=await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState());
   assert.equal(holding.activeHeldDirection,'up','actual pointer press activates source repeat');
   assert.ok(holding.scrollTop<early.overflow-100,
    'holding actual original up arrow moves more than one line without faking DOM scroll');
   await page.mouse.up();
   await page.waitForFunction(()=>!window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState().activeHeldDirection);
   const released=await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState());
   await page.waitForTimeout(180);
   const stable=await log.evaluate(el=>el.scrollTop);
   assert.ok(Math.abs(stable-released.scrollTop)<3,'release stops native held scroll timer');
   // New actual chat cannot force history reader back to end.
   const append=await page.evaluate(()=>{
    const input=document.getElementById('message');
    input.value='원본 보류 대화 읽기 유지';
    document.getElementById('chat-form').requestSubmit();
    return {scrollTop:document.getElementById('chat-log').scrollTop,
     bottom:document.getElementById('chat-log').scrollHeight};
   });
   assert.ok(Math.abs(append.scrollTop-stable)<3,
    'fresh actual message preserves the original reader position');
  }else{
   assert.equal((await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState())).keyboardHistoryEnabled,true);
  }
  assert.equal(await page.locator('#board-nodes .tile').count(),104,'DMP playable game unchanged');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-original-source-chat-held-history-'+(mobile?'mobile-webkit':'chromium')+'.png'});
  console.log('ORIGINAL IMG CHATTING LIVE SOURCE BUTTON HOLD/KEYBOARD PASS',JSON.stringify({mobile,early,paged}));
 }finally{await browser.close();}
})().catch(error=>{console.error('SOURCE HELD CHAT FAILED',error.stack||error);process.exit(1)});
