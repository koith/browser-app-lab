'use strict';
/* The old "make room" 4LEAF entry must invoke the actual native ChatRoom
 * ownerdialog.png create flow, never a fake local-only apology modal.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  await page.evaluate(()=>window.__ROG_TEST__.go('rooms'));
  await page.evaluate(()=>document.getElementById('make-room').click());
  await page.waitForFunction(()=>document.querySelector('#social-modal form [name="name"]'));
  assert.equal(await page.locator('#social-modal form [name="name"]').count(),1);
  assert.equal(await page.locator('#social-modal form [name="capacity"]').count(),1);
  assert.equal(await page.locator('#social-modal form [name="password"]').count(),1);
  assert.equal(await page.locator('#modal[data-native-dice-dialog]').count(),0,
   'real ChatRoom owner dialog, not Dice WEB apology popup');
  const native=await page.evaluate(()=>{
   const form=document.querySelector('#social-modal form');
   return {name:form.getAttribute('class'),atlas:document.querySelector('#social-modal')?.outerHTML.slice(0,650)};
  });
  await page.locator('#social-modal form [name="name"]').fill('원본 채팅방 생성 UX 검증');
  await page.locator('#social-modal form [name="capacity"]').selectOption('4');
  await page.locator('#social-modal form button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState()?.view==='room');
  const state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.view,'room','source dialog must create an actual playable room');
  assert.ok(state.roomId,'native room has a real identity');
  await page.screenshot({path:'leaf-original-chattown-real-create-entry.png'});
  assert.deepEqual(errors,[]);
  console.log('ORIGINAL CHATTOWN CREATE ENTRY PASS '+JSON.stringify({
   route:state.view,roomId:state.roomId,dialog:native.name}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL CHAT CREATE ENTRY FAILED',e.stack||e);process.exit(1)});
