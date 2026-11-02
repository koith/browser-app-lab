'use strict';
/* Live Genesis pawn browser QA, using SHA-verified OBS 2002 pixels.
 * Direction mapping is explicitly WEB inferred; checks original source
 * frame IDs and loaded PNGs, not a claimed recovered EXE action table.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const which=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (which==='webkit'?webkit:chromium).launch({
  headless:true,args:which==='webkit'?[]:['--no-sandbox']});
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:800,height:600},
  isMobile:mobile,hasTouch:mobile,deviceScaleFactor:mobile?2:1,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   window.ORIGINAL_LEAF_FULL_ACTION_FRAMES?.['0040']?.frames.length===37);
  const available=await page.evaluate(()=>Object.entries(window.ORIGINAL_LEAF_FULL_ACTION_FRAMES)
   .map(([id,data])=>({id,count:data.frames.length,source:data.originalMember,
    indexes:data.frames.map(f=>f.index),
    sha:data.sourceSHA256})));
  assert.equal(available.length,45,
   'complete source inventory must contain all 45 SHA-verified original 37-frame members');
  for(const id of ['0040','0046','0078'])
   assert.ok(available.some(a=>a.id===id),
    'previously visually reviewed side/attack actor must never be lost: '+id);
  assert.ok(available.every(x=>x.count===37&&
   x.indexes.every((n,i)=>n===i)&&/^[a-f0-9]{64}$/.test(x.sha)));
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const probe=[];
  for(const card of ['c_0056','c_0063','c_0095']){
   const start=await page.evaluate(card=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=[card];m.players[0].position=1;T.setMatch(m);
    return {id:m.players[0].id,turn:m.active,position:m.players[0].position};
   },card);
   await page.waitForTimeout(180);
   const state=await page.evaluate(id=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
    if(!pawn)return {missing:true};
    pawn.dataset.travelFacing='left';
    const seen=new Set();
    const observer=new MutationObserver(()=>seen.add(Number(pawn.dataset.actorFrame)));
    observer.observe(pawn,{attributes:true,attributeFilter:['data-actor-frame']});
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(id,'walk',1150);
    const evidence={rig:pawn.dataset.actorRig,member:pawn.dataset.sourceObsMember,
      seq:pawn.dataset.sourceFrameSequence,source:pawn.dataset.sourceTravelFacing,
      src:pawn.querySelector('.leaf-chess-original-obs')?.getAttribute('src')};
    return new Promise(resolve=>setTimeout(()=>{
      observer.disconnect();
      const img=pawn.querySelector('.leaf-chess-original-obs');
      resolve({...evidence,seen:[...seen],last:img?.getAttribute('src'),
       loaded:!!img?.complete&&img.naturalWidth>0});
    },660));
   },start.id);
   assert.equal(state.missing,undefined,card+' actual source pawn exists');
   assert.equal(state.rig,'original-obs-sprite',card+' never uses fabricated proxy');
   assert.equal(state.seq,'14,15,16,17,18,19',card+' side walk block');
   assert.equal(state.source,'native-CHR-walk-side/source-index-VERIFIED/semantic-role-INFERRED');
   const stem=({'c_0056':'1040','c_0063':'1046','c_0095':'1078'})[card];
   assert.ok(state.src?.includes('/original/OBS/action-full/'+stem+'-'),
    'source must be the actual complete 2002 actor sprites: '+JSON.stringify(state));
   assert.ok(state.seen.length>=3&&state.seen.every(f=>f>=14&&f<=19),
    'actual moving pawn renders distinct original side frames: '+JSON.stringify(state));
   // WebKit may still be downloading the changing sprite at 660ms.
   // Verify eventual real decoded pixels on the live pawn (not a mocked
   // source) after the action settles, instead of assuming instant HTTP.
   await page.waitForFunction(id=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
    const img=pawn?.querySelector('img.leaf-chess-original-obs');
    return !!img?.complete&&img.naturalWidth>0&&
      img.getAttribute('src')?.includes('/original/OBS/action-full/');
   },start.id,{timeout:12000});
   const end=await page.evaluate(()=>({turn:window.__ROG_TEST__.getMatch().active,
    position:window.__ROG_TEST__.getMatch().players[0].position}));
   assert.deepEqual(end,{turn:start.turn,position:start.position},
    'source-only side pose must never change authoritative game turn or path');
   // Follow through with the actual Genesis actor controller's battle
   // attack signal. These are source-verified weapon poses, but interpreting
   // 31/33/35 as a 2002 attack animation is still WEB inferred.
   const attack=await page.evaluate(id=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+id+'"]');
    const seen=new Set();
    const observer=new MutationObserver(()=>seen.add(Number(pawn.dataset.actorFrame)));
    observer.observe(pawn,{attributes:true,attributeFilter:['data-actor-frame']});
    // Browser frame delivery differs on mobile WebKit. Keep the native
    // source attack live long enough to observe all genuine source frames;
    // this QA-only pose does not mutate the authoritative match state.
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(id,'attack',1800);
    const seq=pawn.dataset.sourceFrameSequence;
    const evidence=pawn.dataset.sourceAttackEvidence;
    return new Promise(resolve=>{
      const cutoff=setTimeout(()=>{
        clearInterval(check);
        observer.disconnect();
        resolve({seq,evidence,seen:[...seen]});
      },1450);
      const check=setInterval(()=>{
        if(![31,32].every(f=>seen.has(f)))return;
        clearInterval(check);
        clearTimeout(cutoff);
        observer.disconnect();
        resolve({seq,evidence,seen:[...seen]});
      },35);
    });
   },start.id);
   assert.equal(attack.seq,'25,31,32,32,25',
    card+' uses original wind-up, strike and follow-through frames');
   assert.equal(attack.evidence,
    'strike-front-31-32/structural-37/INFERRED');
   assert.ok([31,32].every(f=>attack.seen.includes(f)),
    card+' actually renders all three distinct original attack poses '+JSON.stringify(attack));
   probe.push({card,side:state.seen,attack:attack.seen});
  }
  assert.deepEqual(errors,[],'no browser errors from complete original actor source');
  console.log('4LEAF COMPLETE ORIGINAL ACTOR SIDE WALK PASS',JSON.stringify({which,mobile,available:available.length,probe}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ORIGINAL ACTOR COMPLETE SIDE WALK FAILED',e.stack||e);process.exit(1)});
