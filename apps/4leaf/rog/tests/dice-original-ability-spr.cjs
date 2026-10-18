'use strict';
/* Genuine 2002 winAbility.spr pixels must appear ONLY on authorized actual
 * game ability cast; confirm/cancel, original source dimensions/origins,
 * real charges and turn state all remain independently functional. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
    'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
    window.__LEAF_ORIGINAL_ABILITY__?.members.length===6);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].team=['c_0045']; // genuine CardData abilityId 25: BLOCK
   m.players[0].ability=100;
   window.__ROG_TEST__.drawGame();
  });
  assert.equal(await page.locator('#ability-btn').isEnabled(),true);
  assert.equal(await page.locator('#leaf-original-ability-stage').count(),0,
   'source ability art must not overlay ordinary board idle turns');
  await page.locator('#ability-btn').click();
  await page.waitForFunction(()=>document.querySelector('#modal-title')?.textContent==='어빌리티 발동');
  assert.equal(await page.locator('#leaf-original-ability-stage').count(),0,
   'asking for original ability confirmation is not yet actual cast');
  await page.locator('#modal-buttons button').filter({hasText:'발동'}).click();
  await page.waitForFunction(()=>document.querySelector('#leaf-original-ability-stage')?.dataset.status==='ready',
   null,{timeout:8000});
  const proof=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   const scene=document.getElementById('leaf-original-ability-stage');
   const images=[...scene.querySelectorAll('img')];
   return {state:window.__LEAF_ORIGINAL_ABILITY__.getState(),
    source:scene.dataset.sourceMember,placement:scene.dataset.placement,
    aria:scene.getAttribute('aria-label'),
    type:scene.getAttribute('role'),
    frames:images.map(img=>({
     n:Number(img.dataset.sourceFrame),
     natural:[img.naturalWidth,img.naturalHeight],
     width:img.width,height:img.height,
     left:parseFloat(img.style.left),top:parseFloat(img.style.top),
     src:img.getAttribute('src'),original:img.dataset.originalSourceMember
    })),
    player:{meter:m.players[0].ability,block:m.players[0].effects.block},
    active:m.active,rollCount:m.turn};
  });
  assert.equal(proof.source,'Dice/IMG.pak:winAbility.spr');
  assert.match(proof.placement,/archive-origin-delta/);
  assert.equal(proof.state.originalSourceRecovered,true);
  assert.equal(proof.state.historicalTimingRecovered,false,
   'do not falsely claim exact original scene duration from 2D source');
  assert.equal(proof.frames.length,6);
  assert.deepEqual(proof.frames.map(f=>f.n),[0,1,2,3,4,5]);
  assert.deepEqual(proof.frames.map(f=>f.natural),[
   [330,284],[41,29],[41,29],[41,29],[41,29],[41,29]]);
  assert.deepEqual(proof.frames.map(f=>[f.left,f.top]),[
   [0,0],[35,287],[65,326],[146,340],[226,326],[256,287]],
   'each individual actual source IMG.pak SPR frame uses its archived native origin offsets');
  assert.ok(proof.frames.every(f=>f.src.includes('original/SourceSPRExtra/winAbility-')&&
   f.original==='Dice/IMG.pak:winAbility.spr'));
  assert.deepEqual(proof.player,{meter:0,block:1},
   'actual source ability GUI must accompany real CardData Block 25 effect and meter debit');
  assert.equal(proof.active,0,'ability GUI never invents or advances game turns');
  await page.screenshot({path:'leaf-original-source-winAbility-live.png'});
  await page.waitForFunction(()=>!document.getElementById('leaf-original-ability-stage'),null,{timeout:7000});
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   m.players[0].ability=100;window.__ROG_TEST__.drawGame();
  });
  await page.locator('#ability-btn').click();
  await page.locator('#modal-buttons button').filter({hasText:'취소'}).click();
  assert.equal(await page.locator('#leaf-original-ability-stage').count(),0);
  assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].ability),100,
   'cancel remains cancel; no source art and no ability meter loss');
  assert.deepEqual(errors,[]);
  console.log('ORIGINAL WINABILITY 2002 SIX SPR FRAMES PASS',JSON.stringify({frames:6,
   actualAbility:'CardData c_0045/BLOCK25',cancelPreserved:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL ABILITY ART REGRESSION FAILED',e.stack||e);process.exit(1)});
