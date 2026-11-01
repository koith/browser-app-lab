'use strict';
/* CHT-02/P0-CHAT: real Dice IMG scroll, async social BroadcastChannel,
 * system commands, and network's shared message writer. Previous production
 * code snapped top=0 to bottom and disabled the down source control.
 * Keep latest auto-follow when reader is already at bottom. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__&&window.__LEAF_NATIVE_DICE_CHAT_SCROLL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const form=document.getElementById('chat-form'),input=document.getElementById('message');
   for(let i=0;i<40;i++){input.value='실제 채팅 이력 '+i+' '+'대화 '.repeat(8);form.requestSubmit()}
  });
  await page.waitForFunction(()=>document.getElementById('chat-log')?.scrollHeight-
   document.getElementById('chat-log')?.clientHeight>60);
  await page.locator('#chat-log').focus();
  await page.keyboard.press('Home');
  await page.waitForFunction(()=>document.getElementById('chat-log').scrollTop<2);
  const scope=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().scope);
  const send=async message=>page.evaluate(([scope,message])=>{
   const ch=new BroadcastChannel('4leaf_social_presence_v3');
   ch.postMessage({v:1,from:'qa-other-tab',kind:'chat',
    id:'qa-'+Math.random(),scope,user:'상대',text:message,
    sender:'qa-other-tab',time:Date.now()});
   ch.close();
  },[scope,message]);
  await send('다른 탭에서 온 메시지');
  await page.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('다른 탭에서 온 메시지'));
  await page.evaluate(()=>{
   const node=document.createElement('div');node.textContent='네트워크 상대 채팅';
   window.__LEAF_CHAT_APPEND__(document.getElementById('chat-log'),node,90);
  });
  await page.evaluate(()=>window.__LEAF_SOCIAL__.send('/help'));
  await page.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('/주사위'));
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));
  const oldest=await page.evaluate(()=>{
   const l=document.getElementById('chat-log');
   return {top:l.scrollTop,max:l.scrollHeight-l.clientHeight,
    native:window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState()};
  });
  assert.ok(oldest.max>60);
  assert.ok(oldest.top<2,'remote/system messages cannot displace older history: '+JSON.stringify(oldest));
  assert.equal(oldest.native.upEnabled,false);
  assert.equal(oldest.native.downEnabled,true);
  await page.keyboard.press('End');
  await page.waitForFunction(()=>{
   const l=document.getElementById('chat-log');
   return l.scrollHeight-l.clientHeight-l.scrollTop<=3;
  });
  await send('신규 메시지 자동 따라가기');
  await page.waitForFunction(()=>document.getElementById('chat-log')?.textContent.includes('신규 메시지 자동 따라가기'));
  const newest=await page.evaluate(()=>{
   const l=document.getElementById('chat-log');
   return {gap:l.scrollHeight-l.clientHeight-l.scrollTop,
    native:window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState()};
  });
  assert.ok(newest.gap<=3);
  assert.equal(newest.native.downEnabled,false);
  assert.deepEqual(errors,[]);
  console.log('ROUND4 DICE ASYNC HISTORY SCROLL PASS',JSON.stringify({oldest,newest}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ROUND4 DICE ASYNC SCROLL FAILED',e.stack||e);process.exit(1)});
