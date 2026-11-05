'use strict';
/* Runtime acceptance: CHR +260 source body identity and 18-byte OBS keyframes.
 * Old card-ID=source-ID tests were invalidated by the real 98 CHR records.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const isWebKit=process.env.FOURLEAF_BROWSER==='webkit';
 const browser=await (isWebKit?webkit:chromium).launch({headless:true,
  ...(isWebKit?{}:{args:['--no-sandbox']})});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&
    window.__LEAF_NATIVE_CARD_ACTIONS__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const cards=await page.evaluate(()=>{
   const m=window.__LEAF_CHR_BODY_MAP__;
   return Object.keys(m.cards).filter(id=>m.cards[id].pak==='OBS'&&m.resolve(id));
  });
  // 42 archived + 17 recovered OBS bodies (#579: 1025-1039, 1041, 1057).
  assert.equal(cards.length,59,'59 true source OBS full bodies linked to actual CHR cards');
  const REAR='3,5,6,7,8',SIDE='14,15,16,17,18,19',FRONT='25,26,27,28,29,30';
  // 1057 (card 0074) has its front art at 0-10; its OWN table swaps the
  // rear/front slots (pixel-checked), so it is expected to differ.
  const SWAPPED={'0074':{rear:'25,26,27,28,29,30',front:'3,4,5,6,7,8',idleRear:'22,23,24',idleFront:'0,1,2'}};
  for(const card of cards){
   const live=await page.evaluate(card=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+card];m.players[0].position=1;T.setMatch(m);
    const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    const src=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    const result={card,member:src.originalMember,frameCount:src.frames.length,
      items:{},rig:p?.dataset.actorRig};
    for(const facing of ['away','left','right','toward']){
     p.dataset.travelFacing=facing;
     window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'walk',0);
     const img=p.querySelector('img.leaf-chess-original-obs');
     const f=src.frames[Number(p.dataset.actorFrame)];
     const x=p.dataset.sourceMirror==='true'?-(f.originX+f.width):f.originX;
     result.items[facing]={walk:p.dataset.sourceFrameSequence,
      mirror:p.dataset.sourceMirror,source:p.dataset.actorSource,
      provenance:p.dataset.sourceKeyframeProvenance,
      ticks:p.dataset.sourceNativeKeyTicks,
      left:img?.style.getPropertyValue('--leaf-obs-left'),
      expectedLeft:'calc(50% '+(x<0?'-':'+')+' '+Math.abs(x)+'px)',
      image:img?.getAttribute('src')};
     window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
     result.items[facing].idle=p.dataset.sourceFrameSequence;
    }
    return result;
   },card);
   assert.equal(live.rig,'original-obs-sprite',card+' must not display another member or proxy');
   const sw=SWAPPED[card];
   assert.equal(live.items.away.walk,sw?sw.rear:REAR,card);
   assert.equal(live.items.left.walk,SIDE);
   assert.equal(live.items.right.walk,SIDE);
   assert.equal(live.items.toward.walk,sw?sw.front:FRONT,card);
   assert.equal(live.items.right.mirror,'true');
   assert.equal(live.items.left.mirror,'false');
   assert.equal(live.items.away.idle,sw?sw.idleRear:'0,1,2',card);
   assert.equal(live.items.left.idle,'11,12,13');
   assert.equal(live.items.right.idle,'11,12,13');
   assert.equal(live.items.toward.idle,sw?sw.idleFront:'22,23,24',card);
   for(const x of Object.values(live.items)){
    assert.match(x.source,/Original-CHR-body/);
    assert.match(x.provenance,/original-OBS-18-byte-keyframe-indices-VERIFIED/);
    assert.equal(x.left,x.expectedLeft,'original frame anchor and mirror must agree');
    assert.ok(x.image.startsWith('./original/OBS/action-full')||
     x.image.startsWith('./original/OBS/referenced/obs-'+live.member.match(/(\d{4})\.obs$/)[1]+'-'),x.image);
   }
   assert.equal(live.items.away.ticks,sw?'0,3,6,9,12,15':'0,3,6,9,12');
  }
  for(const [card,member,front] of [
    ['0125','OBS2.pak/1199.obs','28,29,30,31,32,33'],
    ['0170','OBS3.pak/1267.obs','40,41,42,43,44,45']
  ]){
   const state=await page.evaluate(card=>{
    const m=window.__ROG_TEST__.getMatch(),T=window.__ROG_TEST__;
    m.players[0].team=['c_'+card];T.setMatch(m);
    const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    p.dataset.travelFacing='toward';window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'walk',0);
    return {source:p.dataset.actorSource,seq:p.dataset.sourceFrameSequence,
      img:p.querySelector('img.leaf-chess-original-obs')?.src,rig:p.dataset.actorRig};
   },card);
   assert.equal(state.seq,front);
   assert.ok(state.source.includes(member),card);
   assert.equal(state.rig,'original-obs-sprite');
  }
  for(const card of ['0156']){
   const state=await page.evaluate(card=>{
    const m=window.__ROG_TEST__.getMatch(),T=window.__ROG_TEST__;
    m.players[0].team=['c_'+card];T.setMatch(m);
    const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    return {source:p.dataset.actorSource,rig:p.dataset.actorRig,
      portrait:p.querySelector('.leaf-chess-original-card-fallback')?.getAttribute('src')};
   },card);
   assert.equal(state.rig,'original-card-portrait-fallback',card);
   assert.ok((state.portrait?.startsWith('./original/CardData/chm_')||
     state.portrait==='./original/IMG/avatarback.png'),card);
  }
  assert.deepEqual(errors,[],'live source model must not throw JS errors');
  console.log('CHR 98 ORIGINAL CARD-BODY AND 59 CLASSIC ACTION-37 BROWSER PASS',
   JSON.stringify({browser:isWebKit?'webkit':'chromium',classic:59,
    obs23Examples:['0125','0170'],missing:['0156'],
    originalMillisKnown:false}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR ORIGINAL ACTOR TABLE BROWSER FAILED',e.stack||e);process.exit(1)});
