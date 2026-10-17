'use strict';
/* Actual native OBS chessmen on one authoritative DMP cell must remain
 * individually visible. The visual separation is explicitly inferred:
 * do not change real source positions, turn order, tile height or painting.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_OBS_FRAMES);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].position=0;m.players[1].position=0;
   m.players[0].team[0]='c_0045';m.players[1].team[0]='c_0042';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#board-pawns .leaf-chess-original-obs')]
   .length===2);
  const together=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   actors:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>{
    const b=p.getBoundingClientRect(),art=p.querySelector('.leaf-chess-original-obs');
    return {position:p.dataset.position,slot:Number(p.dataset.cellPeerSlot),
     peers:Number(p.dataset.cellPeerCount),source:p.dataset.actorSource,
     type:p.dataset.actorRig,formation:p.dataset.formationSource,
     x:b.x+b.width/2,y:b.y+b.height/2,
     inlineLeft:p.style.left,inlineTop:p.style.top,
     width:b.width,native:art?.getAttribute('src')};
   })
  }));
  assert.deepEqual(together.match,[0,0],'logical source DMP positions unchanged');
  assert.deepEqual(together.actors.map(x=>x.slot),[0,1]);
  assert.ok(together.actors.every(x=>x.peers===2&&x.type==='original-obs-sprite'));
  assert.ok(together.actors.every(x=>x.native?.includes('./original/OBS/')));
  assert.ok(together.actors.every(x=>x.inlineLeft.startsWith('calc(')),
   'source world anchoring needs valid CSS, not dropped calc(+ -offset)');
  const horizontal=Math.abs(together.actors[0].x-together.actors[1].x);
  assert.ok(horizontal>=25&&horizontal<=40,
   'two native character sprites must be separate within a single hex platform: '+horizontal);
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[1].position=10;
   window.__ROG_TEST__.drawGame();
  });
  const apart=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch().players.map(p=>p.position),
   actors:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    peers:Number(p.dataset.cellPeerCount),slot:Number(p.dataset.cellPeerSlot),
    native:p.dataset.actorRig,
    left:p.style.left,top:p.style.top
   })),
   tiles:document.querySelectorAll('#board-nodes .tile').length
  }));
  assert.deepEqual(apart.match,[0,10],'engine position data must be authoritative');
  assert.equal(apart.tiles,104,'real original map remains rendered');
  assert.ok(apart.actors.every(x=>x.peers===1&&x.slot===0&&
    x.left.includes('+ 0px')&&x.top.includes('+ 0px')),
    'separate cells return each actual pawn to its own DMP center');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-source-two-obs-chessmen-one-platform.png'});
  console.log('REAL OBS CO-OCCUPANCY DMP PASS',
   JSON.stringify({together,apart,horizontal}));
 }finally{await browser.close()}
})().catch(error=>{console.error('REAL OBS DMP CO-OCCUPANCY FAILED',
 error.stack||error);process.exit(1)});
