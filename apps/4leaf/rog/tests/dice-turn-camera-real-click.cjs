'use strict';
/* Real mouse-driven first Dice roll: camera must return from an unrelated
 * manual pan to the actual pawn; turn owner visible in Korean to players. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_CAMERA__&&window.__LEAF_LOBBY__&&window.__ROG_TEST__);
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  await page.locator('#lobby-create').click();
  await page.locator('#map-select').selectOption('No Item');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.locator('#game:not(.hidden)').waitFor();
  assert.match(await page.locator('#dice-turn-banner').textContent(),/내 차례/);
  assert.equal(await page.locator('#dice-turn-banner').getAttribute('data-turn-owner'),'local');
  // Historical photo: player 1P starts in the left source portrait rail;
  // native IMG/eventmsgbox.png belongs at the top centre, not beneath
  // a tiny fabricated status strip. The extra cue is WEB accessibility,
  // visually anchored to the actual active player and no longer covering it.
  const cue=await page.evaluate(()=>{
   const el=document.getElementById('dice-turn-banner');
   const rail=el.closest('.battle-side-card');
   const badge=el.querySelector('.turn-cue-head');
   const e=document.getElementById('dice-native-event');
   const a=el.getBoundingClientRect(),b=rail.getBoundingClientRect(),c=e?.getBoundingClientRect();
   const overlap=c&&a.left<c.right&&a.right>c.left&&a.top<c.bottom&&a.bottom>c.top;
   return {slot:rail.dataset.slot,active:rail.classList.contains('active'),
    fontSize:parseFloat(getComputedStyle(badge).fontSize),
    top:a.top,left:a.left,railRight:b.right,eventOverlap:!!overlap,
    role:el.getAttribute('aria-label')};
  });
  assert.equal(cue.slot,'1','turn indicator must belong to the actual first player');
  assert.ok(cue.active,'current player source portrait must be selected');
  assert.ok(cue.fontSize>=15,'current player status must be readable, not a 10px corner label');
  assert.ok(cue.left>=cue.railRight,'WEB label must sit next to, not over, source portrait');
  assert.equal(cue.eventOverlap,false,'native IMG/eventmsgbox art must remain unobstructed');
  assert.match(cue.role,/내 차례/);
  const before=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),c=window.__LEAF_CAMERA__;
   c.panBy(100000,100000);
   return {position:m.players[0].position,active:m.active,view:c.getState().visible};
  });
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>{
   const m=window.__ROG_TEST__?.getMatch();
   return m?.players?.[0]?.position>0||m?.active!==0||m?.finished;
  },null,{timeout:45000});
  const after=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),v=window.__LEAF_CAMERA__.getState().visible;
   const pawn=m.players[0],path=window.__LEAF_CAMERA__.getState().path;
   const point=path?.[pawn.position];
   return {position:pawn.position,active:m.active,view:v,point,
    banner:document.getElementById('dice-turn-banner')?.textContent};
  });
  assert.ok(after.position>0,'the actual source pawn moved after the native roll');
  assert.ok(after.point&&after.view,'source camera has a visible window and real pawn');
  const x=after.point.x/100,y=after.point.y/100,v=after.view;
  assert.ok(x>=v.x-.025&&x<=v.x+v.width+.025&&y>=v.y-.025&&y<=v.y+v.height+.025,
   'moved pawn must remain within the actual camera viewport '+JSON.stringify(after));
  // No simulated turn changes: watch for actual dice-game advancement to AI.
  await page.waitForFunction(()=>{
   const m=window.__ROG_TEST__?.getMatch();
   return m?.players?.[m.active]?.bot===true||m?.finished;
  },null,{timeout:45000});
  if(!(await page.evaluate(()=>window.__ROG_TEST__.getMatch().finished))){
   assert.match(await page.locator('#dice-turn-banner').textContent(),/상대 AI 차례/);
   assert.equal(await page.locator('#dice-turn-banner').getAttribute('data-turn-owner'),'opponent');
   const opponent=await page.evaluate(()=>{
    const el=document.getElementById('dice-turn-banner');
    const card=el.closest('.battle-side-card');
    return {slot:card?.dataset.slot,side:card?.parentElement?.className,
     headline:el.querySelector('.turn-cue-head')?.textContent};
   });
   assert.equal(opponent.slot,'2','actual AI turn must move the cue to source 2P portrait');
   assert.match(opponent.side,/right/,'source 2P panel is on the right');
   assert.match(opponent.headline,/상대 AI 차례/);
  }
  // The 2002 source layout is desktop-only; on a phone, do not solve a
  // readability problem by covering the actual 244x52 original event art.
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>{
   const el=document.getElementById('dice-turn-banner');
   const msg=document.getElementById('dice-native-event');
   const a=el.getBoundingClientRect(),b=msg?.getBoundingClientRect();
   const overlap=b&&a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
   const header=el.querySelector('.turn-cue-head');
   const board=document.getElementById('board-area').getBoundingClientRect();
   return {overlap:!!overlap,fontSize:parseFloat(getComputedStyle(header).fontSize),
    visible:a.width>0&&a.height>0&&a.left>=board.left&&a.right<=board.right,
    slot:el.closest('.battle-side-card')?.dataset.slot,rect:[a.x,a.y,a.width,a.height],
    event:b?[b.x,b.y,b.width,b.height]:null};
  });
  assert.ok(mobile.visible,'phone turn cue must remain visible inside the game viewport '+JSON.stringify(mobile));
  assert.ok(mobile.fontSize>=15,'phone title must not shrink to the old unreadable 10px');
  assert.equal(mobile.overlap,false,'do not obscure native event message on a 390px phone '+JSON.stringify(mobile));
  assert.equal(mobile.slot,'2','phone cue must track the actual active player');
  assert.deepEqual(errors,[]);
  console.log('4LEAF_REAL_DICE_TURN_CAMERA_PASS',JSON.stringify({
   panBefore:before.view,rollMove:after.position,actualPawnVisible:true,
   owner:await page.locator('#dice-turn-banner').getAttribute('data-turn-owner')
  }));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error('4LEAF_REAL_DICE_TURN_CAMERA_FAIL',e.stack||e);process.exitCode=1});
