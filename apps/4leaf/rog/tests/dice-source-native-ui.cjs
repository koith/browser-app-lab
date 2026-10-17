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
  await page.evaluate(()=>{
   const log=document.getElementById('chat-log');
   for(let i=0;i<44;i++){
    const line=document.createElement('div');
    line.textContent='Browser fixture line '+i;
    log.append(line);
   }
   log.scrollTop=0;
  });
  await page.waitForFunction(()=>!document.querySelector('.leaf-dice-chat-scroll[data-direction="down"]').disabled);
  assert.equal(await up.isDisabled(),true,'at actual beginning of real chat history up is disabled');
  await down.click();
  const current=await page.evaluate(()=>window.__LEAF_NATIVE_DICE_CHAT_SCROLL__.getState());
  assert.ok(current.scrollTop>0,'clicking archive button actually scrolls shared game chat');
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
