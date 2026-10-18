'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1100,height:860},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  assert.equal(await page.locator('#game-mode').inputValue(),'hotseat',
   'manual, not AI auto-turn, is the default gameplay mode');
  assert.equal(await page.locator('#bot-count').inputValue(),'1',
   'default has exactly one additional human slot');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const initial=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch(),tiles=[...document.querySelectorAll('#board-nodes .tile')];
   const t=tiles[0],style=getComputedStyle(t),pawn=document.querySelector('#board-pawns .board-pawn');
   return {mode:match.mode,bots:match.players.map(p=>p.bot),active:match.active,
    art:t.dataset.originalArt,transform:style.transform,
    dimensions:[t.offsetWidth,t.offsetHeight],count:tiles.length,
    pawnTransform:pawn&&getComputedStyle(pawn).transform,
    worldTransform:getComputedStyle(document.querySelector('#board-world')).transform};
  });
  assert.equal(initial.mode,'hotseat');
  assert.deepEqual(initial.bots,[false,false],'both participants manually control their own turns');
  assert.equal(initial.count,104,'source DMP 4LEAF board still has 104 actual tiles');
  assert.deepEqual(initial.dimensions,[145,97],'native TIS source geometry unchanged');
  assert.ok(initial.art,'every upright tile still uses actual original TIS art');
  assert.ok(initial.transform.startsWith('matrix(1, 0, 0, -1,'),
   'source decoded TIS upside-down scanline is corrected while pixels stay original');
  assert.ok(!initial.pawnTransform?.startsWith('matrix(1, 0, 0, -1,'),
   'source CardData chessmen remain upright');
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.active===1&&
   !document.querySelector('#roll-btn')?.disabled,null,{timeout:30000});
  const after=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch(),
   tileTransform:getComputedStyle(document.querySelector('#board-nodes .tile')).transform,
   visible:!!document.querySelector('#board-nodes .tile')
  }));
  assert.equal(after.match.active,1,'single roll advances only one human turn');
  assert.ok(after.match.players[0].position>0,'one manual roll actually moves the human');
  const p2=after.match.players[1].position;
  await page.waitForTimeout(1600);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[1].position),p2,
   'the other human does not auto-roll after a short delay');
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch().active),1,
   'turn remains at second player until their own click');
  // Source DMP may place the second roll on a battle/keeper/ability cell.
  // That decision is intentionally MANUAL, so it is incorrect to require
  // the next turn to begin without the human resolving the authentic event.
  // Assert the second dice input is recorded and actually begins movement.
  const beforeSecond=await page.evaluate(()=>window.__ROG_TEST__.getMatch().history.length);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(({p2,beforeSecond})=>{
   const m=window.__ROG_TEST__.getMatch();
   return m.history.slice(beforeSecond).some(line=>
    line.includes(m.players[1].name+' 이동 주사위')||
    line.includes(m.players[1].name+' 감옥'));
  },{p2,beforeSecond},{timeout:30000});
  const second=await page.evaluate(()=>({
   match:window.__ROG_TEST__.getMatch(),
   choice:!document.querySelector('#modal').classList.contains('hidden')
  }));
  assert.ok(second.match.history.slice(beforeSecond).some(line=>
    line.includes(second.match.players[1].name+' 이동 주사위')||
    line.includes(second.match.players[1].name+' 감옥')),
   'second person acts only after clicking their own dice; forced warps and battles may reset a pawn before the test checks its final location');
  assert.equal(second.match.mode,'hotseat','second turn remains in real manual hotseat mode');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('#board-nodes .tile').first().evaluate(e=>getComputedStyle(e).transform.startsWith('matrix(1, 0, 0, -1,')),true,
   'hex platform orientation stays correct on phone');
  assert.deepEqual(errors,[],'no browser runtime errors');
  console.log('GENESIS HEX ORIENTATION + MANUAL TURNS PASS',JSON.stringify({initial,afterTurn:after.match.active}));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS HEX ORIENTATION + MANUAL TURNS FAILED',e.stack||e);process.exit(1)});
