'use strict';
/* Browser verifies exact source frame sequences for humanoid 37-frame OBS.
 * Action map is INFERRED, not a decoded 2002 executable table. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const SIDE='14,15,16,17,18,19',REAR='3,4,5,6,7,8',FRONT='25,26,27,28,29,30';
const REAR_1040='3,5,6,7,8'; // actual OBS 1040 trailer keyframes exclude index 4
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   Object.keys(window.ORIGINAL_LEAF_FULL_ACTION_FRAMES||{}).length===45);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const actors=await page.evaluate(()=>Object.keys(window.ORIGINAL_LEAF_FULL_ACTION_FRAMES)
   .filter(id=>!['0084','0085','0086'].includes(id)).sort());
  assert.equal(actors.length,42,'41 humanoid actors plus reviewed 0088 golem');
  for(const id of actors){
   const r=await page.evaluate(id=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+id];m.players[0].position=1;T.setMatch(m);
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]'),out={};
    for(const facing of ['away','left','right','toward']){
     pawn.dataset.travelFacing=facing;
     window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'walk',0);
     const img=pawn.querySelector('img.leaf-chess-original-obs');
     const frame=window.ORIGINAL_LEAF_FULL_ACTION_FRAMES[id].frames[Number(pawn.dataset.actorFrame)];
     const x=pawn.dataset.sourceMirror==='true'?-(frame.originX+frame.width):frame.originX;
     out[facing]={seq:pawn.dataset.sourceFrameSequence,mirror:pawn.dataset.sourceMirror,
      table:pawn.dataset.sourceActionTable,
      keyTicks:pawn.dataset.sourceNativeKeyTicks,
      keyEvidence:pawn.dataset.sourceKeyframeProvenance,
      left:img.style.getPropertyValue('--leaf-obs-left'),
      expectedLeft:'calc(50% '+(x<0?'-':'+')+' '+Math.abs(x)+'px)',
      transform:getComputedStyle(img).transform,src:img.getAttribute('src')};
     window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
     out[facing].idle=pawn.dataset.sourceFrameSequence;
     out[facing].idleMirror=pawn.dataset.sourceMirror;
     out[facing].idleTable=pawn.dataset.sourceActionTable;
    }
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'attack',0);
    out.attack={seq:pawn.dataset.sourceFrameSequence,label:pawn.dataset.sourceAttackEvidence};
    window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);return out;
   },id);
   assert.equal(r.away.seq,id==='0040'?REAR_1040:REAR,id+' rear');
   if(id==='0040'){
    assert.equal(r.away.keyTicks,'0,3,6,9,12');
    assert.match(r.away.keyEvidence,/OBS-1040\/keyframe-index/);
    assert.match(r.away.table,/OBS-keys-VERIFIED\/action-label-INFERRED/);
   }else assert.equal(r.away.keyTicks,'','other source action mappings are WEB-INFERRED');
   assert.equal(r.left.seq,SIDE,id+' left');
   assert.equal(r.right.seq,SIDE,id+' mirrored right');
   assert.equal(r.toward.seq,FRONT,id+' front');
   assert.equal(r.right.mirror,'true',id+' right mirror');
   for(const f of ['away','left','right','toward']){
    assert.equal(r[f].left,r[f].expectedLeft,id+' '+f+' anchor');
    assert.ok(r[f].src.includes('/original/OBS/action-full/'),id+' authentic OBS source');
   }
   assert.match(r.right.transform,/^matrix\(-1, 0, 0, -1/,id+' right mirrored');
   assert.match(r.left.transform,/^matrix\(1, 0, 0, -1/,id+' left unmirrored');
   assert.equal(r.away.idle,id==='0040'?'0,1,2':'0,1,2,1',id+' rear idle');
   assert.equal(r.left.idle,id==='0040'?'11,12,13':'11,12,13,12',id+' left side idle');
   assert.equal(r.right.idle,id==='0040'?'11,12,13':'11,12,13,12',id+' right side idle');
   assert.equal(r.toward.idle,id==='0040'?'22,23,24':'22,23,24,23',id+' front idle');
   assert.equal(r.right.idleMirror,'true',id+' mirrored right idle');
   assert.equal(r.left.idleMirror,'false',id+' left idle does not mirror');
   assert.equal(r.toward.idleTable,id==='0040'
    ?'native-1040-idle-front/OBS-keys-VERIFIED/action-label-INFERRED'
    :'idle-front/structural-37/INFERRED');
   assert.equal(r.attack.seq,'25,31,32,32,25',id+' attack');
  }
  for(const id of ['0084','0085','0086']){
   const table=await page.evaluate(id=>{
    const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team=['c_'+id];T.setMatch(m);
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    pawn.dataset.travelFacing='right';window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'walk',0);
    const result=pawn.dataset.sourceActionTable;window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'idle',0);
    return result;
   },id);
   assert.notEqual(table?.includes('structural-37'),true,id+' excluded nonhumanoid');
  }
  const duel=await page.evaluate(async()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=['c_0046'];m.players[1].team=['c_0051'];
   m.players.forEach(p=>{p.position=5});T.setMatch(m);
   T.resolveBattle(m.players[0],m.players[1]);await new Promise(r=>setTimeout(r,300));
   const a=document.querySelector('#battle-visual .battle-visual-side.attacker .leaf-battle-chessman');
   const sides=[...document.querySelectorAll('#battle-visual .battle-visual-side')].map(side=>
    [...side.querySelectorAll('.battle-visual-die')].map(d=>Math.round(d.getBoundingClientRect().top)));
   const defender=document.querySelector('#battle-visual .battle-visual-side.defender .leaf-battle-chessman');
   const opening={seq:a?.dataset.sourceFrameSequence,mirror:a?.dataset.sourceMirror,defender: defender?.dataset.actorPose};
   await new Promise(resolve=>setTimeout(resolve,1100));
   return {opening,stage:document.querySelector('#battle-visual')?.dataset.duelOutcome,
    outcome:{attacker:[a?.dataset.duelResult,a?.dataset.actorPose,a?.dataset.sourceFrameSequence,a?.dataset.sourceOutcomeEvidence,a?.dataset.sourceMirror],
             defender:[defender?.dataset.duelResult,defender?.dataset.actorPose,defender?.dataset.sourceFrameSequence,defender?.dataset.sourceMirror]},
    side:a?.dataset.duelSide,sides};
  });
  assert.equal(duel.opening.seq,'11,33,34,35,36,11');
  assert.equal(duel.opening.mirror,'true');
  assert.equal(duel.opening.defender,'idle');
  const attackerWins=duel.stage==='attacker-wins';
  assert.ok(['attacker-wins','defender-wins'].includes(duel.stage));
  assert.equal(duel.outcome.attacker[0],attackerWins?'win':'lose');
  assert.equal(duel.outcome.defender[0],attackerWins?'lose':'win');
  assert.equal(duel.outcome.attacker[2],attackerWins?'11,12,13,12':'11');
  assert.equal(duel.outcome.attacker[4],'true');
  assert.equal(duel.outcome.defender[3],'false');
  assert.ok(duel.outcome.attacker[3]?.endsWith('/UNVERIFIED'),'no fabricated original hurt/victory source frame');
  assert.equal(duel.side,'attacker');
  for(const tops of duel.sides)assert.equal(new Set(tops).size,1,'battle dice single row');
  assert.deepEqual(errors,[]);
  console.log('ACTION TABLE 37 PASS',JSON.stringify({engine,actors:actors.length,duel}));
 }finally{await browser.close();}
})().catch(e=>{console.error('ACTION TABLE 37 FAILED',e.stack||e);process.exit(1);});
