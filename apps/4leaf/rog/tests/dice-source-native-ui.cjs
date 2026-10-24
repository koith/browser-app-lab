'use strict';
/* Real source-native Dice IMG controls, not a static image mock.
 * PNGs were extracted from SHA1-verified original 4leaf.zip ->
 * InstallShield Dice/IMG.pak, using source BMP dimensions and actual colors.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_NATIVE_DICE_CHAT_SCROLL__);
  const original=await page.evaluate(async()=>{
   const read=src=>new Promise((resolve,reject)=>{
    const img=new Image();img.onload=()=>resolve([img.naturalWidth,img.naturalHeight]);
    img.onerror=reject;img.src='./original/IMG/'+src;
   });
   return {
    buttons:await read('okcancelbut.png'),
    scroll:await read('scrollbutton.png'),
    stats:await read('stats.png')
   };
  });
  assert.deepEqual(original,{buttons:[256,36],scroll:[80,16],stats:[164,125]},
   'real extracted source BMP dimensions must be preserved, not redrawn mock button art');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.locator('#exit-game').click();
  await page.waitForSelector('#modal[data-native-dice-dialog="IMG/dialog.png"]:not(.hidden)');
  const buttons=await page.evaluate(()=>{
   const modal=document.querySelector('#modal');
   return [...modal.querySelectorAll('#modal-buttons button')].map(b=>({
    label:b.textContent,atlas:b.dataset.originalDiceAction||null,
    image:getComputedStyle(b).backgroundImage,
    position:getComputedStyle(b).backgroundPosition,
    size:[b.getBoundingClientRect().width,b.getBoundingClientRect().height]
   }));
  });
  const cancel=buttons.find(b=>b.label==='취소');
  const leave=buttons.find(b=>b.label==='나가기');
  assert.ok(cancel&&cancel.atlas==='cancel','native CANCEL source caption used only for genuine cancel');
  assert.ok(cancel.image.includes('IMG/okcancelbut.png'));
  assert.deepEqual(cancel.size,[64,18],'one original atlas slice remains source-native');
  assert.equal(leave?.atlas,null,'Exit remains truthful text, not a fake Confirm image');
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  assert.ok(await page.locator('#game').isVisible(),'real cancel button retains actual game');
  const up=page.locator('.messenger .leaf-dice-chat-scroll[data-direction="up"]');
  const down=page.locator('.messenger .leaf-dice-chat-scroll[data-direction="down"]');
  await up.waitFor();await down.waitFor();
  const controls=await page.evaluate(()=>{
   return [...document.querySelectorAll('.messenger .leaf-dice-chat-scroll')].map(b=>({
    source:b.dataset.originalSource,image:getComputedStyle(b).backgroundImage,
    rect:[b.getBoundingClientRect().width,b.getBoundingClientRect().height]
   }));
  });
  assert.equal(controls.length,2);
  assert.ok(controls.every(c=>c.source==='IMG/scrollButton.bmp'&&
   c.image.includes('IMG/scrollbutton.png')&&c.rect[0]===16&&c.rect[1]===16));
  // The former fixture directly appended 44 synthetic DOM children. A
  // published PWA can re-render chat, invalidating that scroll state between
  // waitForFunction and a Playwright enabled click. Feed the REAL game chat
  // form instead: no fake messages and no scroll-bar source replacement.
  const history=await page.evaluate(()=>{
   const log=document.getElementById('chat-log'),
    form=document.getElementById('chat-form'),
    input=document.getElementById('message');
   for(let i=0;i<44;i++){
    input.value='2002 원본 IMG 채팅 이력 '+i+' · '+('대화 '.repeat(8));
    form.requestSubmit();
   }
   // New live messages may legitimately follow the latest; the user then
   // deliberately scrolls to the older record via wheel/scrollbar.
   log.scrollTop=0;
   window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.refresh();
   return {messages:log.children.length,top:log.scrollTop,
    height:log.scrollHeight,client:log.clientHeight,
    enabled:window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState()};
  });
  assert.ok(history.messages>=40,'real game chat form must append actual messages');
  assert.ok(history.height-history.client>60,
   'real transcript must overflow before a down arrow can be clickable: '+
   JSON.stringify(history));
  assert.equal(history.top,0,'user intentionally opened oldest message');
  await page.waitForFunction(()=>{
   const log=document.getElementById('chat-log'),
    down=document.querySelector('.messenger .leaf-dice-chat-scroll[data-direction="down"]');
   return log.scrollTop<2&&log.scrollHeight-log.clientHeight>60&&
    down&&!down.disabled;
  },null,{timeout:10000});
  assert.equal(await up.isDisabled(),true,'native up arrow inactive at oldest line');
  const preClick=await page.evaluate(()=>{
   const log=document.getElementById('chat-log');
   window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.refresh();
   return {top:log.scrollTop,max:log.scrollHeight-log.clientHeight,
    enabled:window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState()};
  });
  assert.equal(preClick.top,0,'reader stays at oldest line before actual button click');
  assert.equal(preClick.enabled.downEnabled,true,
   'real overflow must enable the native down button: '+JSON.stringify(preClick));
  // A direct user click is required, not element.evaluate(click) bypassing
  // native disabled/pointer semantics. Fail with a clear short error if the
  // live browser changes its scroll geometry.
  await down.click({timeout:8000});
  const current=await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState());
  assert.ok(current.scrollTop>0,'clicking archive button actually scrolls shared game chat');
  // True CHAT form message, not direct DOM manipulation: when a player has
  // intentionally left the newest line using the source IMG arrow, a live
  // incoming/self message must NOT yank the history back to its bottom.
  const afterMessage=await page.evaluate(()=>{
   const input=document.getElementById('message'),form=document.getElementById('chat-form');
   input.value='source history stays here';
   form.requestSubmit();
   const log=document.getElementById('chat-log');
   return {top:log.scrollTop,height:log.scrollHeight,client:log.clientHeight,
    message:log.lastElementChild?.textContent||''};
  });
  assert.ok(afterMessage.message.includes('source history stays here'),
   'the real shared chat handler must still send and append player text');
  assert.ok(Math.abs(afterMessage.top-current.scrollTop)<3,
   'incoming actual CHAT messages may not force a native-button reader to the latest line: '+
    JSON.stringify({current,afterMessage}));
  assert.ok(afterMessage.height-afterMessage.client-afterMessage.top>1,
   'reading source chat history remains possible during new messages');
  assert.equal(await up.isEnabled(),true,'up becomes available when history was moved');
  await up.focus();await page.keyboard.press('Enter');
  const backward=await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState());
  assert.ok(backward.scrollTop<current.scrollTop,'native keyboard Enter performs real scroll up');
  assert.equal(await page.locator('#board-nodes .tile').count(),104,'no source DMP game tile lost');
  assert.deepEqual(errors,[],'native extracted art does not break the browser');
  await page.screenshot({path:'leaf-original-dice-2002-ui-buttons.png'});
  console.log('NATIVE 2002 DICE IMG BUTTONS + LIVE CHAT SCROLL PASS',
   JSON.stringify({original,buttons,controls,scroll:current.scrollTop}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE 2002 SOURCE UI FAILED',e.stack||e);process.exit(1)});
