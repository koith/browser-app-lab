'use strict';
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch(engine===chromium?{args:['--no-sandbox']}:{});const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 try {
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_MAPS);
  await page.locator('[data-route="lobby"]').first().click();await page.locator('#lobby-create').click();await page.locator('#game-mode').selectOption('hotseat');await page.locator('#bot-count').selectOption('1');await page.locator('#start-game').click();await page.waitForSelector('#game:not(.hidden)');
  const result=await page.evaluate(async()=>{
   const T=window.__ROG_TEST__,m=T.getMatch(),old=structuredClone(m);let count=0;
   const names=T.getSourceMaps(),tiles=T.getSourceTiles();
   // Use all 60 genuine reciprocal DMP warp entries, not invented map data.
   for(const [id,rows] of Object.entries(tiles)){
    for(let i=0;i<rows.length;i++){
     if(rows[i].type!=='warp')continue;
     const path=window.ORIGINAL_LEAF_MAPS[id],target=path[i][5];
     if(rows[target]?.type!=='warp'||path[target][5]!==i)continue;
     const copy=structuredClone(old);copy.map=names[id].title;copy.tiles=T.generateTiles(copy.map);
     copy.players[0].position=i;copy.players[1].position=0;copy.players[0].ability=12;T.setMatch(copy);
     await T.resolveTile(copy.players[0]);if(copy.players[0].position!==target)throw Error(id+' warp '+i+' -> '+target+' actual '+copy.players[0].position);
     count++;
    }
   }
   const copy=structuredClone(old);copy.players[0].position=4;copy.players[1].position=0;
   copy.tiles.fill('normal');copy.tiles[0]='start';copy.tiles[copy.tiles.length-1]='goal';copy.tiles[4]='boost';copy.players[0].ability=10;T.setMatch(copy);await T.resolveTile(copy.players[0]);
   const boost={pos:copy.players[0].position,ability:copy.players[0].ability};
   copy.tiles[7]='blessing';copy.players[0].items=[];const random=Math.random;Math.random=()=>.62;try{await T.resolveTile(copy.players[0]);}finally{Math.random=random}
   const items=copy.players[0].items.slice();
   const p=copy.players[0];p.team=['c_0043'];p.effects.armageddon=2;Math.random=()=>.99;let reduced;try{reduced=T.moveValues(p)}finally{Math.random=random}
   T.setMatch(old);return {count,boost,items,reduced};
  });
  assert.equal(result.count,60);assert.deepEqual(result.boost,{pos:7,ability:19});assert.equal(result.items.length,5);assert.ok(!result.items.includes('odincurse'));assert.deepEqual(result.reduced,[4]);
  console.log('SOURCE RULES PASS',JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
