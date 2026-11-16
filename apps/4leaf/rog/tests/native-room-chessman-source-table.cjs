'use strict';
/* 4LEAF 2002-04 Room/roomback.png, REAL 794x404 original source screen.
 * Test actual clickable native table cells, game profile persistence and
 * READY->104-DMP-cell match. No manufactured actors or screenshot wallpaper.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const fs=require('node:fs');
(async()=>{
 const selected=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await selected.launch({headless:true,args:selected===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_DICE_NATIVE__&&window.__LEAF_DICE_ROSTER__&&
   window.__LEAF_NATIVE_CHESSMAN_TABLE__&&window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#dice-lobby-scene.config-open').waitFor();
  const source=await page.evaluate(async()=>{
   const image=new Image();image.src='./original/Room/roomback.png';await image.decode();
   const stage=document.getElementById('dice-native-stage'),rect=stage.getBoundingClientRect();
   const table=document.getElementById('dice-native-owned-chessmen');
   const party=document.getElementById('dice-native-selected-chessmen');
   const norm=el=>{const r=el.getBoundingClientRect();
    return [+(794*(r.left-rect.left)/rect.width).toFixed(1),
      +(404*(r.top-rect.top)/rect.height).toFixed(1),
      +(794*r.width/rect.width).toFixed(1),
      +(404*r.height/rect.height).toFixed(1)];};
   const ro=window.__LEAF_DICE_ROSTER__.getState();
   return {sourceSize:[image.naturalWidth,image.naturalHeight],
    bitmap:getComputedStyle(stage).backgroundImage,
    inventory:norm(table),party:norm(party),
    ownedRows:[...table.children].map(norm),
    partyRows:[...party.children].map(norm),
    roster:ro,selectedState:window.__LEAF_NATIVE_CHESSMAN_TABLE__.getState(),
    visible:!!table.getBoundingClientRect().width,
    drawActualName:table.children[0]?.querySelector('.dice-native-chessman-name')?.textContent,
    phantomCells:table.querySelectorAll('canvas,img').length,
    active:document.activeElement?.id};
  });
  assert.deepEqual(source.sourceSize,[794,404]);
  assert.ok(source.bitmap.includes('original/Room/roomback.png'));
  assert.deepEqual(source.inventory,[373,49,386,176]);
  assert.deepEqual(source.party,[373,255,386,88]);
  assert.equal(source.ownedRows.length,Math.min(source.roster.owned.length,8));
  assert.equal(source.partyRows.length,4);
  assert.equal(source.ownedRows[0][1],49);
  assert.equal(source.ownedRows[0][2],386);
  assert.equal(source.partyRows[3][1],321);
  assert.equal(source.phantomCells,0,'card labels must overlay the source bitmap, not a fake image');
  assert.equal(source.drawActualName,source.roster.owned[0].name);
  const before=source.roster.team;
  const unassigned=source.roster.owned.find(c=>!before.includes(c.id));
  assert.ok(unassigned,'test needs a real owned unassigned source chessman');
  await page.locator('#dice-native-selected-chessmen button[data-slot="3"]').click();
  assert.equal((await page.locator('#dice-native-selected-chessmen button[data-slot="3"]').getAttribute('aria-pressed')),'true');
  await page.locator('#dice-native-owned-chessmen button[data-card-id="'+unassigned.id+'"]').click();
  const updated=await page.evaluate(()=>({
   table:window.__LEAF_NATIVE_CHESSMAN_TABLE__.getState(),
   roster:window.__LEAF_DICE_ROSTER__.getState(),
   saved:JSON.parse(localStorage.getItem('rog_profile')),
   selectedCell:document.querySelector('#dice-native-selected-chessmen button[data-slot="3"]')?.dataset.cardId
  }));
  assert.equal(updated.table.selected[3],unassigned.id);
  assert.equal(updated.roster.team[3],unassigned.id);
  assert.equal(updated.saved.team[3],unassigned.id);
  assert.equal(updated.selectedCell,unassigned.id);
  assert.equal(new Set(updated.roster.team.filter(Boolean)).size,updated.roster.team.filter(Boolean).length);
  await page.screenshot({path:'leaf-native-room-2004-populated-'+selected.name()+'.png'});
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_NATIVE_CHESSMAN_TABLE__&&window.__LEAF_DICE_ROSTER__);
  assert.equal((await page.evaluate(()=>window.__LEAF_DICE_ROSTER__.getState().team[3])),unassigned.id,
   'actual 2002 source table selection must survive browser reload');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#dice-lobby-scene.config-open').waitFor();
  await page.locator('#point-limit').selectOption('24');
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.locator('#game:not(.hidden)').waitFor({timeout:15000});
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes .tile').length===104);
  const match=await page.evaluate(()=>window.__ROG_TEST__.getMatch());
  assert.equal(match.players.length,2);
  assert.equal(match.players[0].team[3],unassigned.id,
   'the genuine READY action must use the same card selected in the SOURCE room table');
  assert.deepEqual(errors,[]);
  console.log('4LEAF_NATIVE_2004_CHESSMAN_INFO_PASS '+JSON.stringify({
   engine:selected.name(),originalPixels:[794,404],
   upperCellCount:source.ownedRows.length,lowerSlots:source.partyRows.length,
   realEditedCard:unassigned.id,realSavedCard:updated.saved.team[3],
   actualMatchPlayers:match.players.length,actualGameCells:104,
   zeroInventedCardImages:true
  }));
 }finally{await browser.close();}
})().catch(e=>{console.error('4LEAF_NATIVE_2004_CHESSMAN_INFO_FAIL',e.stack||e);process.exit(1)});
