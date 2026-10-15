const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto('file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>!!window.__LEAF_DICE_FRAME__&&!!window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>window.__LEAF_DICE_FRAME__?.getState().docked,{timeout:5000});
  const native=await page.evaluate(async()=>{
   const dims=async file=>{
    const i=new Image();i.src='./original/IMG/'+file+'.png';
    await i.decode();
    return [i.naturalWidth,i.naturalHeight];
   };
   const box=sel=>{
    const r=document.querySelector(sel).getBoundingClientRect();
    return [r.x,r.y,r.width,r.height];
   };
   const chat=document.querySelector('.messenger');
   const mini=document.querySelector('#board-mini');
   return {
    declared:window.__LEAF_DICE_FRAME__.getState(),
    atlasChat:await dims('chatwnd'),
    atlasMini:await dims('minimap'),
    atlasTopbar:await dims('topbar'),
    atlasTitle:await dims('title'),
    frame:box('#app'),main:box('#main'),chat:box('.messenger'),mini:box('#board-mini'),
    chatBackground:getComputedStyle(chat).backgroundImage,
    miniBackground:getComputedStyle(mini).backgroundImage,
    chatInputVisible:getComputedStyle(document.querySelector('#message')).visibility==='visible',
    boardBackground:getComputedStyle(document.querySelector('#board-world')).backgroundImage,
    nodeCount:document.querySelectorAll('#board-nodes .tile').length,
    dock:mini.parentElement.id
   };
  });
  assert.deepEqual(native.atlasTitle,[800,600],'original Dice client title resource is 800x600');
  assert.deepEqual(native.atlasTopbar,[608,42],'original topbar is 608x42');
  assert.deepEqual(native.atlasChat,[406,152],'original live chat window resource is 406x152');
  assert.deepEqual(native.atlasMini,[172,152],'original minimap resource is 172x152');
  assert.ok(Math.abs(native.frame[2]-800)<2&&Math.abs(native.frame[3]-600)<2,'desktop game uses source logical frame');
  assert.ok(native.main[2]>=594&&native.main[2]<=612,'608px original content coordinate space retained');
  assert.ok(Math.abs(native.chat[2]-406)<1&&Math.abs(native.chat[3]-152)<1,'native chat bitmap registration');
  assert.ok(Math.abs(native.mini[2]-172)<1&&Math.abs(native.mini[3]-152)<1,'native minimap bitmap registration');
  assert.ok(Math.abs(native.mini[0]-native.main[0]-414)<2,'minimap is independently docked beside real chat');
  assert.ok(Math.abs(native.mini[1]-native.chat[1])<2,'original live mini and chat are on the same row');
  assert.equal(native.dock,'dice-native-minidock','actual minimap canvas reparented, not a fake duplicate');
  assert.ok(native.chatBackground.includes('/original/IMG/chatwnd.png'));
  assert.ok(native.miniBackground.includes('/original/IMG/minimap.png'));
  assert.ok(!native.boardBackground.includes('/original/IMG/bgtile.png'),'do not paste ChatTown terrain under Dice TIS board');
  assert.equal(native.nodeCount,104,'the source board contains live interactive TIS cells');
  assert.ok(native.chatInputVisible,'the original chat source art has a real input');
  assert.equal(await page.locator('#mini-map-canvas').count(),1,'only one working minimap canvas');
  await page.locator('#message').fill('원본 채팅창 테스트');
  await page.locator('#message').press('Enter');
  await page.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('원본 채팅창 테스트'));
  await page.screenshot({path:'leaf-dice-original-800x600-frame.png'});
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.players[0].position>0,{timeout:12000});
  assert.equal(await page.locator('#mini-map-canvas').count(),1,'the minimap survives an actual move');
  await page.locator('#exit-game').click();
  await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
  await page.waitForFunction(()=>window.__LEAF_DICE_FRAME__.getState().docked===false);
  assert.equal(await page.locator('#board-mini').evaluate(el=>el.parentElement.id),'board-area','return original minimap to game when outside dice route');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-join').click();
  assert.ok(await page.locator('#game:not(.hidden)').isVisible(),'resumed match still usable');
  assert.equal(await page.locator('#board-mini').evaluate(el=>el.parentElement.id),'dice-native-minidock','docked minimap restores on resume');
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>window.__LEAF_DICE_FRAME__.getState().docked===false);
  assert.equal(await page.locator('#board-mini').evaluate(el=>el.parentElement.id),'board-area','mobile keeps minimap over game board');
  assert.ok(await page.locator('#roll-btn').isVisible(),'roll button is available after responsive reflow');
  const mobile=await page.locator('.messenger').boundingBox();
  assert.ok(mobile.width<=390&&mobile.width>300,'mobile keeps actual chat input visible');
  await page.screenshot({path:'leaf-dice-original-frame-mobile.png'});
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('NATIVE DICE FRAME PASS: 800x600 source, live 406x152 chat and 172x152 minimap, moving game, resume and mobile');
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE DICE FRAME FAILED:',e.stack||e);process.exit(1)});
