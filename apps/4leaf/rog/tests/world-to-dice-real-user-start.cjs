'use strict';
/* PUBLIC ENTRY USER JOURNEY, not an injected __ROG_TEST__.go('lobby') bypass.
 * Mobile phone and desktop click the real WorldMap source region, 2002
 * channel numerals, room creation, native READY and one actual DMP turn. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const engine=(process.env.FOURLEAF_BROWSER||'chromium')==='webkit'?webkit:chromium;
const phone=process.env.FOURLEAF_MOBILE==='1';
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({
  viewport:phone?{width:390,height:844}:{width:1280,height:900},
  isMobile:phone,hasTouch:phone,serviceWorkers:'block'});
 const errors=[],requests=[],steps=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 page.on('console',m=>{if(m.type()==='error')errors.push('console '+m.text())});
 page.on('requestfailed',r=>requests.push({url:r.url(),error:r.failure()?.errorText}));
 const inspect=async(step)=> {
  const state=await page.evaluate(()=>{
   const lobby=document.getElementById('lobby'),channel=document.getElementById('dice-channels');
   const button=id=>{const e=document.getElementById(id),r=e?.getBoundingClientRect();
    const top=r?document.elementFromPoint(r.x+r.width/2,r.y+r.height/2):null;
    return {present:!!e,hidden:!!e?.closest('.hidden'),display:e?getComputedStyle(e).display:null,
      disabled:!!e?.disabled,box:r?{x:r.x,y:r.y,w:r.width,h:r.height}:null,
      hit:top?.id||top?.className?.toString().slice(0,100)||null,
      parentHit:top?.closest('button')?.id||null};
   };
   return {route:document.querySelector('.scene:not(.hidden)')?.id,
     where:document.getElementById('where')?.textContent,
     world:document.querySelector('.world-location[data-region="dice"]')?.getBoundingClientRect().toJSON(),
     channel:channel?.className,lobby:lobby?.className,
     create:button('lobby-create'),ready:button('start-game'),
     config:document.getElementById('dice-room-config')?.className,
     native:window.__LEAF_DICE_NATIVE__?.getState?.(),
     roomButtons:window.__LEAF_DICE_ROOM_BUTTONS__?.getState?.(),
     chState:window.__LEAF_LOBBY__?.getState?.(),
     game:document.getElementById('game')?.className,
     board:document.querySelectorAll('#board-nodes>.tile').length,
     match:window.__ROG_TEST__?.getMatch?.()?{
      map:window.__ROG_TEST__.getMatch().map,
      mode:window.__ROG_TEST__.getMatch().mode,
      players:window.__ROG_TEST__.getMatch().players.map(p=>({position:p.position,team:p.team}))
     }:null,
     modal:document.getElementById('modal')?.className.includes('hidden')?null:{
      title:document.getElementById('modal-title')?.textContent,
      content:document.getElementById('modal-content')?.textContent}
   };
  }).catch(e=>({inspectionError:String(e)}));
  steps.push({step,state});
  console.log('USER_FLOW_STEP',JSON.stringify({step,...state}));
  return state;
 };
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&
   window.__LEAF_WORLD__&&window.__LEAF_DICE_NATIVE__,null,{timeout:20000});
  await inspect('world-initial');
  // A meaningful source sprite hit is normally inside the native button,
  // not generic navigate('lobby'). Three actual taps at distinct pixels
  // reproduce touch hit masks without using hidden JS state shortcuts.
  const world=page.locator('.world-location[data-region="dice"]');
  assert.equal(await world.count(),1,'WorldMap must expose one dice region');
  const rect=await world.boundingBox();assert.ok(rect&&rect.width>10&&rect.height>10);
  for(const [x,y] of [[.5,.5],[.35,.42],[.6,.7]]){
   if(await page.locator('#dice-channels:not(.hidden)').count())break;
   await world.click({position:{x:Math.round(rect.width*x),y:Math.round(rect.height*y)}});
   await page.waitForTimeout(200);
  }
  let state=await inspect('world-dice-click');
  assert.equal(state.route,'dice-channels',
   'WorldMap dice entry must open ORIGINAL Region source channel selection');
  const select=page.locator('#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]');
  await select.click();state=await inspect('native-region-channel');
  assert.equal(state.route,'lobby','source Ispin 1 channel must enter actual room list');
  await page.locator('#lobby-create').click();state=await inspect('native-room-create');
  assert.equal(state.route,'lobby');
  assert.ok(state.config?.includes('lobby-config')&&!state.config.includes('hidden'),
   'native ROOM CREATE must reveal playable game settings and READY');
  assert.equal(state.ready.disabled,false,'game ready must not be disabled');
  assert.equal(state.ready.hidden,false,'source READY must actually be visible');
  assert.ok(state.ready.box?.w>=20&&state.ready.box.h>=15,
    'native READY must have a mobile-accessible click area');
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#point-limit').selectOption('12');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForTimeout(350);state=await inspect('ready-tap-game-start');
  assert.equal(state.route,'game',
    'original native ROOM READY must transition to playable board without hidden modal');
  assert.equal(state.board,104,'authentic 4LEAF DMP board must draw all 104 source tiles');
  assert.equal(state.match?.players.length,2);
  assert.ok(!state.modal,'no invisible blocker modal may stop a fresh play');
  const before=state.match.players[0].position;
  await page.locator('#roll-btn').click();
  await page.waitForFunction(before=>{
   const m=window.__ROG_TEST__?.getMatch?.();
   return !!m&&m.lastRoll?.length>0&&m.players[0].position!==before;
  },before,{timeout:25000});
  state=await inspect('first-authentic-dice-turn');
  assert.ok(state.match?.players[0].position>before);
  console.log('USER_REAL_WORLD_TO_DICE_START_PASS',JSON.stringify({
   engine:engine.name(),phone,map:state.match.map,board:state.board,
   turn:state.match.players[0].position,steps:steps.length,errors}));
  assert.equal(errors.length,0,'browser must have no unhandled JS exceptions');
 }catch(error){
  console.error('USER_REAL_WORLD_TO_DICE_START_FAIL',error.stack||String(error));
  console.error('USER_FLOW_DIAGNOSTIC',JSON.stringify({steps,errors,requests:requests.slice(0,20)}));
  await page.screenshot({path:'leaf-world-to-game-failure-'+engine.name()+'-'+(phone?'phone':'desktop')+'.png',
    fullPage:true}).catch(()=>{});
  throw error;
 }finally{
  fs.writeFileSync('leaf-world-to-game-'+engine.name()+'-'+(phone?'phone':'desktop')+'.json',
   JSON.stringify({steps,errors,requests},null,2));
  await browser.close();
 }
})().catch(()=>process.exit(1));
