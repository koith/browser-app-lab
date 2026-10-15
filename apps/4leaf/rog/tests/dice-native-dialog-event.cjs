'use strict';
// Native Genesis IMG/dialog.png (292x110) is a genuine framed source bitmap,
// not a screen capture. Use its edges for LIVE confirmation, no fake dialogs;
// IMG/eventmsgbox.png (244x52) displays ACTUAL game move messages.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&document.querySelector('#start-game'));
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  // Two genuine hotseat users give deterministic turns without an AI race.
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const art=await page.evaluate(async()=>{
   const src=async name=>{
    const i=new Image();i.src='./original/IMG/'+name+'.png';
    await i.decode();return [i.naturalWidth,i.naturalHeight];
   };
   return {dialog:await src('dialog'),event:await src('eventmsgbox')};
  });
  assert.deepEqual(art.dialog,[292,110],'source original Genesis dialog bitmap shape');
  assert.deepEqual(art.event,[244,52],'source original Genesis event message box shape');

  await page.locator('#exit-game').click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),
   'real game exit asks for confirmation');
  const prompt=await page.locator('#modal').evaluate(node=>{
   const window=node.querySelector('.modal-window');
   const style=getComputedStyle(window);
   const bounds=window.getBoundingClientRect();
   return {native:node.dataset.nativeDiceDialog,
    graphic:style.borderImageSource,regions:style.borderImageSlice,
    viewport:[bounds.width,bounds.height],title:node.querySelector('#modal-title').textContent,
    realButtons:[...node.querySelectorAll('#modal-buttons button')].map(b=>b.textContent),
    foreground:getComputedStyle(node.querySelector('#modal-content')).color};
  });
  assert.equal(prompt.native,'IMG/dialog.png','only actual game short dialogs use recovered source');
  assert.ok(prompt.graphic.includes('/original/IMG/dialog.png'),'real 292x110 frame drives genuine game popup');
  assert.ok(prompt.regions.includes('17')&&prompt.regions.includes('4'),
   'source rectangle has original 17px top and intact corner/nine-slice');
  assert.ok(Math.abs(prompt.viewport[0]-292)<1,'do not scale original source horizontal frame');
  assert.deepEqual(prompt.realButtons,['나가기','취소'],
   'restore appearance without changing real confirmation callbacks');
  assert.ok(prompt.title.includes('게임에서 나가기'));
  await page.screenshot({path:'leaf-original-genesis-dialog.png'});
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  assert.equal(await page.locator('#modal:not(.hidden)').count(),0,'Cancel keeps the existing live game');
  assert.ok(await page.locator('#game:not(.hidden)').isVisible(),'cancel did not abandon any real game state');
  assert.ok(await page.locator('#roll-btn').isEnabled(),'source frame does not block gameplay controls');
  await page.locator('#dice-menu-round').click();
  const complex=await page.locator('#modal').evaluate(node=>({
   native:node.dataset.nativeDiceDialog||null,
   participants:node.querySelectorAll('#modal-content div').length,
   body:node.querySelector('#modal-content').textContent
  }));
  assert.equal(complex.native,null,'complex live participant details are not clipped into original 110px small dialog');
  assert.ok(complex.participants>=2&&complex.body.includes('라운드'),
   'real match details remain visible and inspectable');
  await page.locator('#modal-buttons button').first().click();

  // Real turn with native status art: not a hard-coded demonstration message.
  const oldLog=await page.locator('#dice-native-event').textContent();
  await page.locator('#roll-btn').click();
  await page.waitForFunction(previous=>{
   const node=document.querySelector('#dice-native-event');
   return node?.textContent&&node.textContent!==previous&&
    node.dataset.source==='IMG/eventmsgbox.png'&&node.offsetWidth>0;
  },oldLog,{timeout:16000});
  const move=await page.locator('#dice-native-event').evaluate(node=>({
   source:node.dataset.source,paint:getComputedStyle(node).backgroundImage,
   frame:[node.offsetWidth,node.offsetHeight],
   rendered:[node.getBoundingClientRect().width,node.getBoundingClientRect().height],
   position:getComputedStyle(node).position,
   visible:getComputedStyle(node).display,
   parent:node.parentElement.id,
   realEventNodes:document.querySelectorAll('#dice-native-event').length,
   event:node.textContent,title:node.title
  }));
  assert.equal(move.source,'IMG/eventmsgbox.png','actual played move displayed in original source event');
  assert.equal(move.parent,'board-area','original event source appears in the visible playable board, not hidden web item footer');
  assert.equal(move.realEventNodes,1,'one live event UI, no fake duplicate');
  assert.equal(move.visible,'flex','actual source-backed event remains painted on screen');
  assert.equal(move.position,'absolute','event floats without hiding actual playable TIS tile hitboxes');
  assert.ok(move.paint.includes('/original/IMG/eventmsgbox.png'));
  assert.ok(Math.abs(move.frame[0]-244)<1&&Math.abs(move.frame[1]-52)<1,
   'true 244x52 original event rectangle in non-mobile client: '+JSON.stringify(move));
  assert.equal(move.event,move.title,'ellipsized two-line paint keeps complete actual gameplay event accessible');
  assert.ok((await page.evaluate(()=>window.__ROG_TEST__.getMatch().history)).includes(move.event),
   'event box is sourced from real persistent match history, never made-up status');
  await page.screenshot({path:'leaf-original-genesis-live-eventbox.png'});
  // Source frame also follows real charged-ability decision, not only exit.
  await page.evaluate(()=>{
   const match=window.__ROG_TEST__.getMatch();
   match.players[match.active].ability=100;
   window.__ROG_TEST__.drawGame();
  });
  await page.locator('#ability-btn').click();
  assert.equal(await page.locator('#modal').getAttribute('data-native-dice-dialog'),'IMG/dialog.png');
  assert.ok((await page.locator('#modal-content').textContent()).includes('충전 100%'));
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  await page.setViewportSize({width:390,height:844});
  await page.locator('#exit-game').click();
  assert.equal(await page.locator('#modal').getAttribute('data-native-dice-dialog'),'IMG/dialog.png');
  assert.ok((await page.locator('.modal-window').boundingBox()).width<=390,
   'original small window is not clipped on phone');
  assert.ok((await page.locator('#dice-native-event').boundingBox()).width<=244,
   'actual original message panel remains visible on phone');
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  assert.deepEqual(errors,[],'native source prompt and eventbox introduce no JS exceptions');
  console.log('GENESIS NATIVE DIALOG/EVENT PASS',JSON.stringify({art,prompt,move,complexParticipants:complex.participants}));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS NATIVE DIALOG/EVENT FAILED',e.stack||e);process.exit(1)});
