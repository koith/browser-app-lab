'use strict';
/* Exhaustive native-DMP facing and actual live pawn direction regression.
 * Archived DMP xy is VERIFIED; translating it to 2D sprite facing is
 * explicitly WEB-INFERRED because the original EXE action table is unknown.
 */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const ENGINE=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await ENGINE.launch({headless:true,...(ENGINE===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DMP_TRAVEL__&&
    Object.keys(window.ORIGINAL_LEAF_MAPS||{}).length===26);
  const audit=await page.evaluate(()=>{
   const sources=window.ORIGINAL_LEAF_MAPS,calc=window.__LEAF_DMP_TRAVEL__.facing;
   let transitions=0,diagonal=0,longDiagonal=0,regressions=0;
   const samples=[];
   for(const [mapId,route] of Object.entries(sources)){
    for(let to=1;to<route.length;to++){
     const from=route[to-1],next=route[to],dx=next[0]-from[0],dy=next[1]-from[1];
     const expected=dy<0?'away':dy>0?'toward':dx<0?'left':dx>0?'right':'toward';
     if(calc(route,to-1,to)!==expected)throw Error('Native DMP facing mismatch '+mapId+' '+to);
     transitions++;
     if(dx&&dy){
      diagonal++;
      if(Math.abs(dx)>1||Math.abs(dy)>1){
       longDiagonal++;
       // On these jumps old WEB percent-based dx/dy ratio misclassified some
       // forward diagonals as side walk; source grid y MUST win.
       const projectedX=dx*70/2800*100,projectedY=dy*47/1551*100;
       const old=projectedY<-.5?'away':
        Math.abs(projectedX)>1&&Math.abs(projectedX)>=Math.abs(projectedY)?
        (projectedX<0?'left':'right'):'toward';
       if(old!==expected){
        regressions++;
        samples.push({mapId,from:to-1,to,expected,old,dx,dy});
       }
      }
     }
    }
   }
   return {maps:Object.keys(sources).length,transitions,diagonal,longDiagonal,regressions,
    samples,invalid:calc(null,0,1),same:calc([[2,2],[2,2]],0,1)};
  });
  assert.equal(audit.maps,26,'all original DMP route files checked');
  assert.equal(audit.transitions,1894,'every original successive DMP index checked');
  assert.ok(audit.diagonal>400&&audit.longDiagonal>5,'source routes include real nonunit diagonals');
  assert.ok(audit.regressions>=8,'demonstrate original projected-coordinate bug on real files');
  assert.equal(audit.invalid,null);
  assert.equal(audit.same,'toward');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const live=await page.evaluate(samples=>{
   const game=window.__ROG_TEST__,info=game.getSourceMaps();
   const original=game.getMatch(),out=[];
   for(const item of samples){
    const name=info[item.mapId]?.title;
    if(!name)throw Error('Source map id missing '+item.mapId);
    const route=window.ORIGINAL_LEAF_MAPS[item.mapId];
    const sample={...original,map:name,tiles:game.generateTiles(name),
      players:original.players.map(p=>({...p,position:item.from}))};
    game.setMatch(sample);
    const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    if(!actor||actor.dataset.position!==String(item.from))
     throw Error('Pawn not grounded at source previous cell '+item.mapId);
    sample.players[0].position=item.to;
    game.setMatch(sample);
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const actual=pawn?.dataset.travelFacing;
    const basis=pawn?.dataset.travelFacingBasis;
    const platform=document.querySelector('#board-nodes>.tile[data-tile="'+item.to+'"]');
    const playerDepth=Number(pawn?.dataset.dmpPainterDepth);
    const tileDepth=Number(platform?.style.zIndex);
    out.push({id:item.mapId,to:item.to,expected:item.expected,
      actual,basis,depthValid:Number.isFinite(playerDepth)&&playerDepth>tileDepth});
   }
   game.setMatch(original);
   return out;
  },audit.samples);
  assert.equal(live.length,audit.regressions,'every proven bad original source step tested live');
  assert.ok(live.every(x=>x.actual===x.expected),
   'actual rendered chessman follows source DMP vertical axis: '+JSON.stringify(live));
  assert.ok(live.every(x=>x.basis==='original-DMP-XY/web-direction-inference'),
   'do not falsely label inferred sprite direction as decoded EXE behavior');
  assert.ok(live.every(x=>x.depthValid),'chessman remains above its true native source platform');
  assert.deepEqual(errors,[],'no runtime errors after real game changes across native source routes');
  console.log('4LEAF ORIGINAL DMP SOURCE FACING PASS '+JSON.stringify({
   browser:ENGINE===chromium?'chromium':'webkit',
   maps:audit.maps,transitions:audit.transitions,diagonal:audit.diagonal,
   longDiagonal:audit.longDiagonal,wrongDirectionFixed:audit.regressions,liveCases:live.length
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF DMP FACING FAILED',e.stack||e);process.exit(1)});
