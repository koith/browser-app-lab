'use strict';
/* 2026-11-01 restoration checks, measured on the RENDERED game:
 *  - walking up the board (away from camera) plays reviewed rear frames 3..7,
 *    walking down plays the front cycle; unreviewed members keep old paths;
 *  - attack shows the reviewed front three-quarter frame 18;
 *  - battle scores use original 1167.obs numerals when digits are 0..7.
 * Evidence level for direction/attack is INFERRED (visual review), not an
 * original EXE action table; this test pins behaviour, not historical truth. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,
  args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  // Find an upward and a downward two-step run on the live DMP path.
  const seg=await page.evaluate(()=>{
   const T=window.__ROG_TEST__,m=T.getMatch(),n=m.tiles.length;
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
   const ys=[];
   for(let i=0;i<n;i++){m.players[0].position=i;T.setMatch(m);ys.push(parseFloat(pawn.style.top.replace('calc(','')));}
   let up=-1,down=-1;
   for(let i=1;i<n-1;i++){
    if(up<0&&ys[i]-ys[i-1]<-1&&ys[i+1]-ys[i]<-1)up=i-1;
    if(down<0&&ys[i]-ys[i-1]>1&&ys[i+1]-ys[i]>1)down=i-1;
   }
   return {up,down};
  });
  assert.ok(seg.up>=0&&seg.down>=0,'live path has upward and downward runs '+JSON.stringify(seg));
  const walk=(card,start)=>page.evaluate(async([card,start])=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=[card];m.players[0].position=start;T.setMatch(m);
   await new Promise(r=>setTimeout(r,250));
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
   const seen=new Set();
   const obs=new MutationObserver(()=>seen.add(Number(pawn.dataset.actorFrame)));
   obs.observe(pawn,{attributes:true,attributeFilter:['data-actor-frame']});
   for(let k=1;k<=2;k++){m.players[0].position=start+k;T.drawGame();await new Promise(r=>setTimeout(r,70));}
   await new Promise(r=>setTimeout(r,700));obs.disconnect();
   const img=pawn.querySelector('img.leaf-chess-original-obs');
   return {facing:pawn.dataset.travelFacing,seq:pawn.dataset.sourceFrameSequence,
    evidence:pawn.dataset.sourceTravelFacing,frames:[...seen].sort((a,b)=>a-b),
    turn:m.active,position:m.players[0].position,src:img?.getAttribute('src')};
  },[card,start]);
  const report={};
  for(const card of ['c_0046','c_0078','c_0040']){
   const up=await walk(card,seg.up),down=await walk(card,seg.down);
   assert.equal(up.facing,'away');assert.equal(down.facing,'toward');
   assert.equal(up.seq,'3,4,5,6,7',card+' walks away with reviewed rear frames');
   assert.equal(up.evidence,'rear-walk-3-7/visual-reviewed/INFERRED');
   assert.ok(up.frames.length>=3&&up.frames.every(f=>f>=3&&f<=7),card+' rendered rear frames '+up.frames);
   assert.ok(down.seq.split(',').every(f=>Number(f)>=25&&Number(f)<=30),card+' walks toward with front frames');
   report[card]={up:up.frames,down:down.frames};
  }
  // Unreviewed rear (0058: diagonal sword poses at 3..7) keeps the front cycle.
  const guarded=await walk('c_0058',seg.up);
  assert.ok(guarded.seq.split(',').every(f=>Number(f)>=25),'0058 rear is not reviewed; never shows 3..7');
  // Attack: reviewed front three-quarter frame 18, one-shot, ends on front.
  const attack=await page.evaluate(async()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team=['c_0046'];T.setMatch(m);
   await new Promise(r=>setTimeout(r,200));
   const pawn=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
   window.__LEAF_GENESIS_ACTORS__.poseByPlayer(m.players[0].id,'attack',0);
   const seq=pawn.dataset.sourceFrameSequence,ev=pawn.dataset.sourceAttackEvidence;
   await new Promise(r=>setTimeout(r,900));
   return {seq,ev,end:pawn.dataset.actorFrame,done:pawn.dataset.sourcePlaybackComplete};
  });
  assert.equal(attack.seq,'25,18,18,25');
  assert.equal(attack.ev,'front-three-quarter-18/visual-reviewed/INFERRED');
  assert.equal(attack.done,'true');assert.equal(attack.end,'25');
  // Battle score numerals.
  const score=await page.evaluate(async()=>{
   const T=window.__ROG_TEST__,m=T.getMatch();
   m.players.forEach(p=>{p.position=5});T.setMatch(m);
   const R=Math.random;const seq=[.55,0,.4,.4];let k=0;Math.random=()=>k<seq.length?seq[k++]:R();
   try{T.resolveBattle(m.players[0],m.players[1]);}finally{setTimeout(()=>{Math.random=R},1500);}
   await new Promise(r=>setTimeout(r,1300));
   return [...document.querySelectorAll('#battle-visual .battle-visual-total')].map(el=>({
    text:el.textContent,source:el.dataset.numeralSource,
    digits:[...el.querySelectorAll('img.battle-total-digit')].map(i=>({src:i.getAttribute('src'),ok:i.complete&&i.naturalHeight>=65}))}));
  });
  assert.equal(score.length,2,'two battle scores');
  for(const s of score){
   assert.match(s.text,/^\d\d$/);
   if(/[89]/.test(s.text)){
    assert.equal(s.source,'web-text/digit-8-or-9-not-extracted');assert.equal(s.digits.length,0);
   }else{
    assert.equal(s.source,'original-OBS-1167.obs/digits-0-7');
    assert.deepEqual(s.digits.map(d=>d.src),s.text.split('').map(d=>'./original/OBS/bulk/1167-0'+d+'.png'));
    assert.ok(s.digits.every(d=>d.ok),'original numerals loaded');
   }
  }
  assert.deepEqual(errors,[]);
  console.log('ACTOR DIRECTION / ATTACK / SCORE PASS',JSON.stringify({engine,seg,report,attack,score}));
 }finally{await browser.close();}
})().catch(e=>{console.error('ACTOR DIRECTION FAILED',e.stack||e);process.exit(1);});
