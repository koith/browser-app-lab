'use strict';
/* Broken original CHR body sprite must never downgrade to another card's
 * OBS body. Recover the SAME member after network restores without turn edits. */
const assert=require('node:assert/strict'),{chromium,webkit}=require('playwright');
const path=require('node:path');
(async()=>{
 const webkitEnabled=process.env.FOURLEAF_BROWSER==='webkit';
 const browser=await (webkitEnabled?webkit:chromium).launch({headless:true,
  ...(webkitEnabled?{}:{args:['--no-sandbox']})});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const blocked=/\/original\/OBS\/action-full\/1043-\d+\.png(?:\?|$)/;
 let denied=0;await page.route(blocked,route=>{denied++;return route.abort('failed');});
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&
   window.__LEAF_GENESIS_ACTORS__?.recoverAvailableOriginals);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const start=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team=['c_0060'];window.__ROG_TEST__.setMatch(m);
   return {id:m.players[0].id,active:m.active,position:m.players[0].position};
  });
  // Existing image retry path may retry 3 times. Once exhausted, preserve
  // CardData's genuine portrait, not member 1043 from an unrelated CHR card.
  await page.waitForFunction(id=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   return p?.dataset.obsUnavailable==='true'&&
    p?.dataset.actorRig==='original-card-portrait-fallback';
  },start.id,{timeout:18000});
  const after=await page.evaluate(id=>{
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const m=window.__ROG_TEST__.getMatch();
   return {card:pawn.dataset.chessmanId,rig:pawn.dataset.actorRig,
    portrait:pawn.querySelector('.leaf-chess-original-card-fallback')?.getAttribute('src'),
    actorImage:pawn.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
    active:m.active,position:m.players[0].position};
  },start.id);
  assert.ok(denied>=1,'exercise real failed 1043 asset download');
  assert.equal(after.card,'0060');assert.equal(after.rig,'original-card-portrait-fallback');
  assert.ok((after.portrait?.startsWith('./original/CardData/')||
    after.portrait==='./original/IMG/avatarback.png'));
  assert.deepEqual({active:after.active,position:after.position},
   {active:start.active,position:start.position});
  await page.unroute(blocked);
  await page.evaluate(()=>window.__LEAF_GENESIS_ACTORS__.recoverAvailableOriginals());
  await page.waitForFunction(id=>{
   const p=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
   const img=p?.querySelector('img.leaf-chess-original-obs:not([hidden])');
   return p?.dataset.actorRig==='original-obs-sprite'&&
    p.dataset.actorSource?.includes('1043.obs')&&img?.complete&&
    img.naturalWidth>15&&img.getAttribute('src')?.includes('/original/OBS/action-full/1043-');
  },start.id,{timeout:18000});
  const recovered=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {active:m.active,position:m.players[0].position,team:m.players[0].team.slice()};
  });
  assert.deepEqual(recovered,{active:start.active,position:start.position,team:['c_0060']});
  assert.deepEqual(errors,[],'original OBS retry/fallback cannot crash app');
  console.log('CHR AUTHENTIC OBS FAILED SOURCE PORTRAIT FALLBACK AND RECOVERY PASS',
   JSON.stringify({denied,card:after.card,member:'1043',sameGameState:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR SOURCE RECOVERY FAILED',e.stack||e);process.exit(1)});
