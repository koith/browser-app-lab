'use strict';
/* Native 2002 IMG.pak minipanel.spr must be FOUR real 75x20 buttons.
 * Map stays a working DMP navigator; Chessman Info must read the REAL
 * selected CardData source rather than an invented name/stat screenshot.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
async function check(browser,mobile){
 const page=await browser.newPage({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  deviceScaleFactor:mobile?2:1,isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'
 });
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__LEAF_NATIVE_MINIPANEL__&&window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team=['c_0045','c_0042'];
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>document.querySelector('#dice-native-party .dice-chessman-slot.occupied'));
  const baseline=await page.evaluate(async()=>{
   const root=document.getElementById('board-mini');
   const buttons=[...root.querySelectorAll('.leaf-native-minipanel-tab')];
   const frames=[];
   for(let i=0;i<4;i++){
    const img=new Image();
    img.src='./original/SourceSPRExtra/minipanel-'+String(i).padStart(2,'0')+'.png';
    await img.decode();
    frames.push([img.naturalWidth,img.naturalHeight]);
   }
   const m=window.__ROG_TEST__.getMatch();
   return {source:root.dataset.nativePanelSource,
    nativeFrames:root.dataset.nativePanelFrames,
    tabCount:buttons.length,
    dimensions:frames,
    backgrounds:buttons.map(b=>getComputedStyle(b).backgroundImage),
    parent:root.parentElement?.id,
    ariaHidden:root.parentElement?.getAttribute('aria-hidden'),
    game:{turn:m.turn,active:m.active,position:m.players[0].position},
    canvasVisible:getComputedStyle(document.getElementById('mini-map-canvas')).visibility};
  });
  assert.equal(baseline.source,'Dice/IMG.pak:minipanel.spr');
  assert.equal(baseline.nativeFrames,'4');
  assert.equal(baseline.tabCount,2);
  assert.deepEqual(baseline.dimensions,[[75,20],[75,20],[75,20],[75,20]],
   'all source minipanel tabs must use the real 2002 native size');
  assert.ok(baseline.backgrounds[0].includes('minipanel-01.png')&&
   baseline.backgrounds[1].includes('minipanel-02.png'),
   'initial source bitmap displays real original active minimap / inactive chessman info');
  assert.equal(baseline.canvasVisible,'visible');
  if(!mobile&&baseline.parent==='dice-native-minidock')
   assert.equal(baseline.ariaHidden,'false','docked real source buttons must be accessible');
  const button=page.locator('#board-mini .leaf-native-minipanel-tab[data-panel="info"]');
  await button.click();
  await page.waitForFunction(()=>document.querySelector('#board-mini')?.dataset.activePanel==='info');
  const first=await page.evaluate(()=>{
   const node=document.getElementById('leaf-native-chessman-info');
   const tab=document.querySelector('#board-mini [data-panel="info"]');
   return {view:window.__LEAF_NATIVE_MINIPANEL__.getState(),
    label:node.querySelector('strong').textContent,
    stats:node.querySelector('span').textContent,
    infoVisible:getComputedStyle(node).display,
    canvas:getComputedStyle(document.getElementById('mini-map-canvas')).visibility,
    buttonArt:getComputedStyle(tab).backgroundImage,
    chosen:document.querySelector('#dice-native-party .dice-chessman-slot.selected')?.dataset.cardId,
    source:node.dataset.sourceCardArtwork};
  });
  assert.equal(first.view.view,'info');
  assert.equal(first.view.layoutVerified,false,
   'actual CardData values do NOT prove recovered 2002 information panel layout');
  assert.equal(first.view.card,first.chosen,'info always reads active genuine party selection');
  assert.ok(first.source.includes('original/CardData/chm_'));
  assert.ok(first.buttonArt.includes('minipanel-03.png'),
   'selected chessman info shows real original 2002 source frame 3');
  assert.ok(first.stats.includes('이동')&&first.stats.includes('공격'));
  assert.equal(first.canvas,'hidden','only the visible source DMP canvas is temporarily hidden');
  assert.notEqual(first.infoVisible,'none');
  const slot=page.locator('#dice-native-party .dice-chessman-slot.occupied').nth(1);
  await slot.evaluate(el=>el.click());
  await page.waitForFunction(()=>document.querySelector('#leaf-native-chessman-info')?.dataset.sourceCardId==='c_0042');
  const second=await page.evaluate(()=>{
   const el=document.getElementById('leaf-native-chessman-info');
   return {card:el.dataset.sourceCardId,name:el.querySelector('strong').textContent,
    source:el.dataset.sourceCardArtwork,info:el.querySelector('span').textContent};
  });
  assert.equal(second.card,'c_0042');
  assert.ok(second.source.includes('original/CardData/chm_'));
  assert.ok(second.name.length>0&&second.info.includes('방어'));
  await page.locator('#board-mini .leaf-native-minipanel-tab[data-panel="map"]').click();
  const restored=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch(),panel=document.getElementById('board-mini');
   return {view:panel.dataset.activePanel,canvas:getComputedStyle(document.getElementById('mini-map-canvas')).visibility,
    overlay:getComputedStyle(document.getElementById('leaf-native-chessman-info')).display,
    source:getComputedStyle(panel.querySelector('[data-panel="map"]')).backgroundImage,
    game:{turn:m.turn,active:m.active,position:m.players[0].position}};
  });
  assert.equal(restored.view,'map');
  assert.equal(restored.canvas,'visible');
  assert.equal(restored.overlay,'none');
  assert.ok(restored.source.includes('minipanel-01.png'));
  assert.deepEqual(restored.game,baseline.game,'view tab clicks never invent moves or change game turn');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-native-original-minipanel-'+(mobile?'mobile':'desktop')+'.png'});
  console.log('GENUINE 2002 MINIPANEL 4 SOURCE FRAMES, REAL MAP/CHESSMAN TABS PASS',JSON.stringify({
   mobile,source:baseline.source,frames:baseline.dimensions,
   selectedSourceCard:second.card,turnUnchanged:true}));
 }finally{await page.close()}
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{await check(browser,false);await check(browser,true)}
 finally{await browser.close()}
})().catch(e=>{console.error('NATIVE MINIPANEL TAB QA FAILED',e.stack||e);process.exit(1)});
