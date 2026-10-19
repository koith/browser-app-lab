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
 const rewards=await page.evaluate(()=>{
  const calculate=window.__ROG_TEST__.calculateMatchReward;
  const mock=(count,map,time,position=0)=>({
   map,startedAt:1000000,players:Array.from({length:count},(_,id)=>({id,position:id?0:position})),tiles:Array(70).fill('normal')
  });
  return {
   tooFast:calculate({id:0},mock(2,'4LEAF'),1000000+179999).gp,
   fourLeafTwo:calculate({id:0},mock(2,'4LEAF'),1000000+180000).gp,
   warpgateTwo:calculate({id:0},mock(2,'워프 게이트'),1000000+180000).gp,
   warpgateEight:calculate({id:0},mock(8,'워프 게이트'),1000000+720000).gp,
   fourLeafEight:calculate({id:0},mock(8,'4LEAF'),1000000+720000).gp,
   loserShare:calculate({id:1},mock(2,'4LEAF',0,35),1000000+180000).gp
  }
 });
 assert.deepEqual(rewards,{tooFast:0,fourLeafTwo:49,warpgateTwo:29,warpgateEight:89,fourLeafEight:109,loserShare:24},'historical original GP eligibility, payouts and loser position share');
 console.log('ORIGINAL GP PASS: 1m30 per participant; 4LEAF 49/109; Warpgate 29/89; no early payout');
 const elemental=await page.evaluate(()=>{
   const source=window.ORIGINAL_LEAF_CHESSMEN,mod=window.__ROG_TEST__.elementalModifier;
   const cards=[0,1,2,3].map(t=>source.find(c=>c.element===t&&c.usable===1&&c.move>0&&c.atk>0&&c.def>0));
   if(cards.some(v=>!v))return {missing:cards.map(x=>!!x)};
   const [wand,sword,cup,disk]=cards.map(c=>'c_'+c.id);
   return {
     swordBuff:mod([sword],'attack','SWORDS'),swordDebuff:mod([sword],'attack','CUPS'),
     cupBuff:mod([sword,wand,cup],'support','CUPS'),cupDebuff:mod([sword,wand,cup],'support','SWORDS'),
     wandBuff:mod([sword,wand],'defense','WANDS'),wandDebuff:mod([sword,wand],'defense','DISKS'),
     diskBuff:mod([disk],'move','DISKS'),diskDebuff:mod([disk],'move','WANDS'),
     neutral:mod([disk],'move','NONE')
   };
 });
 assert.deepEqual(elemental,{swordBuff:2,swordDebuff:-2,cupBuff:2,cupDebuff:-2,wandBuff:2,wandDebuff:-2,diskBuff:2,diskDebuff:-2,neutral:0},'source-element interactions all match documented 4LEAF rule');
 console.log('ORIGINAL ELEMENTS PASS: SWORDS/CUPS/WANDS/DISKS across attack, defense, assist and dice movement');
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
  if(name==='4LEAF'){
   await page.waitForTimeout(450);
   const vis=await page.evaluate(()=>{
     const f=sel=>{const e=document.querySelector(sel);if(!e)return null;const b=e.getBoundingClientRect();return {box:[b.left,b.top,b.width,b.height].map(x=>Math.round(x)),transform:getComputedStyle(e).transform,visibility:getComputedStyle(e).visibility,left:e.style.left,top:e.style.top}};
     return {area:f('#board-area'),world:f('#board-world'),pawn:f('.board-pawn'),firstTile:f('.tile'),lastTile:f('.tile:nth-child(10)'),visibleTiles:[...document.querySelectorAll('.tile')].filter(x=>getComputedStyle(x).visibility==='visible').length,camera:window.__LEAF_CAMERA__?.getState?.().scale};
   });console.log('4LEAF CAMERA GEOMETRY',JSON.stringify(vis));
   await page.screenshot({path:'rog-source-map-playable.png'});
   await page.evaluate(()=>{
     const m=window.__ROG_TEST__.getMatch();
     window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
   });
   await page.waitForSelector('#battle-visual',{timeout:5000});
   await page.screenshot({path:'rog-source-battle-live.png'});
   await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
   await page.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:5000});
  }
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
 const randomized=await page.evaluate(()=>{
  const match=window.__ROG_TEST__.getMatch();
  const info=window.__ROG_TEST__.getSourceMaps();
  const entries=Object.entries(info).filter(([id,entry])=>
   window.ORIGINAL_LEAF_MAPS[id]?.length>9);
  const source=entries.find(([id,entry])=>entry.title===match?.map);
  return {map:match?.map,sourceId:source?.[0]||null,
   sourceCount:source?window.ORIGINAL_LEAF_MAPS[source[0]].length:0,
   actualCells:match?.tiles.length,available:entries.length,
   historicalNamed:Object.keys(window.ORIGINAL_LEAF_MAP_INFO||{}).length,unverifiedName:source?.[1]?.metadataStatus||null};
 });
 assert.equal(randomized.available,26,
  'random game must include 25 originally titled DMP paths plus playable source 0170');
 assert.ok(randomized.sourceId && randomized.sourceCount===randomized.actualCells,
  'original random-map must choose one of ALL 26 archived DMP routes: '+
   JSON.stringify(randomized));
 if(randomized.sourceId==='0170')
  assert.ok(randomized.unverifiedName,
   'anonymous 2002 DMP 0170 must not receive a fabricated archival map title');
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