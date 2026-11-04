'use strict';
/* Visual front-source audit revised after original CHR +260 card-body mapping.
 * 2004 screenshot remains comparison reference. No identity guessed from card ID.
 */
const assert=require('node:assert/strict'),path=require('node:path');
const {readFileSync}=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:920},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&
   window.__LEAF_NATIVE_CARD_ACTIONS__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const visualReviewedBodyKeys=['0040','0042','0043','0044','0045',
   '0046','0048','0049','0051','0052','0053','0054','0055','0056','0058',
   '0059','0060','0061','0062','0064'];
  const reviewedCards=await page.evaluate(keys=>{
   const map=window.__LEAF_CHR_BODY_MAP__;
   return keys.map(key=>Object.keys(map.cards).find(card=>map.assetKey(card)===key)).filter(Boolean);
  },visualReviewedBodyKeys);
  assert.equal(reviewedCards.length,20,'all 20 previously audited ORIGINAL body keys have true CHR cards');
  const proofs=[];
  for(const card of reviewedCards){
   const state=await page.evaluate(card=>{
    const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team[0]='c_'+card;
    T.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
    const src=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    const f=src.frames[Number(pawn.dataset.actorFrame)];
    const img=pawn.querySelector('img.leaf-chess-original-obs');
    const style=getComputedStyle(img),matrix=new DOMMatrixReadOnly(style.transform);
    return {card,member:src.originalMember,index:Number(pawn.dataset.actorFrame),
     source:img.getAttribute('src'),sha:f.sha256,
     rig:pawn.dataset.actorRig,seq:pawn.dataset.sourceFrameSequence,
     evidence:pawn.dataset.sourceFacingEvidence,cssFlipY:matrix.m22,
     w:img.getBoundingClientRect().width,h:img.getBoundingClientRect().height};
   },card);
   assert.ok([22,23,24].includes(state.index),
    'source front idle must be the CHR-selected original frame: '+JSON.stringify(state));
   assert.equal(state.seq,'22,23,24');
   const member=state.member.match(/(1\d{3})\.obs$/)?.[1];
   assert.ok(member&&state.source.includes('/'+member+'-'+String(state.index).padStart(2,'0')+'.png'),
    'native PNG must come from true CHR member: '+JSON.stringify(state));
   assert.equal(state.rig,'original-obs-sprite');
   assert.match(state.evidence,/CHR-native-front-keys/);
   assert.ok(state.cssFlipY<0,'original OBS flip-top-bottom decoder must render upright');
   assert.ok(state.w>=10&&state.h>=35,'original native actor must be visible');
   proofs.push(state);
  }
  const bad=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();m.players[0].team[0]='c_0040';
   window.__ROG_TEST__.drawGame();
   const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
   return {source:p.dataset.actorSource,rig:p.dataset.actorRig};
  });
  // #579 published 1025 itself: 0040 shows its own body, never 1040.
  assert.equal(bad.rig,'original-obs-sprite','0040 renders its own recovered body');
  assert.match(bad.source,/OBS\.pak\/1025\.obs$/,'do not substitute 1040');
  const original='data:image/jpeg;base64,'+
   readFileSync(path.resolve(__dirname,'../../assets/battle.jpg')).toString('base64');
  await page.evaluate(reference=>{
   const wrap=document.createElement('div');wrap.id='obs-visual-audit';
   wrap.style.cssText='position:fixed;inset:0;z-index:99999;display:flex;gap:14px;background:#17132e;padding:18px';
   const image=new Image();image.src=reference;image.style.width='46vw';
   const live=document.getElementById('game').cloneNode(true);
   live.style.cssText='position:relative!important;width:46vw;height:600px;display:block';
   wrap.append(image,live);document.body.append(wrap);
  },original);
  await page.waitForFunction(()=>document.querySelector('#obs-visual-audit>img')?.naturalWidth===800);
  await page.screenshot({path:'leaf-obs-original-battle-vs-chr-native-source.png'});
  assert.deepEqual(errors,[]);
  console.log('CHR 20 VERIFIED BODY FRONTS ORIGINAL OBS PASS',
   JSON.stringify({audited:proofs.length,wrongCardFallbackPrevented:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR FRONT ORIGINAL SOURCE FAILED',e.stack||e);process.exit(1)});
