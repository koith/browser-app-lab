'use strict';
// Genuine source DMP cells are individually inspectable and camera-focusable.
// Their type/coordinates/TIS/warp destinations must come ONLY from extracted
// original files. No artificial height layer, extra actor or match mutation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',err=>errors.push(String(err)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const BASE=process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html');
 try{
  await page.goto(BASE);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__&&window.__LEAF_DMP_EXPLORER__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile[data-dmp-focusable]').length===104);
  const initial=await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();
   const rows=window.ORIGINAL_LEAF_MAPS[
    Object.keys(window.ORIGINAL_LEAF_MAP_INFO).find(id=>window.ORIGINAL_LEAF_MAP_INFO[id].title===match.map)
   ];
   const original=rows.map((row,index)=>({row,index}))
    .filter(x=>x.row[3]===10&&x.row[5]!==x.index&&x.row[5]>=0&&x.row[5]<rows.length);
   const dom=[...document.querySelectorAll('#board-nodes .tile')];
   return {count:dom.length,
    accessible:dom.every(t=>t.getAttribute('role')==='button'&&t.tabIndex===0),
    labels:dom.every(t=>t.getAttribute('aria-label')?.includes('원본 DMP')),
    type:dom[0].dataset.originalArt,
    original,
    positions:match.players.map(p=>p.position),active:match.active,
    history:match.history.slice(),camera:window.__LEAF_CAMERA__.getState().visible,
    tileSourceSize:dom.map(t=>[t.offsetWidth,t.offsetHeight])
   };
  });
  assert.equal(initial.count,104,'every genuine recovered 4LEAF DMP cell is still in live view');
  assert.ok(initial.accessible&&initial.labels,'all DMP cells have source coordinate accessible inputs');
  assert.ok(initial.tileSourceSize.every(x=>x[0]===145&&x[1]===97),
   'real 145x97 native raised TIS source art, not a screenshot or a smaller false UI');
  assert.ok(initial.original.length>=2,'the extracted original DMP exposes real warp connections');
  const index=initial.original[0].index;
  const inspect=await page.evaluate(index=>window.__LEAF_DMP_EXPLORER__.focus(index),index);
  assert.equal(inspect.index,index);
  assert.deepEqual(inspect.coord,initial.original[0].row.slice(0,2),
   'actual source DMP grid x/y, not fabricated screen coordinates');
  assert.equal(inspect.sourceCode,initial.original[0].row[2],
   'preserve third DMP cell-code without falsely calling it 3D height');
  assert.equal(inspect.warpTo,initial.original[0].row[5],
   'actual warp target is the indexed original DMP record, not random jump');
  assert.ok(inspect.sourceArt,'the visible original raised platform maps to a genuine TIS file');
  const popup=page.locator('#dice-source-dmp-inspector');
  assert.ok(await popup.isVisible(),'gameplay-source inspector is actually visible on top of the real board');
  assert.equal(await popup.getAttribute('data-reconstruction'),'web-inspector',
   'do not portray inferred UI as historic native game protocol');
  const style=await popup.evaluate(e=>({
   paint:getComputedStyle(e).backgroundImage,
   parent:e.parentElement.id,source:e.dataset.sourceArt,
   position:getComputedStyle(e).position
  }));
  assert.ok(style.paint.includes('original/IMG/eventmsgbox.png'),
   'use actual original event frame for current DMP selection, not screenshot overlay');
  assert.equal(style.parent,'board-area','inspector is in the visible playable world, not hidden footer');
  assert.equal(style.source,inspect.sourceArt);
  assert.equal(style.position,'absolute');
  const beforeWarp=await page.evaluate(()=>({
   history:window.__ROG_TEST__.getMatch().history.slice(),
   active:window.__ROG_TEST__.getMatch().active,
   position:window.__ROG_TEST__.getMatch().players.map(x=>x.position),
   minimap:window.__LEAF_MINIMAP_NAV__.getState()
  }));
  const jump=page.locator('.dmp-inspector-warp');
  assert.ok(await jump.isVisible(),'original DMP connection has an actual clickable destination');
  await jump.click();
  const selected=await page.evaluate(()=>({
   selection:window.__LEAF_DMP_EXPLORER__.getState().selected,
   follow:window.__LEAF_MINIMAP_NAV__.getState().follow,
   camera:window.__LEAF_CAMERA__.getState().visible,
   history:window.__ROG_TEST__.getMatch().history.slice(),
   active:window.__ROG_TEST__.getMatch().active,
   positions:window.__ROG_TEST__.getMatch().players.map(x=>x.position)
  }));
  assert.equal(selected.selection,inspect.warpTo,'real warp destination is focused by live camera');
  assert.equal(selected.follow,false,'manual DMP inspection uses shared source minimap camera');
  assert.deepEqual(selected.history,beforeWarp.history,'inspection NEVER adds fake move entries');
  assert.equal(selected.active,beforeWarp.active,'inspection NEVER advances a human turn');
  assert.deepEqual(selected.positions,beforeWarp.position,'inspection NEVER teleports real chessmen');
  assert.notDeepEqual(selected.camera,beforeWarp.minimap.camera.visible,'focusing distant DMP destination navigates actual world camera');
  assert.equal(await page.locator('#board-nodes .tile[aria-pressed="true"]').count(),1,
   'selected original source tile has clear focus without ghost copies');
  await page.screenshot({path:'leaf-native-dmp-warp-terrain-focus.png'});

  const focusTarget=page.locator('#board-nodes .tile[data-tile="'+inspect.warpTo+'"]');
  await focusTarget.focus();
  await page.keyboard.press('Enter');
  assert.equal(await popup.getAttribute('data-index'),String(inspect.warpTo),
   'keyboard Enter inspects the actual visible TIS platform');
  await page.keyboard.press(' ');
  assert.equal(await popup.getAttribute('data-index'),String(inspect.warpTo),
   'Space key also uses the actual source DOM tile');
  await page.locator('.dmp-inspector-close').click();
  assert.equal(await popup.isVisible(),false,'native-source event panel can be closed without a game action');
  assert.equal(await page.locator('#board-nodes .tile[aria-pressed="true"]').count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(index=>window.__LEAF_DMP_EXPLORER__.focus(index),index);
  assert.ok(await popup.isVisible(),'mobile real DMP source inspector works at 390px without losing the scene');
  const mobile=await popup.boundingBox();
  assert.ok(mobile.width<=244&&mobile.x>=0&&mobile.x+mobile.width<=390,
   'the compact source panel is inside the actual phone viewport');
  assert.deepEqual(await page.locator('#board-nodes .tile').first().evaluate(e=>[e.offsetWidth,e.offsetHeight]),[145,97],
   'phone preserves unscaled original TIS logical sprite pixels');
  assert.deepEqual(errors,[],'DMP navigation, source sprites and remote-free game state have no runtime exceptions');
  console.log('GENESIS REAL DMP SOURCE CELL EXPLORATION PASS',JSON.stringify({
   sourceCells:initial.count,warpLinks:initial.original.length,
   selectedDmp:inspect.coord,sourceArt:inspect.sourceArt,warpTarget:inspect.warpTo,
   initialPlayers:initial.positions,afterPlayers:selected.positions,
   cameraBefore:beforeWarp.minimap.camera.visible,cameraAfter:selected.camera,mobile
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS REAL DMP SOURCE CELL EXPLORATION FAILED',e.stack||e);process.exit(1)});
