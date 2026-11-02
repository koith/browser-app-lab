'use strict';
/* Regression: the authentic ChatRoom background is the only movement target.
 * In particular, genuine messenger/roster controls must not teleport a pawn.
 * A reused frame must not retain movement handlers across view changes.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__);
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('입력/순간이동 회귀검증',4,12);
  });
  await page.waitForSelector('#rooms.classic-chat-room #social-image-frame.social-interior');
  await page.waitForSelector('.social-avatar.self');
  const seat=()=>page.locator('.social-avatar.self').getAttribute('data-seat');
  const initial=await seat();
  assert.notEqual(initial,null);
  await page.locator('#chat-log').click({position:{x:10,y:10}});
  assert.equal(await seat(),initial,'clicking the actual chat transcript must not move the avatar');
  await page.locator('#message').click();
  assert.equal(await seat(),initial,'focusing the real message field must not move the avatar');

  // Re-rendering the same source-size frame must REPLACE, not stack, its
  // movement handler. Verify the owned handler remains a single property.
  await page.evaluate(()=>{
   for(let i=0;i<4;i++)window.__LEAF_SOCIAL__.render();
   const frame=document.getElementById('social-image-frame');
   if(typeof frame.onclick!=='function')throw Error('room terrain handler missing');
  });
  assert.equal(await seat(),initial);
  await page.locator('#chat-log').click({position:{x:10,y:10}});
  assert.equal(await seat(),initial,'chat UI click after four re-renders must not teleport');

  // Two opposite terrain coordinates cannot both resolve to the same seat.
  // Dispatch directly on the real frame to isolate the terrain gesture
  // from a real native actor or furniture that could physically cover it.
  const movement=await page.evaluate(()=>{
   const frame=document.getElementById('social-image-frame');
   const actor=document.querySelector('.social-avatar.self');
   const before=actor.dataset.seat;
   const rect=frame.getBoundingClientRect();
   const hit=(x,y)=>{
    frame.dispatchEvent(new MouseEvent('click',{bubbles:true,button:0,
     clientX:rect.left+rect.width*x/100,clientY:rect.top+rect.height*y/100}));
    return actor.dataset.seat;
   };
   const first=hit(17,65);
   const second=hit(91,97);
   const transition=getComputedStyle(actor).transitionDuration;
   return {before,first,second,transition};
  });
  assert.notEqual(movement.first,movement.second,'free terrain clicks must snap to different source room seats');
  assert.ok(movement.first!==movement.before||movement.second!==movement.before,
   'clicking bare room terrain moves the genuine actor');
  assert.ok(movement.transition.split(',').every(v=>parseFloat(v)===0),
   'original room seat changes must not animate linearly');

  // The frame is reused for room lists. It must not keep a room gesture.
  await page.locator('#social-back').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view!=='room');
  assert.equal(await page.locator('#social-image-frame').evaluate(el=>el.onclick),null,
   'leaving ChatRoom clears the room-only movement handler');

  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('모바일 클릭회귀검증',4,12));
  await page.waitForSelector('.social-avatar.self');
  const mobileSeat=await seat();
  await page.locator('#message').click();
  assert.equal(await seat(),mobileSeat,'mobile input focus must not move the actor');
  assert.deepEqual(errors,[],'no browser runtime exception');
  console.log('CHATROOM_TERRAIN_INPUT_PASS '+JSON.stringify({initial,movement,mobileSeat}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHATROOM_TERRAIN_INPUT_FAILED',e.stack||e);process.exit(1)});
