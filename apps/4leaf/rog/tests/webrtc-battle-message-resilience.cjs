'use strict';
/* Real Chromium WebRTC channel acceptance, not a mocked transport.
 * A legitimate peer may send a battle-request packet; malformed peer
 * payloads must not throw or replace the guest's visible dialog.
 * Opening a new offer must discard the old host broadcast callback.
 */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const BASE=process.env.FOURLEAF_SMOKE_URL||'http://127.0.0.1:8765/';

test('real WebRTC rejects malformed battle packets and clears old host callbacks',async t=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 t.after(()=>browser.close());
 const host=await browser.newPage({serviceWorkers:'block',viewport:{width:1280,height:900}});
 const guest=await browser.newPage({serviceWorkers:'block',viewport:{width:1280,height:900}});
 const pageErrors=[];
 for(const [name,page] of [['host',host],['guest',guest]]){
  page.on('pageerror',e=>pageErrors.push(name+': '+String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(BASE);
  await page.waitForFunction(()=>!!window.__LEAF_NET__&&!!window.__LEAF_BRIDGE__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('network');
  await page.locator('#net-panel:not(.hidden)').waitFor({timeout:5000});
 }
 await host.locator('#net-make').click();
 await host.waitForFunction(()=>document.querySelector('#net-output-offer')?.value.length>20,null,{timeout:25000});
 const offer=await host.locator('#net-output-offer').inputValue();
 await guest.locator('#net-input-offer').fill(offer);
 await guest.locator('#net-accept-offer').click();
 await guest.waitForFunction(()=>document.querySelector('#net-output-answer')?.value.length>20,null,{timeout:25000});
 const answer=await guest.locator('#net-output-answer').inputValue();
 await host.locator('#net-input-answer').fill(answer);
 await host.locator('#net-apply-answer').click();
 await Promise.all([host,guest].map(page=>page.waitForFunction(
  ()=>window.__LEAF_NET__.connected===true,null,{timeout:25000})));
 await host.waitForFunction(()=>window.__LEAF_NET__.guestName!==null&&
  typeof window.__LEAF_BRIDGE__.onState==='function',null,{timeout:10000});
 const valid={type:'battle-request',bid:8,attacker:'호스트',defender:'게스트',
  attack:11,defense:10,diceAttack:[5,6],diceDefense:[4,6],
  options:['결과 확인','자폭']};
 const invalid=[
  {...valid,diceAttack:'5,6'},
  {...valid,diceDefense:{join:'not-an-array'}},
  {...valid,options:'결과 확인'},
  {...valid,options:['결과 확인',{}]},
  {...valid,diceAttack:[0,7]},
  {...valid,bid:'8'},
  {...valid,options:Array.from({length:100},()=> '결과 확인')}
 ];
 const sent=await host.evaluate(packets=>{
  return packets.map(packet=>window.__LEAF_NET__.send(packet))
   .concat(window.__LEAF_NET__.send({type:'chat',who:'host',text:'BAD_PACKET_BARRIER_410'}));
 },invalid);
 assert.ok(sent.every(Boolean),'send all malformed frames and an ordered valid chat barrier');
 await guest.waitForFunction(()=>document.querySelector('#chat-log')
  ?.textContent.includes('BAD_PACKET_BARRIER_410'),null,{timeout:10000});
 assert.equal(await guest.locator('#modal:not(.hidden)').count(),0,
  'bad battle packets must never open an untrusted dialog');
 assert.deepEqual(pageErrors,[],'malformed peer data cannot throw in the browser');
 assert.equal(await host.evaluate(packet=>window.__LEAF_NET__.send(packet),valid),true);
 await guest.locator('#modal:not(.hidden)').waitFor({timeout:10000});
 assert.ok((await guest.locator('#modal-title').textContent()).includes('전투 카드 선택'),
  'authentic host battle request still displays correct dialog');
 assert.equal(await guest.locator('#modal-buttons button').count(),2);
 await guest.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
 assert.equal(await guest.locator('#modal:not(.hidden)').count(),0,
  'legitimate battle selection still closes the dialog');

 // A deliberately invalid host snapshot exercises the REAL guest receiver
 // rejecting the payload. The host must see that refusal over the same
 // ordered RTCDataChannel, not silently assume the guest is synchronized.
 assert.equal(await host.evaluate(()=>window.__LEAF_NET__.send({
  type:'state',match:{map:'4LEAF',mode:'network',players:[]}
 })),true);
 await host.waitForFunction(()=>document.querySelector('#net-status')
  ?.textContent.includes('상대 기기에서 경기 상태를 적용하지 못했습니다'),null,{timeout:10000});
 // The durable accepted-state branch is already exercised by the separate
 // actual browser guest-save test. Here stub only its return value to verify
 // the acknowledgement's transport and host display, without rewriting data.
 await guest.evaluate(()=>{window.__LEAF_BRIDGE__.receiveMatch=()=>true});
 assert.equal(await host.evaluate(()=>window.__LEAF_NET__.send({
  type:'state',match:{map:'4LEAF',mode:'network',players:[]}
 })),true);
 await host.waitForFunction(()=>document.querySelector('#net-status')
  ?.textContent.includes('상대 기기에서 전달받은 경기 상태를 저장했습니다'),null,{timeout:10000});
 assert.deepEqual(pageErrors,[],'both receipt paths must preserve real WebRTC operation');

 // A fresh host offer resets the old connection. The previous connected
 // host onState handler must not survive to any later guest/host session.
 await host.locator('#net-make').click();
 await host.waitForFunction(()=>document.querySelector('#net-output-offer')
  ?.value.length>20,null,{timeout:25000});
 const reset=await host.evaluate(()=>({
  connected:window.__LEAF_NET__.connected,
  role:window.__LEAF_NET__.role,
  guestName:window.__LEAF_NET__.guestName,
  onState:window.__LEAF_BRIDGE__.onState
 }));
 assert.equal(reset.connected,false,'new offer has no connected game authority');
 assert.equal(reset.role,'host');
 assert.equal(reset.guestName,null,'old remote guest name cannot leak to next peer');
 assert.equal(reset.onState,null,'old host state broadcast callback must be released');
 assert.deepEqual(pageErrors,[]);
});
