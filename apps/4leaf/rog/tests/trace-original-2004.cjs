'use strict';
/* Screenshot-to-live-DOM pixel tracing, NOT a visual redesign or fake static UI.
 * Reference originals:
 *   assets/board.jpg + battle.jpg: 800x600 2002-04 Dice combat.
 *   assets/chat_ref.jpg: 794x528 2004 ChatRoom.
 * Screenshots are only diagnostic art; game keeps real roll, actors, chat.
 * Battle/reference and a fresh first turn have DIFFERENT dynamic game states.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../../assets');
function source(name){return fs.readFileSync(path.join(root,name));}
function absNear(actual,target,span,label){assert.ok(Number.isFinite(actual)&&Math.abs(actual-target)<=span,
  label+': expected '+target+' ±'+span+' original pixels, got '+actual);}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__&&window.__LEAF_LOBBY__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.locator('#game:not(.hidden)').waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile').length>=100);
  const geometry=await page.evaluate(()=>{
   const app=document.querySelector('#app').getBoundingClientRect();
   function rect(sel){const el=document.querySelector(sel);if(!el)return null;
    const a=el.getBoundingClientRect();return {x:+(a.x-app.x).toFixed(2),y:+(a.y-app.y).toFixed(2),
     w:+a.width.toFixed(2),h:+a.height.toFixed(2),right:+(a.right-app.x).toFixed(2),bottom:+(a.bottom-app.y).toFixed(2)};}
   return {app:{w:app.width,h:app.height},top:rect('#game .scene-banner'),
    board:rect('#board-area'),left:rect('#game .battle-team-side.left'),
    right:rect('#game .battle-team-side.right'),mini:rect('.dice-native-minidock'),
    chat:rect('.messenger'),chessmen:rect('.sidebar'),event:rect('#dice-native-event'),
    roll:rect('#dice-source-roll'),turn:rect('#dice-turn-banner')};
  });
  absNear(geometry.app.w,800,2,'original Dice width');
  absNear(geometry.app.h,600,2,'original Dice height');
  const targets=[
   ['top','x',96,2],['top','y',0,2],['top','w',608,2],['top','h',30,2],
   ['board','y',30,2],['board','h',418,3],['board','w',800,2],
   ['left','x',0,2],['left','w',96,2],
   ['right','x',704,2],['right','w',96,2],
   ['mini','x',0,2],['mini','y',448,2],['mini','w',172,2],['mini','h',152,2],
   ['chat','x',172,2],['chat','y',448,2],['chat','w',406,2],['chat','h',152,2],
   ['chessmen','x',578,2],['chessmen','y',448,2],['chessmen','w',222,2],['chessmen','h',152,2],
   // Event panel is genuine IMG/eventmsgbox.png; on the WEB board it sits\n   // 37px below the original 30px menu => ABSOLUTE y67, not y37. This\n   // is WEB placement; historical native y is not proven by a battle still.\n   ['event','x',278,3],['event','y',67,3],['event','w',244,2],['event','h',52,2]
  ];
  const measured=targets.map(([id,key,expected,slack])=>({id,key,expected,actual:geometry[id]?.[key],delta:(geometry[id]?.[key]??0)-expected,slack}));
  console.log('DICE-ORIGINAL-800X600-RECTS '+JSON.stringify(geometry));
  console.log('DICE-ORIGINAL-800X600-ANCHORS '+JSON.stringify(measured));
  for(const t of measured)absNear(t.actual,t.expected,t.slack,t.id+'.'+t.key);
  assert.ok(geometry.turn&&geometry.turn.w>=110,'readable real turn cue is still present');
  const currentDice=await page.locator('#app').screenshot({type:'jpeg',quality:58});
  await makeOverlay('dice',source('board.jpg'),currentDice);
  // The native ROLL control MUST remain inside reference centre x365..435 and y389..439.
  // Its source sprite is 69..91x51; compare centre, not the transparent image cell.
  absNear(geometry.roll.x+geometry.roll.w/2,400,12,'original ROLL horizontal center');
  absNear(geometry.roll.y+geometry.roll.h/2,414,15,'original ROLL vertical center');
  // Actual click: original DMP match must still advance.
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.players[0].position>0,null,{timeout:30000});
  assert.ok((await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position))>before);
  // Native reference board.jpg/battle.jpg depicts a duel, not a fresh roll.
  // Inspect the actual live combat state separately: no WEB-only speech
  // bubble or event tray may cover the genuine BATTLE and VS source art.
  await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].position=5;m.players[1].position=5;
   T.setMatch(m);
   T.resolveBattle(m.players[0],m.players[1]).catch(e=>console.error('source trace battle',e));
  });
  await page.waitForSelector('#battle-visual',{timeout:12000});
  const battleOverlays=await page.evaluate(()=>({
   battle:!!document.querySelector('#battle-visual'),
   eventVisibility:getComputedStyle(document.querySelector('#dice-native-event')).visibility,
   turnVisibility:getComputedStyle(document.querySelector('#dice-turn-banner')).visibility,
   sourcePodiums:document.querySelectorAll('#battle-visual .leaf-native-winbattle-podiums').length
  }));
  console.log('BATTLE-2004-SOURCE-OVERLAY '+JSON.stringify(battleOverlays));
  assert.equal(battleOverlays.eventVisibility,'hidden','original battle heading must not be covered by event tray');
  assert.equal(battleOverlays.turnVisibility,'hidden','native battle score cannot be covered by WEB turn bubble');
  await makeOverlay('battle',source('battle.jpg'),await page.locator('#app').screenshot({type:'jpeg',quality:58}));
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('Source-trace room 2004',4,12);
  });
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden)');
  const chat=await page.evaluate(()=>{
   const stage=document.querySelector('#social-image-frame');
   const origin=stage.getBoundingClientRect();
   const rect=s=>{const e=document.querySelector(s);const a=e?.getBoundingClientRect();
    return a?{x:+(a.x-origin.x).toFixed(2),y:+(a.y-origin.y).toFixed(2),w:a.width,h:a.height}:null;};
   return {frame:rect('#social-image-frame'),log:rect('#rooms .messenger[data-native-overlay="true"]'),
    users:rect('#rooms .social-user-panel[data-native-overlay="true"]'),
    exit:rect('#social-back[data-in-original-room="true"]')};
  });
  console.log('CHAT-ORIGINAL-794X528-RECTS '+JSON.stringify(chat));
  absNear(chat.frame.w,794,2,'original 2004 ChatRoom frame width');
  absNear(chat.frame.h,528,2,'original 2004 ChatRoom frame height');
  absNear(chat.log.x,18,1,'chat log original x18');
  absNear(chat.log.y,0,1,'chat log original y0');
  absNear(chat.log.w,407,2,'chat original 407px message panel');
  absNear(chat.log.h,118,2,'chat original 118px message panel');
  absNear(chat.users.x,621,1,'participant list original x621');
  absNear(chat.users.y,10,1,'participant list original y10');
  absNear(chat.users.h,128,2,'participant list original height');
  absNear(chat.exit.x,728,2,'original EXIT hotspot x728');
  absNear(chat.exit.y,503,2,'original EXIT hotspot y503');
  const currentChat=await page.locator('#social-image-frame').screenshot({type:'jpeg',quality:60});
  await makeOverlay('chat',source('chat_ref.jpg'),currentChat);
  assert.deepEqual(errors,[]);
  console.log('ORIGINAL_2004_SCREEN_TRACING_REAL_BROWSER_PASS');
 }finally{await browser.close();}
 async function makeOverlay(id,original,current){
  const p=await browser.newPage({viewport:{width:1750,height:660},deviceScaleFactor:1});
  const mime='image/jpeg';const ref='data:'+mime+';base64,'+original.toString('base64');
  const live='data:'+mime+';base64,'+current.toString('base64');
  await p.setContent('<style>body{background:#182042;color:#fff;font:12px sans-serif}.pair{display:flex;gap:8px}.pair img{display:block;image-rendering:auto}</style><div class="pair"><section>ORIGINAL REFERENCE<br><img id="src" src="'+ref+'"></section><section>LIVE DOM<br><img id="live" src="'+live+'"></section></div>');
  await p.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));
  await p.screenshot({path:'4leaf-trace-'+id+'-source-vs-web.png',fullPage:true});
  const overlays=await p.evaluate(()=>{
   const refs=[document.querySelector('#src'),document.querySelector('#live')];
   const width=refs[0].naturalWidth,height=refs[0].naturalHeight;
   const c=document.createElement('canvas');c.width=width;c.height=height;const x=c.getContext('2d');
   x.globalAlpha=1;x.drawImage(refs[0],0,0);x.globalAlpha=.5;x.drawImage(refs[1],0,0);
   return c.toDataURL('image/png').split(',')[1];
  });
  fs.writeFileSync('4leaf-trace-'+id+'-50pct-overlay.png',Buffer.from(overlays,'base64'));
  // log JPEG of current actual browser for visual inspection; never use screenshot as UI layer.
  console.log('FOURLEAF_TRACE_JPEG_'+id.toUpperCase()+'='+current.toString('base64'));
  await p.close();
 }
})().catch(e=>{console.error('ORIGINAL_2004_SCREEN_TRACING_FAILED',e.stack||e);process.exit(1);});
