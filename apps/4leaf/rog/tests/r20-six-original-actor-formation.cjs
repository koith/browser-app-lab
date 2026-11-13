'use strict';
/* ACT-04: real six-person native DMP cell formation. Only source-original
 * 2D OBS actor pixels, foot/contact and web painter order are accepted;
 * original 2004 EXE 3D body pivots / true mesh shadows remain UNVERIFIED. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&window.__LEAF_CHR_BODY_MAP__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('5');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const IDs=['0040','0042','0045','0056','0078','0096'];
  await page.evaluate(ids=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   if(m.players.length!==6)throw Error('real six-player source engine requested');
   m.players.forEach((p,i)=>{p.team=['c_'+ids[i]];p.position=1;});
   T.setMatch(m);T.drawGame();
  },IDs);
  await page.waitForFunction(ids=>{
   const pawns=[...document.querySelectorAll('#board-pawns .board-pawn')];
   return pawns.length===6&&pawns.every(p=>
     p.dataset.actorRig==='original-obs-sprite'&&
     p.querySelector('img.leaf-chess-original-obs')?.complete&&
     p.querySelector('img.leaf-chess-original-obs')?.naturalWidth>0&&
     ids.includes(p.dataset.chessmanId));
  },IDs,{timeout:20000});
  const state=await page.evaluate(()=>{
   const sourceTile=document.querySelector('#board-nodes>.tile[data-tile="1"]');
   const z=Number(sourceTile.style.zIndex);
   const actors=[...document.querySelectorAll('#board-pawns .board-pawn')];
   return {players:window.__ROG_TEST__.getMatch().players.length,
    tileSource:sourceTile.dataset.originalArt,tileSourceSize:sourceTile.dataset.nativeTisSize,
    tileZ:z,actors:actors.map(p=>{
     const img=p.querySelector('img.leaf-chess-original-obs');
     const r=p.getBoundingClientRect(),br=img.getBoundingClientRect();
     return {id:p.dataset.chessmanId,frame:p.dataset.actorFrame,
      original:p.dataset.actorSource,rig:p.dataset.actorRig,
      z:Number(getComputedStyle(p).zIndex),row:Number(p.dataset.formationRow),
      footprint:Number(p.dataset.sourceContactWidth),
      imageSource:img.getAttribute('src'),image:[img.naturalWidth,img.naturalHeight],
      bottomGap:Number((br.bottom-r.bottom).toFixed(2))};
    })};
  });
  assert.equal(state.players,6);
  assert.equal(state.tileSourceSize,'145x97');
  assert.equal(state.actors.length,6);
  assert.equal(new Set(state.actors.map(x=>x.id)).size,6);
  assert.ok(state.actors.every(x=>x.rig==='original-obs-sprite'&&
   x.original?.startsWith('Original-CHR-body/')&&x.imageSource?.startsWith('./original/OBS/')&&
   x.image.every(v=>v>0)&&Number.isFinite(x.footprint)&&x.footprint>=18&&x.footprint<=84),
   'each genuine source actor must have its own source body and real proportional contact');
  assert.ok(state.actors.every(x=>x.z>state.tileZ&&x.z<=state.tileZ+8));
  assert.ok(new Set(state.actors.map(x=>x.row)).size>=2,'shared source cell forms real front and rear rows');
  for(let i=0;i<state.actors.length;i++)for(let j=i+1;j<state.actors.length;j++){
   const a=state.actors[i],b=state.actors[j];
   if(a.row===b.row)continue;
   assert.ok(a.row<b.row?a.z>b.z:a.z<b.z,'rear source figures must paint behind front figures');
  }
  await page.screenshot({path:'leaf-r20-original-six-player-source-formation.png'});
  assert.deepEqual(errors,[]);
  console.log('R20_SIX_ORIGINAL_OBS_ACTOR_FORMATION_PASS',JSON.stringify({actors:state.actors.map(({id,z,row,imageSource,footprint})=>({id,z,row,imageSource,footprint})),legacy3D:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R20_SIX_OBS_ACTOR_FORMATION_FAIL',e.stack||e);process.exit(1)});
