'use strict';
/* Authentic 2002 Genesis OBS full-body frames have been recovered for some cards.
 * Never mistake the fallback CSS proxy for actual original pixels.
 * Assert NO ChatTown Registry avatar stands on the Dice board, each actor
 * corresponds to a genuine selected chessman and uses live animation states.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const initial=await page.evaluate(()=>({
   cardTeam:window.__ROG_TEST__.getMatch().players.map(p=>p.team[0].replace(/^c_/,'')),
   actors:window.__LEAF_GENESIS_ACTORS__.getState().rendered,
   sourceIds:Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}),
   portraits:[...document.querySelectorAll('#board-pawns .leaf-chess-portrait')].map(el=>({
    src:el.getAttribute('src'),ready:el.complete,dimensions:[el.naturalWidth,el.naturalHeight]})),
   heights:[...document.querySelectorAll('#board-pawns .leaf-chess-actor')].map(el=>el.getBoundingClientRect().height),
   chatAvatar:document.querySelectorAll('#board-pawns img[src*="/Registry/sava"]').length
  }));
  assert.equal(initial.actors.length,2,'only real two human chessmen appear on board');
  assert.deepEqual(initial.actors.map(x=>x.chessmanId),initial.cardTeam,
   'every source sprite identity comes from the actual participant chessman');
  assert.ok(initial.actors.every(x=>{
   const native=initial.sourceIds.includes(x.chessmanId);
   return x.pose==='idle'&&(native
    ? x.rig==='original-obs-sprite'&&x.originalRecovered==='true'
    : x.rig==='inferred-8head'&&x.originalRecovered==='false');
  }), 'each existing original OBS character must use its actual 2002 pixels; missing frames may use explicitly inferred proxy');
  assert.ok(initial.heights.every((n,i)=>
    initial.sourceIds.includes(initial.cardTeam[i])?n===0:n>=70&&n<=125),
   'native OBS artwork hides the fallback CSS skeleton; only missing characters use source-scale proxy');
  assert.equal(initial.chatAvatar,0,'ChatTown avatars are NOT used on Genesis board');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .leaf-chess-portrait')].every(x=>x.complete&&x.naturalWidth>15),null,{timeout:13000});
  assert.ok(initial.portraits.every(x=>x.src.startsWith('./original/CardData/chm_')));
  const rig=page.locator('#board-pawns .board-pawn').first();
  assert.equal(await rig.locator('.leaf-chess-head').count(),1);
  assert.equal(await rig.locator('.leaf-chess-arm').count(),2);
  assert.equal(await rig.locator('.leaf-chess-leg').count(),2);
  const original=await rig.getAttribute('data-chessman-id');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0045';
   window.__ROG_TEST__.drawGame();
  });
  assert.notEqual(await rig.getAttribute('data-chessman-id'),original,
   'changing an actual team card rerenders real actor identity instead of fixed player-index avatar');
  assert.equal(await rig.getAttribute('data-chessman-id'),'0045');
  assert.equal(await rig.getAttribute('data-actor-rig'),'original-obs-sprite',
   'original OBS pixels replace inferred CSS when the chessman asset exists');
  // Legitimate actual move sequence uses real 104-cell DMP game and calls
  // actor state transitions. Restore original card to continue real match.
  await page.evaluate(old=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_'+old;
   window.__ROG_TEST__.drawGame();
  },original);
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>{
   const x=window.__LEAF_GENESIS_ACTORS__.getState().rendered[0];
   return x?.counts?.walk>0;
  },null,{timeout:15000});
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().active===1&&
   !document.querySelector('#roll-btn').disabled,null,{timeout:23000});
  const stats=await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.getState());
  assert.ok(stats.rendered[0].counts.walk>=1,'game movement triggers articulated walking state');
  assert.ok(stats.rendered[0].counts.idle>=2,'walking returns to breathing idle');
  // Trigger the existing battlefield animation state machine using real
  // game player identifiers, not by adding imaginary NPCs to the match.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'attack',200);
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[1].id,'hurt',200);
  });
  assert.equal(await rig.getAttribute('data-actor-pose'),'attack');
  assert.equal(await page.locator('#board-pawns .board-pawn').nth(1).getAttribute('data-actor-pose'),'hurt');
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .board-pawn')].every(x=>x.dataset.actorPose==='idle'),
   null,{timeout:2000});
  await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.poseByPlayer(0,'victory',200));
  assert.equal(await rig.getAttribute('data-actor-pose'),'victory');
  const recovered=await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.getState().originalFullBodyFramesRecovered);
  assert.ok(['0042','0045','0043','0054'].every(id=>recovered.includes(id))&&
   recovered.length>=46,
   'recovered IDs include all existing 2002 OBS source characters without fabricating unrelated rig files');
  await page.screenshot({path:'leaf-genesis-source-card-proxy-not-chat-actor.png'});
  assert.deepEqual(errors,[]);
  console.log('CARD-IDENTIFIED CHESSMEN + WEB WALK ATTACK HURT VICTORY PASS',JSON.stringify(stats));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS CHESSMEN RIG FAILED',e.stack||e);process.exit(1)});
