'use strict';
/* CHT-02: the 2004 original ChatRoom has ONE 390x97 history pane.
 * Two actual browser peers must not throw the older-history reader to the
 * bottom when a remote peer or a real system message arrives. The 52x40
 * source sprite remains attached to the same live transcript.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,
  args:engine===chromium?['--no-sandbox']:[]});
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
 await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const host=await context.newPage(),guest=await context.newPage(),errors=[];
 for(const p of [host,guest])p.on('pageerror',e=>errors.push(e.message));
 try{
  const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await host.goto(url);
  await host.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_NATIVE_SCROLLBAR__&&window.__ROG_TEST__);
  const id=await host.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   return window.__LEAF_SOCIAL__.createRoom('원본 채팅 읽기 위치 유지 검증',4);
  });
  await guest.goto(url);
  await guest.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await guest.evaluate(room=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.joinRoom(room);
  },id);
  await Promise.all([host,guest].map(p=>p.waitForFunction(()=>
   document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,null,{timeout:16000})));
  await host.waitForFunction(()=>document.querySelector('#chat-log')?.clientHeight===97&&
   window.__LEAF_NATIVE_SCROLLBAR__?.getState().ready===true,null,{timeout:12000});
  for(let i=0;i<32;i++)
   await guest.evaluate(i=>window.__LEAF_SOCIAL__.send('원본 채팅 읽기 검사 '+String(i).padStart(2,'0')),i);
  await host.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('원본 채팅 읽기 검사 31')&&
   window.__LEAF_NATIVE_SCROLLBAR__?.getState().overflow>160,null,{timeout:16000});
  const before=await host.evaluate(()=>{
   const log=document.getElementById('chat-log');
   const scroll=document.getElementById('social-native-chat-scroll');
   return {top:log.scrollTop,max:log.scrollHeight-log.clientHeight,
    count:document.querySelectorAll('#chat-log').length,
    scrollCount:document.querySelectorAll('#social-native-chat-scroll').length,
    source:scroll.dataset.source,
    formRect:document.getElementById('chat-form').getBoundingClientRect().toJSON(),
    logRect:log.getBoundingClientRect().toJSON()};
  });
  assert.ok(before.max>160&&before.top>=before.max-3,
   'new real peer messages follow latest ONLY while currently at bottom');
  assert.deepEqual([before.count,before.scrollCount],[1,1],
   'never create a second/fake historical chat log');
  assert.equal(before.source,'ChatRoom/scrollbar.png');
  // Real pointer on the native source scrollbar track, no synthetic scrollTop.
  await host.locator('#social-native-scroll-track').click({position:{x:5,y:4}});
  await host.waitForFunction(()=>document.getElementById('chat-log').scrollTop<4);
  const reading=await host.evaluate(()=>{
   const log=document.getElementById('chat-log');
   return {top:log.scrollTop,limit:log.scrollHeight-log.clientHeight,
    percent:document.getElementById('social-native-scroll-track').getAttribute('aria-valuenow')};
  });
  assert.ok(reading.limit>160&&reading.top<4,'real source pointer reaches oldest messages');
  await guest.evaluate(()=>window.__LEAF_SOCIAL__.send('친구가 보낸 새로운 원본 메시지'));
  await host.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('친구가 보낸 새로운 원본 메시지'));
  const remote=await host.evaluate(()=>{
   const log=document.getElementById('chat-log');
   return {top:log.scrollTop,max:log.scrollHeight-log.clientHeight,
    down:document.getElementById('social-native-scroll-down').disabled};
  });
  assert.ok(Math.abs(remote.top-reading.top)<=2,
   'remote live peer cannot snap older reader to bottom: '+JSON.stringify({reading,remote}));
  assert.ok(remote.max>reading.limit);
  assert.equal(remote.down,false,'source-native down button stays actionable while history is being read');

  // A real /help command produces an original-room system line via the same
  // shared log, and must obey the identical history-reading rule.
  await host.evaluate(()=>window.__LEAF_SOCIAL__.send('/help'));
  await host.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('/주사위'));
  const afterSystem=await host.locator('#chat-log').evaluate(el=>el.scrollTop);
  assert.ok(Math.abs(afterSystem-reading.top)<=2,'system notice must not hijack the history reader');

  // Keyboard controls operate on the one source 52x40 scroll rail.
  const track=host.locator('#social-native-scroll-track');
  assert.equal(await track.getAttribute('role'),'scrollbar');
  assert.equal(await track.getAttribute('tabindex'),'0');
  await track.focus();
  await host.keyboard.press('End');
  const end=await host.locator('#chat-log').evaluate(el=>({
   top:el.scrollTop,max:el.scrollHeight-el.clientHeight
  }));
  assert.ok(end.max-end.top<=2,'End scrolls to the last peer message');
  await host.keyboard.press('PageUp');
  const pageUp=await host.locator('#chat-log').evaluate(el=>el.scrollTop);
  assert.ok(pageUp<end.top-30,'PageUp reads earlier live history');
  await host.keyboard.press('ArrowDown');
  const down=await host.locator('#chat-log').evaluate(el=>el.scrollTop);
  assert.ok(down>pageUp+20,'ArrowDown advances the same transcript');
  await host.keyboard.press('Home');
  const home=await host.locator('#chat-log').evaluate(el=>el.scrollTop);
  assert.ok(home<3,'Home reaches the oldest actual message');
  await host.keyboard.press('PageDown');
  const pageDown=await host.locator('#chat-log').evaluate(el=>el.scrollTop);
  assert.ok(pageDown>home+30,'PageDown navigates the genuine source chat window');

  await host.keyboard.press('End');
  await guest.evaluate(()=>window.__LEAF_SOCIAL__.send('맨 아래를 읽을 때는 새 글 따라가기'));
  await host.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('맨 아래를 읽을 때는 새 글 따라가기'));
  const newest=await host.locator('#chat-log').evaluate(el=>({
   top:el.scrollTop,max:el.scrollHeight-el.clientHeight
  }));
  assert.ok(newest.max-newest.top<=2,'latest-follow behavior remains intact at bottom');

  await host.locator('#social-back').click();
  assert.equal(await host.locator('#social-native-chat-scroll').count(),1);
  assert.equal(await host.locator('#social-native-chat-scroll').evaluate(el=>getComputedStyle(el).display),'none',
   'native scrollbar remains invisible when no original room is active');
  await host.setViewportSize({width:390,height:844});
  await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('모바일 스크롤 영역 검증',4));
  assert.ok(await host.locator('#message').isVisible());
  assert.equal(await host.locator('#social-native-chat-scroll').evaluate(el=>getComputedStyle(el).display),'none',
   'small mobile viewport keeps its accessible OS chat scroller');
  assert.deepEqual(errors,[]);
  console.log('NATIVE 2004 CHAT HISTORY READING PASS '+JSON.stringify({
   engine:engine.name(),room:id,before,reading,remote,afterSystem,end,pageUp,down,home,pageDown,newest}));
 }finally{
  await context.close();await browser.close();
 }
})().catch(e=>{console.error('NATIVE 2004 CHAT HISTORY READING FAILED:',e.stack||e);process.exit(1)});
