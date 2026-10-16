const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL || 'file://'+path.resolve(__dirname,'../index.html'));
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
    atlasAbility:await dims('abilitybar'),
    atlasMenu:await dims('menu'),
    atlasTerrain:await dims('bgtile'),
    frame:box('#app'),main:box('#main'),chat:box('.messenger'),mini:box('#board-mini'),
    chatBackground:getComputedStyle(chat).backgroundImage,
    miniBackground:getComputedStyle(mini).backgroundImage,
    chatInputVisible:getComputedStyle(document.querySelector('#message')).visibility==='visible',
    boardBackground:getComputedStyle(document.querySelector('#board-world')).backgroundImage,
    terrainSize:getComputedStyle(document.querySelector('#board-world')).backgroundSize,
    terrainRepeat:getComputedStyle(document.querySelector('#board-world')).backgroundRepeat,
    gridDecoration:getComputedStyle(document.querySelector('#game .board-area'),'::before').content,
    nodeCount:document.querySelectorAll('#board-nodes .tile').length,
    dock:mini.parentElement.id
   };
  });
  assert.deepEqual(native.atlasTitle,[800,600],'original Dice client title resource is 800x600');
  assert.deepEqual(native.atlasTopbar,[608,42],'original topbar is 608x42');
  assert.deepEqual(native.atlasChat,[406,152],'original live chat window resource is 406x152');
  assert.deepEqual(native.atlasMini,[172,152],'original minimap resource is 172x152');
  assert.deepEqual(native.atlasAbility,[92,64],'original four-frame 92x16 ABILITY atlas');
  assert.deepEqual(native.atlasMenu,[608,30],'true original 608x30 Genesis in-game IMG/menu atlas');
  assert.deepEqual(native.atlasTerrain,[725,485],'actual recovered 725x485 native Dice forest-and-cliff battlefield');
  assert.ok(Math.abs(native.frame[2]-800)<2&&Math.abs(native.frame[3]-600)<2,'desktop game uses source logical frame');
  assert.ok(native.main[2]>=594&&native.main[2]<=612,'608px original content coordinate space retained');
  assert.ok(Math.abs(native.chat[2]-406)<1&&Math.abs(native.chat[3]-152)<1,'native chat bitmap registration');
  assert.ok(Math.abs(native.mini[2]-172)<1&&Math.abs(native.mini[3]-152)<1,'native minimap bitmap registration');
  // Historic real-play board.jpg/battle.jpg show LEFT minimap + CENTRAL chat,
  // not the reverse order inferred solely from original atlas dimensions.
  assert.ok(Math.abs(native.mini[0]-native.main[0])<2,'archival screenshot: original minimap at bottom LEFT');
  assert.ok(Math.abs(native.chat[0]-native.main[0]-172)<2,'archival screenshot: functional chat directly RIGHT of source minimap');
  assert.ok(Math.abs(native.mini[1]-native.chat[1])<2,'original live mini and chat are on the same row');
  assert.equal(native.dock,'dice-native-minidock','actual minimap canvas reparented, not a fake duplicate');
  assert.ok(native.chatBackground.includes('/original/IMG/chatwnd.png'));
  assert.ok(native.miniBackground.includes('/original/IMG/minimap.png'));
  assert.ok(native.boardBackground.includes('/original/IMG/bgtile.png'),'the Dice battlefield must display its actual recovered 725x485 forest terrain, not a flat blue placeholder');
  assert.equal(native.terrainSize,'725px 485px','keep native source terrain image pixels beneath the independent TIS platform entities');
  assert.equal(native.terrainRepeat,'repeat','pan/zoom retains the original scenery across the larger MVE world');
  assert.equal(native.gridDecoration,'none','fake radial grids must not obscure real source cliffs and buildings');
  assert.equal(native.nodeCount,104,'the source board contains live interactive TIS cells');
  // Source v0.96d Tiles/0000.png is exactly 145x97. Every map cell uses
  // a *real independent* TIS bitmap; obsolete added numbering and fake
  // center crest must not cover the recovered hex geometry.
  const nativeTiles=await page.evaluate(async()=>{
   const source=new Image();source.src='./original/Tiles/0000.png';await source.decode();
   const tile=document.querySelector('#game .board-world .tile[data-original-art]');
   const style=getComputedStyle(tile),rect=tile.getBoundingClientRect();
   const crest=getComputedStyle(document.querySelector('#game .board-center')).display;
   return {
    pixels:[source.naturalWidth,source.naturalHeight],
    paint:style.backgroundImage,
    glyph:getComputedStyle(tile.querySelector('.tile-symbol')).display,
    number:getComputedStyle(tile.querySelector('small')).display,
    sourceTile:tile.dataset.originalArt,
    hitbox:[parseFloat(style.width),parseFloat(style.height)],
    title:tile.title,
    dataset:tile.dataset.tile,
    crest,
    guides:getComputedStyle(document.querySelector('#game #board-lines')).opacity,
    clickable:typeof tile.onclick==='function'
   };
  });
  assert.deepEqual(nativeTiles.pixels,[145,97],'actual source PNG contains the recovered 145x97 4LEAF TIS artwork');
  assert.ok(nativeTiles.paint.includes('/original/Tiles/'),'battlefield cell displays its recovered native platform art');
  assert.equal(nativeTiles.glyph,'none','native artwork already contains artwork, so synthetic emoji labels are hidden');
  assert.equal(nativeTiles.number,'none','invented printed tile numbers no longer obscure TIS artwork');
  assert.equal(nativeTiles.crest,'none','invented large centre crest is not placed over original board art');
  assert.equal(nativeTiles.guides,'0','invented SVG connector lines no longer cover the source map');
  assert.ok(Math.abs(nativeTiles.hitbox[0]/nativeTiles.hitbox[1]-145/97)<0.02,'independent TIS hitbox preserves original source aspect');
  assert.deepEqual(nativeTiles.hitbox,[145,97],
   'each independent source TIS source platform is full 145x97, never old 70x47 half-size');

  assert.ok(nativeTiles.clickable&&nativeTiles.dataset!==undefined&&nativeTiles.title.includes('칸'),'source tiles retain independent hitboxes, accessible source indices and actual gameplay handlers');

  const sourceMenu=await page.evaluate(()=>{
   const rect=s=>document.querySelector(s).getBoundingClientRect();
   const menu=document.querySelector('#game .scene-banner');
   const world=document.querySelector('#game .board-area');
   const exit=document.querySelector('#exit-game');
   const menuStyle=getComputedStyle(menu);
   const info=document.querySelector('#dice-menu-round');
   const party=document.querySelector('#dice-menu-party');
   return {
    title:getComputedStyle(document.querySelector('#app>.titlebar')).display,
    bar:getComputedStyle(document.querySelector('#app>.statusbar')).display,
    topline:getComputedStyle(document.querySelector('#game .game-topline')).display,
    background:menuStyle.backgroundImage,
    height:rect('#game .scene-banner').height,
    alignment:Math.abs(rect('#game .board-area').top-rect('#game .scene-banner').bottom),
    buttons:[info,party].map(btn=>({
     width:btn.getBoundingClientRect().width,height:btn.getBoundingClientRect().height,
     source:getComputedStyle(btn).backgroundImage
    })),
    exit:{source:getComputedStyle(exit).backgroundImage,width:exit.getBoundingClientRect().width}
   };
  });
  assert.equal(sourceMenu.title,'none','original Dice client does not show invented revival Windows titlebar');
  assert.equal(sourceMenu.bar,'none','original Dice client does not have invented bottom status strip');
  assert.equal(sourceMenu.topline,'none','remove fake second PLAYERS/ROUND strip that stole historic stage height');
  assert.ok(sourceMenu.background.includes('/original/IMG/menu.png'),'top chrome paints the recovered real source menu art');
  assert.equal(sourceMenu.height,30,'source game menu uses native 30px logical frame');
  assert.ok(sourceMenu.alignment<2,'actual battlefield begins directly below source menu');
  assert.ok(sourceMenu.buttons.every(b=>b.width===29&&b.height===29&&b.source.includes('/original/IMG/menu.png')),'two source glyphs are actual working buttons');
  assert.ok(sourceMenu.exit.source.includes('/original/MainFrame/toolbarbtn.png')&&sourceMenu.exit.width===30,'actual accessible OUT uses original toolbar sprite');
  await page.locator('#dice-menu-round').click();
  assert.ok((await page.locator('#modal:not(.hidden) #modal-content').textContent()).includes('라운드'),'first native icon opens current real match state');
  await page.locator('#modal-buttons button').first().click();
  await page.locator('#dice-menu-party').click();
  assert.ok((await page.locator('#modal:not(.hidden) #modal-title').textContent()).includes('체스맨'),'second native icon opens the currently selected original chessman');
  await page.locator('#modal-buttons button').first().click();
  assert.ok(native.chatInputVisible,'the original chat source art has a real input');
  assert.equal(await page.locator('#mini-map-canvas').count(),1,'only one working minimap canvas');
  const initialAbility=await page.locator('#ability-btn').evaluate(el=>{
   const st=getComputedStyle(el),r=el.getBoundingClientRect();
   return {width:r.width,height:r.height,image:st.backgroundImage,pos:st.backgroundPosition,disabled:el.disabled};
  });
  assert.equal(initialAbility.disabled,true,'ability action waits for actual 100% charge');
  assert.deepEqual([initialAbility.width,initialAbility.height],[92,16],'live ability button uses native 92x16 frame');
  assert.ok(initialAbility.image.includes('/original/IMG/abilitybar.png'),'actual source sprite powers the button');
  assert.ok(initialAbility.pos.includes('0px 0px'),'uncharged ability uses source resting frame');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].ability=100;
   window.__ROG_TEST__.drawGame();
  });
  assert.ok(await page.locator('#ability-btn').isEnabled(),'original button becomes interactive at full charge');
  assert.ok((await page.locator('#ability-btn').evaluate(el=>getComputedStyle(el).backgroundPosition)).includes('-16px'),'charged ability uses live source frame');
  await page.locator('#ability-btn').hover();
  assert.ok((await page.locator('#ability-btn').evaluate(el=>getComputedStyle(el).backgroundPosition)).includes('-32px'),'hover uses independent original frame');
  await page.locator('#ability-btn').click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),'real charged ability opens original game ability selection');
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  await page.locator('#message').fill('원본 채팅창 테스트');
  await page.locator('#message').press('Enter');
  await page.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('원본 채팅창 테스트'));
  await page.screenshot({path:'leaf-dice-original-800x600-frame.png'});
  const originalCamera=await page.locator('#board-world').evaluate(el=>el.style.transform);
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.players[0].position>0,{timeout:12000});
  assert.equal(await page.locator('#mini-map-canvas').count(),1,'the minimap survives an actual move');
  await page.evaluate(()=>window.__LEAF_CAMERA__?.viewport(1.65,24,16));
  await page.waitForFunction(()=>window.__LEAF_CAMERA__?.getState()?.scale===1.65);
  const movedWorld=await page.locator('#board-world').evaluate(el=>({
   transform:el.style.transform,
   background:getComputedStyle(el).backgroundImage,
   tileCount:el.querySelectorAll('#board-nodes .tile').length
  }));
  assert.ok(movedWorld.background.includes('/original/IMG/bgtile.png'),'actual forest scenery moves inside the SAME game camera as live MVE tiles');
  assert.equal(movedWorld.tileCount,104,'all original independent TIS tile hitboxes survive terrain zoom');
  assert.notEqual(movedWorld.transform,originalCamera,'camera tracks original terrain and playable tiles together');
  await page.locator('#exit-game').click();
  await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
  await page.waitForFunction(()=>window.__LEAF_DICE_FRAME__.getState().docked===false);
  assert.equal(await page.locator('#board-mini').evaluate(el=>el.parentElement.id),'board-area','return original minimap to game when outside dice route');
  assert.notEqual(await page.locator('#app>.titlebar').evaluate(el=>getComputedStyle(el).display),'none','leaving Dice returns normal WorldMap/ChatTown chrome');
  assert.notEqual(await page.locator('#app>.statusbar').evaluate(el=>getComputedStyle(el).display),'none','other screens still retain their own status panel');
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
