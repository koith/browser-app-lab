const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 await page.goto('file://'+path.resolve(__dirname,'../index.html'));
 await page.waitForFunction(()=>!!window.__ROG_TEST__);
 const maps=await page.evaluate(()=>Object.entries(window.ORIGINAL_LEAF_MAP_INFO||{}).filter(([id])=>window.ORIGINAL_LEAF_MAPS[id]?.length>9).map(([id,v])=>({id,name:v.title,n:window.ORIGINAL_LEAF_MAPS[id].length})));
 assert.ok(maps.length>=25,'all original source map titles must load');
 let completed=0;
 for(const {id,name,n} of maps){
  await page.evaluate(()=>{document.querySelector('#modal').classList.add('hidden');window.__ROG_TEST__.go('lobby')});
  if(await page.locator('#lobby-create').isVisible())await page.locator('#lobby-create').click();
  await page.locator('#map-select').selectOption(name);
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#game-mode').selectOption('ai');
  await page.locator('#start-game').click();
  await page.waitForFunction(name=>window.__ROG_TEST__.getMatch()?.map===name&&document.querySelector('#game:not(.hidden)'),name,{timeout:7000});
  const result=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {n:m.tiles.length,tiles:document.querySelectorAll('#board-nodes .tile').length,pawns:document.querySelectorAll('#board-pawns .board-pawn').length,source:window.ORIGINAL_LEAF_TILES?.[window.ORIGINAL_LEAF_MAP_INFO&&Object.keys(window.ORIGINAL_LEAF_MAP_INFO).find(id=>window.ORIGINAL_LEAF_MAP_INFO[id].title===m.map)]?.length||0};
  });
  assert.equal(result.n,n,name+' original map size');
  assert.equal(result.tiles,n,name+' live tile elements');
  assert.equal(result.pawns,2,name+' actor instances');
  if(result.source)assert.equal(result.source,n,name+' decoded historical tile entries');
  // Every board must end in a legitimate, reachable GOAL and award GP.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].position=m.tiles.length-2;
   m.tiles[m.tiles.length-2]='normal';
   m.players[1].position=0;
   window.__ROG_TEST__.drawGame();
  });
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.finished===true,null,{timeout:7000});
  const winner=await page.evaluate(()=>window.__ROG_TEST__.getMatch().winner);
  assert.equal(winner,0,name+' GOAL must award local win');
  completed++;
 }
 await page.evaluate(()=>{document.querySelector('#modal').classList.add('hidden');window.__ROG_TEST__.go('lobby')});
 if(await page.locator('#lobby-create').isVisible())await page.locator('#lobby-create').click();
 await page.locator('#map-select').selectOption('__RANDOM__');
 await page.locator('#start-game').click();
 const randomized=await page.evaluate(()=>window.__ROG_TEST__.getMatch()?.map);
 assert.ok(maps.some(m=>m.name===randomized),'official random-map should choose one of the decoded originals');
 assert.equal(await page.locator('#app.app-classic-dice').count(),1,'4:3 original gameplay focus automatically enabled');
 const rect=await page.locator('#app').boundingBox();
 assert.ok(rect.width<=970,'desktop original-era game view is 4:3-sized');
 await page.screenshot({path:'rog-classic-focus.png'});
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.locator('#roll-btn').isVisible(),'mobile WebView roll button remains usable');
 await page.screenshot({path:'rog-classic-focus-mobile.png'});
 assert.deepEqual(errors,[],'no runtime JavaScript errors');
 await browser.close();
 console.log('4LEAF ORIGINAL ARCHIVE COVERAGE PASS:',completed,'historical playable maps, GOAL victories, random-map, 4:3 screen and mobile');
})().catch(e=>{console.error('4LEAF ARCHIVE COVERAGE FAILED',e.stack||e);process.exit(1)});