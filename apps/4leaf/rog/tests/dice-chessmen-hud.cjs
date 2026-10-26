const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 // This sprite/layout check uses a real local match; central-chat permissions
 // are covered separately in centralized ChatTown authority tests.
 await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_CHESSMEN?.length>50);
  const initiallyHidden=await page.locator('#dice-client-sidebar').evaluate(el=>getComputedStyle(el).display);
  assert.equal(initiallyHidden,'none','right chessman HUD never decorates WorldMap or ChatTown');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const hud=await page.evaluate(()=>{
   const root=document.getElementById('dice-native-party');
   const sidebar=document.querySelector('#app .sidebar');
   const scene=document.getElementById('game');
   const slots=[...root.querySelectorAll('.dice-chessman-slot')];
   const match=window.__ROG_TEST__.getMatch();
   return {
    side:getComputedStyle(sidebar).display,
    roster:[...match.players[0].team],count:slots.length,
    occupied:slots.filter(s=>s.classList.contains('occupied')).map(s=>({
     id:s.dataset.cardId,source:s.querySelector('img')?.getAttribute('src'),
     text:s.querySelector('b')?.textContent,button:s.tagName})),
    empty:slots.filter(s=>s.classList.contains('vacant')).map(s=>({
     id:s.dataset.cardId,hasImg:!!s.querySelector('img'),button:s.tagName})),
    columns:getComputedStyle(root).gridTemplateColumns,
    rect:root.getBoundingClientRect().toJSON(),
    sidebarRect:sidebar.getBoundingClientRect().toJSON(),
    sceneRect:scene.getBoundingClientRect().toJSON(),
    itemPanel:getComputedStyle(scene.querySelector('.item-bar')).display,
    originalBackground:getComputedStyle(sidebar).backgroundImage
   };
  });
  assert.equal(hud.count,4,'original has four in-game chessman windows, including empty reserve');
  assert.equal(hud.occupied.length,hud.roster.length,'no invented owned chessmen');
  assert.equal(hud.empty.length,4-hud.roster.length,'only actual party members get a portrait');
  assert.ok(hud.empty.every(x=>!x.hasImg&&x.button==='DIV'),'unoccupied source pane cannot show a fake portrait');
  assert.deepEqual(hud.occupied.map(x=>x.id),hud.roster,'original displayed chessmen are actual match party, in role order');
  assert.ok(hud.occupied.every(x=>x.button==='BUTTON'&&x.source.startsWith('./original/CardData/chm_')&&x.text.length>0));
  assert.equal(hud.side,'flex','source 800x600 game shows its dedicated right side UI');
  assert.ok(hud.originalBackground.includes('original/IMG/avatarback.png'),'real source 4LEAF blue atlas used');
  assert.ok(hud.rect.x>=hud.sceneRect.right-194&&hud.rect.right<=hud.sceneRect.right+2, 'the original four chessmen overlay only the rightmost 193px of the 800px scene below the game field');
  assert.ok(Math.abs(hud.rect.right-hud.sidebarRect.right)<12,'chessmen grid is registered to original side rail');
  assert.ok(hud.rect.bottom>hud.sidebarRect.bottom-22,'real four-up chessmen dock at bottom of game side rail');
  assert.equal(hud.itemPanel,'none','fabricated item-card strip no longer replaces source chessmen grid');
  await page.waitForFunction(()=>[...document.querySelectorAll('#dice-native-party .occupied img')].every(img=>img.complete&&img.naturalWidth>20),null,{timeout:20000});
  assert.equal(await page.locator('#dice-native-party .occupied img').count(),hud.roster.length,'CardData images are real recovered files');

  await page.locator('#dice-native-party .occupied').first().click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),'clicking a real portrait shows its actual underlying card statistics');
  assert.ok((await page.locator('#modal-content').textContent()).includes('공격'));
  await page.locator('#modal-buttons button').first().click();
  assert.equal(await page.locator('#modal:not(.hidden)').isVisible(),false,'portrait inspection closes without modifying the match');

  // Real IMG/selector.png contains the four purple-blue source button
  // frames. Each is a functional hitbox; no screenshot image map is used.
  const selector=await page.evaluate(async()=>{
   const img=new Image();img.src='./original/IMG/selector.png';await img.decode();
   return {natural:[img.naturalWidth,img.naturalHeight],
    // Modern restoration previously cropped source icons as four independent
    // tiles and painted a false WEB background. Desktop beta25 renders the
    // *complete* genuine 222x152 original sprite exactly once, with four
    // transparent interactive targets on its native positions.
    completeSource:getComputedStyle(document.querySelector('#dice-client-sidebar')).backgroundImage,
    buttons:[...document.querySelectorAll('#dice-original-selector button')].map(el=>({
     id:el.id,source:getComputedStyle(el).backgroundImage,
     position:getComputedStyle(el).backgroundPosition,
     width:el.getBoundingClientRect().width,
     height:el.getBoundingClientRect().height
    }))};
  });
  assert.deepEqual(selector.natural,[222,152],'real 222x152 native selector image is loaded');
  assert.deepEqual(selector.buttons.map(x=>x.id),['dice-inspect-tool','dice-next-tool','dice-items-toggle','dice-ability-tool'],'four original glyph hitboxes survive as independent controls');
  assert.ok(selector.completeSource.includes('/original/IMG/selector.png'),
   'whole 222x152 authentic source PNG replaces fake right rail backing');
  assert.ok(selector.buttons.every(x=>x.source==='none'&&x.width===29&&x.height===29),
   'four hitboxes receive source glyphs from full panel once, rather than duplicate atlas crops');
  assert.equal(await page.locator('#dice-ability-tool').isDisabled(),true,'native ability shortcut cannot bypass actual charge requirement');
  assert.equal(await page.locator('#dice-native-party').getAttribute('data-selected-index'),'0');
  await page.locator('#dice-next-tool').click();
  assert.equal(await page.locator('#dice-native-party').getAttribute('data-selected-index'),'1','real source navigation button changes focused chessman');
  assert.equal(await page.locator('#dice-native-party .occupied').nth(1).evaluate(el=>document.activeElement===el),true,'native navigation gives keyboard focus to actual source CardData portrait');
  await page.locator('#dice-inspect-tool').click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),'native inspect icon opens focused genuine card data');
  await page.locator('#modal-buttons button').first().click();
  await page.evaluate(()=>{window.__ROG_TEST__.getMatch().players[0].ability=100;window.__ROG_TEST__.drawGame()});
  assert.ok(await page.locator('#dice-ability-tool').isEnabled(),'source star button mirrors real full-charge ability state');
  await page.locator('#dice-ability-tool').click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),'original star icon invokes the existing legitimate ability confirmation');
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();

  // Verify the original-looking roster did not silently delete gameplay
  // inventory. This drawer must reuse the SAME existing #my-items buttons.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].ability=0;
   // Native matches start with a random real inventory. Isolate one
   // genuinely usable source item for deterministic consumption QA.
   m.players[0].items=['charge25'];
   window.__ROG_TEST__.drawGame();
  });
  assert.equal(await page.locator('#dice-item-count').textContent(),'1','real item count is bound to actual match inventory');
  assert.equal(await page.locator('#dice-items-toggle').getAttribute('aria-expanded'),'false');
  await page.locator('#dice-items-toggle').click();
  assert.equal(await page.locator('#dice-items-toggle').getAttribute('aria-expanded'),'true','actual inventory drawer opens on demand');
  assert.equal(await page.locator('#my-items .item-card').count(),1,'existing functional item inventory is retained');
  assert.ok(await page.locator('#my-items .item-card').first().isVisible());
  await page.locator('#my-items .item-card').first().click();
  assert.ok(await page.locator('#modal:not(.hidden)').isVisible(),'actual item use confirmation remains wired');
  await page.locator('#modal-buttons button').filter({hasText:'사용'}).click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].ability===25);
  assert.equal(await page.locator('#dice-item-count').textContent(),'0','real item consumption updates right-hand counter');
  assert.equal(await page.locator('#my-items .item-card').count(),0,'item is genuinely consumed by original game logic');
  await page.locator('#dice-items-toggle').click();
  assert.equal(await page.locator('#dice-items-toggle').getAttribute('aria-expanded'),'false');
  await page.screenshot({path:'leaf-chessmen-right-panel-desktop.png'});

  // Change the actual in-progress team: no static bitmap or sample roster
  // can pass this check, because the fourth pane must become a real portrait.
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[3]='c_0045';
   window.__ROG_TEST__.drawGame();
  });
  const fourth=page.locator('#dice-native-party [data-team-index="3"]');
  assert.equal(await fourth.getAttribute('data-card-id'),'c_0045');
  assert.equal(await fourth.locator('img').count(),1,'fourth true source chessman is rendered in reserve slot');
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.players[0].position>0,null,{timeout:14000});
  assert.equal(await fourth.getAttribute('data-card-id'),'c_0045','party HUD remains live after actual dice movement');

  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('#app .sidebar')?.getBoundingClientRect().width<100);
  assert.equal(await page.locator('#dice-native-party .occupied').count(),4,'small screens keep genuine source cards visible');
  assert.ok(await page.locator('#roll-btn').isVisible(),'real dice action remains accessible alongside source 2x2 roster');
  await page.screenshot({path:'leaf-chessmen-right-panel-mobile.png'});
  await page.locator('#exit-game').click();
  await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
  assert.equal(await page.locator('#dice-client-sidebar').evaluate(el=>getComputedStyle(el).display),'none','outside game source panel disappears');
  assert.deepEqual(errors,[],'no browser JS errors');
  console.log('ORIGINAL FOUR-UP CHESSMEN HUD PASS: CardData source portraits, actual party, right rail, 4th reserve, usable inventory and mobile');
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL CHESSMEN HUD FAILED:',e.stack||e);process.exit(1)});
