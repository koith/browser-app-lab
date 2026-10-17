'use strict';
/* Original 2004 4LEAF battle HUD separates THREE distinct source archives:
 * player-side face: Registry/sava (player's selected avatar);
 * gameplay board / duel actor: Dice/OBS native chessman pixels;
 * lower-right selected party: CardData/chm portrait.
 * Never reuse one resource for all three contexts.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_OBS_FRAMES&&window.__LEAF_SOCIAL__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team[0]='c_0045';
   m.players[1].team[0]='c_0042';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>{
   const imgs=[...document.querySelectorAll(
    '#board-pawns .leaf-chess-original-obs, #battle-player-panels .battle-side-portrait img')];
   return imgs.length===4&&imgs.every(x=>x.complete&&x.naturalWidth>20);
  },null,{timeout:14000});
  const snap=await page.evaluate(()=>({
   players:window.__ROG_TEST__.getMatch().players.map(x=>x.team[0]),
   actualAvatar:window.__LEAF_SOCIAL__.getState().avatar,
   rails:[...document.querySelectorAll('#battle-player-panels .battle-side-portrait img')]
    .map(x=>({src:x.getAttribute('src'),wh:[x.naturalWidth,x.naturalHeight],
      role:x.dataset.sourceRole})),
   board:[...document.querySelectorAll('#board-pawns .board-pawn')]
    .map(x=>({id:x.dataset.chessmanId,source:x.dataset.actorSource,rig:x.dataset.actorRig,
      png:x.querySelector('.leaf-chess-original-obs')?.getAttribute('src')})),
   party:[...document.querySelectorAll('#dice-native-party .dice-chessman-face')]
    .map(x=>x.getAttribute('src'))
  }));
  assert.deepEqual(snap.players,['c_0045','c_0042']);
  assert.deepEqual(snap.rails.map(x=>x.wh),[[75,141],[75,141]],
   'left/right historical player profile uses genuine Registry SAVA pixel size');
  assert.ok(snap.rails.every(x=>x.src.startsWith('./original/Registry/sava')&&
   x.role==='player-avatar-not-chessman'));
  assert.equal(snap.rails[0].src,'./original/Registry/'+
   ['sava00','sava82','sava06','sava01','sava85','sava02',
    'sava84','sava04','sava03','sava83','sava05','sava86'][snap.actualAvatar]+'.png',
   'current selected avatar is reflected on original 1P rail');
  assert.deepEqual(snap.board.map(x=>x.rig),['original-obs-sprite','original-obs-sprite']);
  assert.ok(snap.board.every(x=>x.source.startsWith('OBS/')&&x.png?.includes('./original/OBS/')));
  assert.ok(snap.party.length>=1&&snap.party.every(x=>x.startsWith('./original/CardData/chm_')),
   'lower-right 2x2 party pane uses CardData not player SAVA/OBS');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForSelector('#battle-visual .battle-visual-actor');
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#battle-visual .battle-visual-actor .leaf-chess-original-obs')]
   .every(x=>x.complete&&x.naturalWidth>20),null,{timeout:12000});
  const duel=await page.evaluate(()=>[...document.querySelectorAll(
   '#battle-visual .battle-visual-actor')].map(x=>({
    id:x.dataset.chessmanId,rig:x.dataset.actorRig,
    portrait:x.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
    chatAvatar:x.querySelector('[src*="Registry/sava"]')?.getAttribute('src')||null
   })));
  assert.deepEqual(duel.map(x=>x.id),['0045','0042']);
  assert.ok(duel.every(x=>x.rig==='original-obs-sprite'&&
   x.portrait?.startsWith('./original/OBS/')&&!x.chatAvatar));
  await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();
  // The extracted 75x141 Registry/sava PNGs have real RGBA alpha at
  // their green-key margins. Never force a second synthetic mask over native
  // transparent pixels; source with opaque green alone needs computed mask.
  const protocol=await page.evaluate(()=>location.protocol);
  if(protocol==='http:'||protocol==='https:'){
   await page.waitForFunction(()=>[...document.querySelectorAll(
    '#battle-player-panels .battle-side-portrait img')]
    .every(img=>['ready','native-transparent'].includes(
     img.dataset.registryChroma)),null,{timeout:11000})
    .catch(async error=>{
     const debug=await page.evaluate(()=>({
      chroma:window.__LEAF_REGISTRY_CHROMA__?.getState?.(),
      imgs:[...document.querySelectorAll('#battle-player-panels .battle-side-portrait img')]
       .map(img=>({src:img.getAttribute('src'),source:img.dataset.nativeRegistrySource,
        chroma:img.dataset.registryChroma,removed:img.dataset.registryChromaRemoved,
        originalTransparent:img.dataset.registryOriginalTransparent,
        mask:img.style.maskImage.slice(0,90)})),
      protocol:location.protocol
     }));
     console.log('SOURCE_REGISTRY_ALPHA_FAILURE_DIAG '+JSON.stringify(debug));
     throw error;
    });
   const masks=await page.evaluate(()=>[...document.querySelectorAll(
    '#battle-player-panels .battle-side-portrait img')]
    .map(img=>{
     const canvas=document.createElement('canvas');
     canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
     const ctx=canvas.getContext('2d',{willReadFrequently:true});
     ctx.drawImage(img,0,0);
     const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
     let nativeTransparent=0,visibleGreen=0;
     for(let i=0;i<pixels.length;i+=4){
      if(pixels[i+3]===0)nativeTransparent++;
      else if(pixels[i+1]>220&&pixels[i]<75&&pixels[i+2]<75)visibleGreen++;
     }
     return {original:img.getAttribute('src'),state:img.dataset.registryChroma,
      css:getComputedStyle(img).maskImage,removed:Number(img.dataset.registryChromaRemoved),
      originalTransparent:nativeTransparent,visibleGreen};
    }));
   assert.ok(masks.every(m=>m.original.startsWith('./original/Registry/sava')&&
    (m.state==='native-transparent'
     ? m.originalTransparent>1000&&!m.css.includes('data:image/png;base64')
     : m.state==='ready'&&m.css.includes('data:image/png;base64')&&m.removed>1000)),
    'player rail retains original SAVA RGBA alpha or masks truly opaque source green');
   console.log('VERIFIED_SOURCE_REGISTRY_NATIVE_ALPHA '+JSON.stringify(masks));
  }
  const sourceRailGeometry=await page.evaluate(()=>[...document.querySelectorAll(
    '#battle-player-panels .battle-side-portrait img')].map(img=>{
    const r=img.getBoundingClientRect();
    const parent=img.parentElement.getBoundingClientRect();
    const style=getComputedStyle(img);
    const parentStyle=getComputedStyle(img.parentElement);
    return {src:img.getAttribute('src'),pos:[r.x,r.y,r.width,r.height],
      crop:[parent.x,parent.y,parent.width,parent.height],
      visible:style.visibility,display:style.display,opacity:style.opacity,
      parentDisplay:parentStyle.display,parentVisibility:parentStyle.visibility};
   }));
  console.log('ORIGINAL_SAVA_PLAYER_RAIL_GEOMETRY '+JSON.stringify(sourceRailGeometry));
  const sourceImage=await page.locator('#app').screenshot({
   type:'jpeg',quality:64,animations:'disabled',timeout:16000});
  console.log('ORIGINAL_SOURCE_ROLE_JPEG_BASE64 '+sourceImage.toString('base64'));
  assert.ok(sourceRailGeometry.every(x=>x.crop[2]>25&&x.crop[3]>15&&
    x.display!=='none'&&x.visible==='visible'&&x.opacity!=='0'),
    'native historical player avatar rail must not be hidden by game HUD');
  assert.deepEqual(errors,[],'game should have no browser runtime errors');
  console.log('VERIFIED SOURCE ASSET ROLES',JSON.stringify({rails:snap.rails,board:snap.board,duel}));
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE-ASSET-ROLE REGRESSION:',e.stack||e);process.exit(1)});
