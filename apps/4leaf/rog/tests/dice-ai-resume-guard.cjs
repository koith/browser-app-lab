'use strict';
/* Protect old saved AI games from involuntary autoplay on reload, while
   preserving explicit opt-in AI versus default human hotseat semantics.
   The original binary AI protocol is NOT claimed restored here. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  const url=process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html');
  await page.goto(url);
  await page.waitForFunction(()=>window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  assert.equal(await page.locator('#game-mode').inputValue(),'hotseat',
   'fresh game is MANUAL by default; do not choose computer players silently');
  await page.locator('#game-mode').selectOption('ai');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const created=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {mode:m.mode,autoplay:m.botAutoplay,bots:m.players.map(p=>p.bot)};
  });
  assert.deepEqual(created,{mode:'ai',autoplay:true,bots:[false,true]},
   'AI auto-roll only enabled when a player explicitly selects computer mode');
  assert.equal(await page.locator('#dice-ai-autoplay-toggle').isVisible(),true,
   'AI control must be visibly available during real AI matches');
  assert.equal(await page.locator('#dice-ai-autoplay-toggle').getAttribute('aria-pressed'),'true');
  // Persist a preexisting old AI game at an opponent's turn. The previous
  // client would resume and auto-roll uncontrollably without any consent.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.active=1;
   m.players[1].position=0;
   localStorage.setItem('rog_match',JSON.stringify(m));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  assert.ok(await page.locator('#resume-game').isVisible(),
   'real persisted unfinished AI match remains resumable');
  await page.locator('#resume-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const restored=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {mode:m.mode,active:m.active,autoplay:m.botAutoplay,
    positions:m.players.map(p=>p.position),enabled:!document.getElementById('roll-btn').disabled};
  });
  assert.deepEqual(restored,{mode:'ai',active:1,autoplay:false,positions:[0,0],enabled:true},
   'restored AI opponent is PAUSED and its dice can be rolled by the player');
  assert.equal(await page.locator('#dice-ai-autoplay-toggle').getAttribute('aria-pressed'),'false');
  assert.ok((await page.locator('#dice-ai-autoplay-toggle').textContent()).includes('일시정지'),
   'old automatic game is clearly labeled paused, not silently replayed');
  await page.waitForTimeout(1350);
  const still=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();return [m.active,m.players[1].position];
  });
  assert.deepEqual(still,[1,0],'no hidden timeout automatically rolls saved opponent dice');
  const manualLabel=await page.locator('#roll-btn').getAttribute('aria-label');
  assert.ok(manualLabel.includes('직접 굴리기'),'active bot seat is now explicitly a manual user action');
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().active===0&&
   !document.getElementById('roll-btn').disabled,null,{timeout:30000});
  const manuallyAdvanced=await page.evaluate(()=>({
   bot:window.__ROG_TEST__.getMatch().players[1].position,
   autoplay:window.__ROG_TEST__.getMatch().botAutoplay,
   turn:window.__ROG_TEST__.getMatch().active
  }));
  assert.ok(manuallyAdvanced.bot>0,'one real click rolls and moves exactly one manually controlled opponent');
  assert.equal(manuallyAdvanced.autoplay,false);
  await page.waitForTimeout(1100);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch().active),0,
   'after manual opponent move, bot autoplay does not restart behind the scenes');

  // Enabling computer turns requires a NEW conscious click of the UI.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.active=1;m.players[1].position=0;
   window.__ROG_TEST__.drawGame();
  });
  await page.locator('#dice-ai-autoplay-toggle').click();
  assert.equal(await page.locator('#dice-ai-autoplay-toggle').getAttribute('aria-pressed'),'true');
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[1].position>0,
   null,{timeout:22000});
  const automated=await page.evaluate(()=>({
   p:window.__ROG_TEST__.getMatch().players[1].position,
   source:document.querySelector('#board-nodes .tile')?.dataset.originalArt,
   tileTransform:getComputedStyle(document.querySelector('#board-nodes .tile')).transform,
   pawnTransform:getComputedStyle(document.querySelector('#board-pawns .board-pawn')).transform
  }));
  assert.ok(automated.source,'original source TIS art remains intact during AI turn');
  assert.ok(automated.tileTransform.startsWith('matrix(1, 0, 0, -1,'),
   'the corrected hex platform orientation is stable during actual manual and auto turns');
  assert.ok(!automated.pawnTransform.startsWith('matrix(1, 0, 0, -1,'),
   'actor models are NOT upside down');
  await page.setViewportSize({width:390,height:844});
  assert.ok((await page.locator('#dice-ai-autoplay-toggle').boundingBox()).width>100,
   'pause control stays visible and touch-clickable on mobile');
  await page.locator('#dice-ai-autoplay-toggle').click();
  assert.equal(await page.locator('#dice-ai-autoplay-toggle').getAttribute('aria-pressed'),'false');
  await page.screenshot({path:'leaf-dice-explicit-ai-pause-and-source-orientation.png'});
  assert.deepEqual(errors,[],'source game and saved manual turn guard produce no page errors');
  console.log('GENESIS PERSISTED AI PAUSE / EXPLICIT AUTOPLAY PASS',
   JSON.stringify({created,restored,manuallyAdvanced,automated}));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS SAVED AI AUTOPLAY GUARD FAILED',e.stack||e);process.exit(1)});
