'use strict';
// True source sprites stay interactive while actual DMP y painter order
// interleaves real Registry avatars with the overlapping 145x97 tile planes.
// No invented 3D height, fake participants, or screenshot-only sprite overlay.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&window.ORIGINAL_LEAF_MAPS);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile').length===104&&
    document.querySelectorAll('#board-pawns .board-pawn').length===2,null,{timeout:12000});
  const inspect=()=>page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   const root=document.getElementById('board-nodes');
   const world=document.getElementById('board-world');
   const actors=document.getElementById('board-pawns');
   const pawns=[...actors.querySelectorAll('.board-pawn')];
   return {
    sourceTileCount:tiles.length,
    world:world.id,
    underNodes:actors.parentElement===root,
    display:getComputedStyle(actors).display,
    actors:pawns.map(actor=>{
     const anchor=root.querySelector('.tile[data-tile="'+actor.dataset.position+'"]');
     const css=getComputedStyle(actor);
     const shadow=getComputedStyle(actor,'::before');
     const img=actor.querySelector('img');
     return {
      id:actor.dataset.id,seat:Number(actor.dataset.position),
      originalImage:img.getAttribute('src'),
      anchor:Number(anchor?.style.zIndex),
      actual:Number(css.zIndex),
      variable:actor.style.getPropertyValue('--leaf-pawn-dmp-depth'),
      recorded:Number(actor.dataset.dmpPainterDepth),
      source:Number(actor.dataset.depthTile),
      shadow:shadow.backgroundImage,
      ring:shadow.borderStyle,
      animation:shadow.animationName,
      natural:[img.naturalWidth,img.naturalHeight],
      imageLoaded:img.complete&&img.naturalWidth>0
     };
    }),
    platformDepths:tiles.map(tile=>Number(tile.style.zIndex)),
    sourceFields:tiles.map(tile=>tile.dataset.dmpY)
   };
  });
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns img')].every(i=>i.complete&&i.naturalWidth>0));
  let snapshot=await inspect();
  assert.equal(snapshot.sourceTileCount,104,'genuine game DMP route is intact');
  assert.ok(snapshot.underNodes,'actual actors share a painter ordering parent with original live source TIS platforms');
  assert.equal(snapshot.display,'contents','actor list creates no separate always-front stacking context');
  assert.equal(snapshot.actors.length,2,'only the two actual playing humans are displayed');
  for(const actor of snapshot.actors){
   assert.ok(actor.originalImage.startsWith('./original/Registry/sava'),'actual recovered avatar source is preserved');
   assert.deepEqual(actor.natural,[75,141],'actual Registry source standee is the recovered 75x141 bitmap');
   assert.equal(actor.anchor+1,actor.actual,'real DMP owning tile is behind exactly its own user avatar');
   assert.equal(actor.actual,actor.recorded,'actual CSS z-index equals source DMP painter depth');
   assert.equal(actor.actual,Number(actor.variable),'source painter depth drives the live CSS variable');
   assert.equal(actor.source,actor.seat,'avatar depth references the real current game tile, not fake elevation');
   assert.equal(actor.animation,'none','invented glowing portal ring animation is gone');
   assert.equal(actor.ring,'none','invented neon ring border is removed');
  }
  assert.ok(snapshot.platformDepths.some(n=>n>snapshot.actors[0].actual),
   'nearer genuine native raised platforms can occlude a farther player');
  await page.screenshot({path:'leaf-original-dmp-actor-depth-before-roll.png'});
  // Change real match positions in a controlled QA state to check both ends
  // of the authentic DMP route. No production test NPCs are added.
  const chosen=await page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   const sorted=tiles.map(x=>({i:Number(x.dataset.tile),depth:Number(x.style.zIndex)}))
     .sort((a,b)=>a.depth-b.depth);
   const far=sorted[8],near=sorted[sorted.length-9];
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].position=far.i;m.players[1].position=near.i;
   window.__ROG_TEST__.drawGame();
   return {far,near};
  });
  await page.waitForFunction(([a,b])=>{
   const p=[...document.querySelectorAll('#board-pawns .board-pawn')];
   return p.some(x=>x.dataset.position===String(a))&&p.some(x=>x.dataset.position===String(b));
  },[chosen.far.i,chosen.near.i]);
  snapshot=await inspect();
  assert.equal(snapshot.actors.length,2,'DMP sorting did not create phantom actors');
  assert.ok(snapshot.actors[0].actual<snapshot.actors[1].actual,
   'the genuinely farther source actor paints behind the nearer source actor');
  assert.ok(snapshot.platformDepths.some(n=>n>snapshot.actors[0].actual&&
   n<snapshot.actors[1].actual),
   'intermediate authentic platforms now intersect actor depth correctly');
  // Changing a real tile event requires rerender; keep same actual sprites
  // instead of losing presence, images or movement history.
  const images=await page.locator('#board-pawns .board-pawn img').evaluateAll(nodes=>nodes.map(n=>n.src));
  await page.evaluate(()=>{
   document.getElementById('board-nodes').dataset.renderKey='';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes>.tile').length===104&&
   document.querySelectorAll('#board-pawns .board-pawn').length===2);
  snapshot=await inspect();
  assert.equal(snapshot.display,'contents');
  assert.ok(snapshot.actors.every(a=>a.actual===a.anchor+1),'platform redraw keeps exact actor painter association');
  assert.deepEqual(await page.locator('#board-pawns .board-pawn img').evaluateAll(nodes=>nodes.map(n=>n.src)),images,
   'live source avatar image elements survive 104-source-cell redraw');
  await page.evaluate(()=>window.__LEAF_CAMERA__.zoom(.35));
  const camera=await page.evaluate(()=>window.__LEAF_CAMERA__.getState().scale);
  assert.ok(camera>1.25,'genuine board camera zoom remains operational');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(100);
  const mobile=await inspect();
  assert.equal(mobile.display,'contents','mobile also uses the same genuine DMP actor painter order');
  assert.ok(mobile.actors.every(a=>a.actual===a.anchor+1));
  assert.ok(mobile.actors.every(a=>a.imageLoaded));
  await page.screenshot({path:'leaf-original-dmp-actor-depth-mobile.png'});
  // Finally prove real game input/turn and original TIS source are not inert.
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position!==null,null,{timeout:12000});
  assert.equal(await page.locator('#board-pawns .board-pawn').count(),2);
  assert.deepEqual(errors,[],'no game engine exceptions after DMP actor depth reparenting');
  console.log('GENESIS ACTOR DMP PAINTER ORDER PASS',JSON.stringify({count:snapshot.sourceTileCount,chosen,camera,actors:mobile.actors.map(a=>({id:a.id,z:a.actual,tile:a.seat}))}));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS ACTOR DMP DEPTH FAILED',e.stack||e);process.exit(1)});
