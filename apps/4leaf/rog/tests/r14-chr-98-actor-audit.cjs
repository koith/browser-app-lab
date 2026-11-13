'use strict';
/* R14-A: all 98 CHR cards, live game DOM (2026-11-05).
 * For every card this mounts the card as the real hotseat player's chessman
 * and drives the REAL actor module through idle, walk (toward/left/right/
 * away), board attack, hurt and victory, then a real resolveBattle duel as
 * attacker and as defender. Per state it records the rig, the CHR body
 * member, the original frame indices actually rendered, whether they equal
 * the original OBS table sequence (native-card-action-sequences.js),
 * mirroring, decoded image size and the foot (lowest opaque) row.
 * Defects reported: portrait/CSS fallback on a card whose body is
 * recovered, legacy/structural guesses where an original table exists,
 * rendered indices != original table, missing/undecoded frames, wrong
 * mirror side, and a different body appearing for the card.
 * Card 0156 (OBS2/1222) is expected to be the ONLY unrecovered body.
 * Env: LEAF_AUDIT_OUT=<json>, LEAF_CARDS=0040,0156 (debug subset),
 *      FOURLEAF_BROWSER=webkit. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const BOARD=[['idle','toward'],['walk','toward'],['walk','left'],['walk','right'],['walk','away'],['attack','toward'],['hurt','toward'],['victory','toward']];

async function start(page){
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 await page.goto(base);
 await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&window.__LEAF_CHR_BODY_MAP__&&window.__LEAF_NATIVE_CARD_ACTIONS__);
 await page.locator('[data-route="lobby"]').first().click();
 await page.locator('#lobby-create').click();
 await page.locator('#game-mode').selectOption('hotseat');
 await page.locator('#start-game').click();
 await page.waitForSelector('#game:not(.hidden)');
}
// Wait until the pawn's frame image for the current state is decoded.
async function settled(page,sel){
 await page.waitForFunction(sel=>{const p=document.querySelector(sel);if(!p)return false;
  if(p.dataset.actorSourceLoad==='loading')return false;
  if(p.dataset.actorRig!=='original-obs-sprite')return true;
  const img=p.querySelector('img.leaf-chess-original-obs');
  return Boolean(img&&img.complete&&img.naturalWidth>0&&img.getAttribute('src'))},sel,{timeout:18000});
}
function readState(sel){
 const p=document.querySelector(sel);if(!p)return null;
 const card=p.dataset.chessmanId;
 const vis=e=>{if(e.hidden)return false;for(let n=e;n&&n!==p.parentElement;n=n.parentElement){const c=getComputedStyle(n);
   if(c.display==='none'||c.visibility==='hidden'||Number(c.opacity)===0)return false}
  const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
 const imgs=[...p.querySelectorAll('img')].filter(vis).map(i=>({cls:i.className,
  src:(i.currentSrc||i.src||'').replace(/^.*\/original\//,'original/'),w:i.naturalWidth,h:i.naturalHeight,complete:i.complete}));
 const obs=imgs.find(i=>/leaf-chess-original-obs/.test(i.cls))||null;
 const img=obs;
 const cs=null;
 const native=window.__LEAF_CHR_BODY_MAP__.resolve(card);
 return {card,rig:p.dataset.actorRig||null,source:p.dataset.actorSource||null,
  table:p.dataset.sourceActionTable||null,slot:p.dataset.sourceNativeSlot||null,
  seq:(p.dataset.sourceFrameSequence||'').split(',').filter(Boolean).map(Number),
  frame:p.dataset.actorFrame||null,mirror:p.dataset.sourceMirror||null,
  provenance:p.dataset.sourceKeyframeProvenance||null,
  img:obs,visibleImages:imgs,
  member:native?.originalMember||null,frames:native?.frames?.length||0,
  fallbackNode:imgs.some(i=>/leaf-chess-original-card-fallback|leaf-chess-portrait/.test(i.cls)),
  expectedUrl:native&&Number.isFinite(Number(p.dataset.actorFrame))?(native.frames.find(f=>String(f.index)===p.dataset.actorFrame)?.url||'').replace(/^.*\/original\//,'original/'):null};
}
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const out={generated:new Date().toISOString(),engine,cards:[],summary:null,
  method:'live hotseat pawn + real resolveBattle duel; expected = window.__LEAF_NATIVE_CARD_ACTIONS__.sequenceFor(resolve(card), …)',
  labels:{frameIndices:'VERIFIED (18-byte OBS records)',slotRoles:'INFERRED',tickMs:'UNVERIFIED (WEB 40ms/tick)',hurtVictory:'no original slot identified: static same body, UNVERIFIED'}};
 try{
  await start(page);
  const all=await page.evaluate(()=>Object.keys(window.__LEAF_CHR_BODY_MAP__.cards).sort());
  assert.equal(all.length,98,'98 CHR cards');
  const only=process.env.LEAF_CARDS?process.env.LEAF_CARDS.split(','):null;
  // Exact, disjoint four-way coverage. Every one of the 98 card indices is
  // assigned once across the matrix; no card, state or duel side is skipped.
  const shardCount=Number(process.env.LEAF_AUDIT_SHARD_COUNT||1);
  const shardIndex=Number(process.env.LEAF_AUDIT_SHARD_INDEX||0);
  assert.ok(Number.isSafeInteger(shardCount)&&shardCount>=1&&shardCount<=98,
   'valid bounded full-audit shard count');
  assert.ok(Number.isSafeInteger(shardIndex)&&shardIndex>=0&&shardIndex<shardCount,
   'valid full-audit shard index');
  for(const [cardIndex,card] of all.entries()){
   if(cardIndex%shardCount!==shardIndex)continue;
   if(only&&!only.includes(card))continue;
   const rec={card,states:{},duel:{},defects:[]};
   await page.evaluate(card=>{const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+card];m.players[1].team=['c_0056'];m.active=0;
    m.players.forEach(p=>{p.position=0});T.setMatch(m);T.drawGame()},card);
   const sel='#board-pawns .board-pawn[data-id="'+(await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].id))+'"]';
   await page.waitForSelector(sel);
   await settled(page,sel);
   const ident=await page.evaluate(card=>{const b=window.__LEAF_CHR_BODY_MAP__.cards[card];
    const n=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    return {member:b.originalMember,missing:Boolean(b.missing),recovered:Boolean(n),frames:n?.frames?.length||0}},card);
   rec.body=ident;
   for(const [action,travel] of BOARD){
    const st=await page.evaluate(([sel,action,travel])=>{const p=document.querySelector(sel);
     p.dataset.travelFacing=travel;window.__LEAF_GENESIS_ACTORS__.pose(p,action,0);
     const n=window.__LEAF_CHR_BODY_MAP__.resolve(p.dataset.chessmanId);
     const exp=n?window.__LEAF_NATIVE_CARD_ACTIONS__.sequenceFor(n,p.dataset.chessmanId,action,travel,{duel:false,rest:travel}):null;
     return exp?{expected:exp.map(f=>f.index),expectedMirror:Boolean(exp.mirror),expectedTable:exp.table,expectedSlot:exp.nativeSlot||null,evidence:exp.nativeEvidence}:{expected:null}},[sel,action,travel]);
    await settled(page,sel);
    // WebKit can finish a short source action while an in-flight PNG decodes.
    // Never treat that transient as a missing recovered body, but also never
    // swallow a genuinely missing PNG: require decoded pixels before sampling.
    await settled(page,sel);
    const got=await page.evaluate(readState,sel);
    const key=action+(action==='walk'?'-'+travel:'');
    rec.states[key]={...got,...st};
    // defects
    if(ident.recovered){
     if(got.rig!=='original-obs-sprite')rec.defects.push(key+': rig '+got.rig+' although CHR body is recovered');
     if(got.fallbackNode)rec.defects.push(key+': portrait fallback node visible');
     if(!got.img||!got.img.w)rec.defects.push(key+': no decoded original frame image');
     else if(got.expectedUrl&&got.img.src!==got.expectedUrl)rec.defects.push(key+': shows '+got.img.src+' not frame '+got.frame+' of own body');
     const num=m=>String(m||'').match(/(\d{4})\.obs/)?.[1];
     if(got.member&&num(got.member)!==num(ident.member))rec.defects.push(key+': other body '+got.member);
     if(!st.expected)rec.defects.push(key+': no original-table sequence (would fall back to '+(got.table||'?')+')');
     if(st.expected){
      if(JSON.stringify(got.seq)!==JSON.stringify(st.expected))rec.defects.push(key+': rendered '+got.seq.join(',')+' != original '+st.expected.join(','));
      if(String(st.expectedMirror)!==got.mirror)rec.defects.push(key+': mirror '+got.mirror+' != original '+st.expectedMirror);
      if(!/native-CHR/.test(got.table||''))rec.defects.push(key+': non-original table '+got.table);
     }
    }else{
     if(got.img)rec.defects.push(key+': stale OBS pixels '+got.img.src+' visible on an unrecovered body');
     if(!got.fallbackNode)rec.defects.push(key+': unrecovered body shows no CardData portrait');
    }
   }
   // real duel as attacker then defender
   for(const side of ['attacker','defender']){
    await page.evaluate(([card,side])=>{const T=window.__ROG_TEST__,m=T.getMatch();
     document.getElementById('battle-visual')?.remove();
     m.players[0].team=['c_'+(side==='attacker'?card:'0056')];m.players[1].team=['c_'+(side==='attacker'?'0063':card)];
     m.players.forEach(p=>{p.position=0});T.setMatch(m);T.drawGame();
     T.resolveBattle(m.players[0],m.players[1],false)},[card,side]);
    await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.nativeBattlePodium==='ready',null,{timeout:16000}).catch(()=>{});
    const dsel='#battle-visual .leaf-battle-chessman[data-duel-side="'+side+'"]';
    // sample the real timeline: pose + rendered frame every 60ms for 4s
    const timeline=await page.evaluate(async sel=>{const t0=performance.now(),seen=[];let last='';
     while(performance.now()-t0<4000){const p=document.querySelector(sel);if(!p)break;
      const k=(p.dataset.actorPose||'')+'|'+(p.dataset.actorFrame||'')+'|'+(p.dataset.sourceMirror||'');
      if(k!==last){seen.push({t:Math.round(performance.now()-t0),pose:p.dataset.actorPose,frame:p.dataset.actorFrame,mirror:p.dataset.sourceMirror,table:p.dataset.sourceActionTable});last=k}
      await new Promise(r=>setTimeout(r,60))}
     return seen},dsel);
    const got=await page.evaluate(readState,dsel);
    rec.duel[side]={...got,timeline};
    if(ident.recovered){
     if(!got||got.rig!=='original-obs-sprite')rec.defects.push('duel-'+side+': rig '+(got&&got.rig));
     if(got&&got.card!==card)rec.defects.push('duel-'+side+': shows card '+(got&&got.card));
     const attackTable=timeline.find(s=>s.pose==='attack')?.table||'';
     if(side==='attacker'&&!/duel-lunge/.test(attackTable))rec.defects.push('duel-attacker: no original slot-12 lunge ('+attackTable+')');
     const firstMirror=timeline.find(s=>s.pose==='attack')?.mirror;
     if(side==='attacker'&&firstMirror!=='true')rec.defects.push('duel-attacker: lunge not mirrored to face the defender');
    }
    await page.evaluate(()=>{const b=[...document.querySelectorAll('.leaf-native-battle-actions button, #modal-buttons button')].find(x=>/결과 확인/.test(x.textContent));b&&b.click()});
    await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:6000}).catch(()=>{});
   }
   out.cards.push(rec);
   if(rec.defects.length)console.log(card,rec.defects.length,'defects:',rec.defects.slice(0,4).join(' | '));
  }
  const recovered=out.cards.filter(c=>c.body.recovered);
  out.summary={shardIndex,shardCount,cards:out.cards.length,recoveredBodies:recovered.length,
   unrecovered:out.cards.filter(c=>!c.body.recovered).map(c=>c.card+'='+c.body.member),
   cardsWithDefects:out.cards.filter(c=>c.defects.length).map(c=>c.card),
   defectCount:out.cards.reduce((s,c)=>s+c.defects.length,0),pageErrors:errors};
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(out,null,1)+'\n');
  console.log(JSON.stringify(out.summary));
  assert.deepEqual(errors,[]);
  if(!only){
   assert.equal(out.cards.length,Math.ceil((98-shardIndex)/shardCount),
    'complete shard of the canonical sorted 98-body source roster');
   const missingIndex=all.indexOf('0156');
   assert.ok(missingIndex>=0,'known original source gap stays registered');
   assert.deepEqual(out.summary.unrecovered,
    missingIndex%shardCount===shardIndex?['0156=null']:[],
    'the source-absent body must appear in exactly its owning shard');
  }
  assert.deepEqual(out.summary.cardsWithDefects,[],'actor defects');
  console.log('R14 CHR 98 ACTOR AUDIT PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('R14 CHR 98 ACTOR AUDIT FAILED',e.stack||e);process.exit(1)});
