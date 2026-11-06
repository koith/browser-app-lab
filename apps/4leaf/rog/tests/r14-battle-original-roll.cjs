'use strict';
/* R14-B: original D6 roll on the battle podium, real resolveBattle path.
 * Desktop 800x600, iPhone 13 portrait and landscape. Per die it records
 * every rendered source frame and checks:
 *  - frames come only from Dice/OBS.pak 1171: slot 20 keys, then slot 12
 *    keys, then the VERIFIED face (value-1), in that order;
 *  - totals stay hidden while dice are falling and are shown on landing;
 *  - the attacker stays idle during the roll and lunges (slot 12 of its own
 *    CHR body) only after the totals, then the outcome follows the lunge;
 *  - a bot-only battle auto-confirms only after the dice landed.
 * Order and ms are INFERRED/WEB; frame indices/ticks are VERIFIED. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const VIEWS=[['desktop-800x600',{viewport:{width:800,height:600}}],['iphone-portrait','iPhone 13'],['iphone-landscape','iPhone 13 landscape']];
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 const out={engine,generated:new Date().toISOString(),views:[]};
 try{
  for(const [name,spec] of VIEWS){
   const opts=typeof spec==='string'?{...devices[spec]}:spec;delete opts.defaultBrowserType;
   const ctx=await browser.newContext({...opts,serviceWorkers:'block'});
   const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
   await page.goto(base);
   await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_BATTLE_DICE_ROLL__&&window.__LEAF_DICE_FALL__?.diceBlocksReady);
   await page.locator('[data-route="lobby"]').first().click();
   await page.locator('#lobby-create').click();
   await page.locator('#game-mode').selectOption('hotseat');
   await page.locator('#start-game').click();
   await page.waitForSelector('#game:not(.hidden)');
   await page.waitForFunction(()=>window.__LEAF_DICE_FALL__.originalRollTable(6),null,{timeout:15000});
   const table=await page.evaluate(()=>{const t=window.__LEAF_DICE_FALL__.originalRollTable(6);
    return {fall:t.fall.frames.map(f=>f.block+':'+f.index),impact:t.impact.frames.map(f=>f.block+':'+f.index)}});
   const trace=await page.evaluate(async()=>{
    const T=window.__ROG_TEST__,m=T.getMatch();m.players[0].team=['c_0040'];m.players[1].team=['c_0063'];T.drawGame();
    const log=[];const t0=performance.now();let stop=false;
    const tick=()=>{const s=document.getElementById('battle-visual');
     if(s){log.push({t:Math.round(performance.now()-t0),phase:s.dataset.battlePhase||'',
      dice:[...s.querySelectorAll('.battle-visual-die.battle-die-has-original')].map(d=>({eye:d.dataset.eye,f:d.dataset.rollFrame||'',st:d.dataset.battleRoll||''})),
      totals:[...s.querySelectorAll('.battle-visual-total')].map(t=>getComputedStyle(t).visibility),
      poses:Object.fromEntries([...s.querySelectorAll('.leaf-battle-chessman')].map(a=>[a.dataset.duelSide,a.dataset.actorPose])),
      nativeAttackFrame:s.querySelector('.leaf-battle-chessman[data-duel-side="attacker"]')?.dataset.actorFrame||'',
      nativeAttackSequence:s.querySelector('.leaf-battle-chessman[data-duel-side="attacker"]')?.dataset.sourceFrameSequence||'',
      lungeMs:Number(s.querySelector('.leaf-battle-chessman[data-duel-side="attacker"]')?.dataset.sourceNativeDurationMs)||0,
      clipped:[...s.querySelectorAll('.battle-die-original')].some(i=>{const r=i.getBoundingClientRect();return r.width>0&&(r.left<0||r.right>innerWidth||r.top<0||r.bottom>innerHeight)})})}
     if(!stop)requestAnimationFrame(tick)};
    requestAnimationFrame(tick);
    T.resolveBattle(m.players[0],m.players[1],false);
    // Chromium usually finishes within 5.2s; WebKit may need longer to
    // paint every recovered OBS collision key before its full native lunge.
    // A fixed 5.2s trace cut off a valid outcome at ~5.3s and misreported
    // that as an early-result animation defect. Wait for the ACTUAL outcome,
    // preserving all strict frame-order and lunge-duration assertions below.
    await new Promise(resolve=>{
     const deadline=performance.now()+20000;
     const poll=()=>{
      const stage=document.getElementById('battle-visual');
      if(stage?.dataset.battlePhase==='outcome'||performance.now()>deadline){resolve();return}
      setTimeout(poll,40);
     };
     poll();
    });
    await new Promise(r=>setTimeout(r,100));
    stop=true;return log});
   // per-die frame order
   const dieCount=trace.find(x=>x.dice.length)?.dice.length||0;
   assert.ok(dieCount>0,name+' battle dice rendered');
   const perDie=[...Array(dieCount)].map((_,i)=>{const seq=[];for(const x of trace){const f=x.dice[i]?.f;if(f&&seq.at(-1)!==f)seq.push(f)}return {eye:trace.at(-1).dice[i].eye,seq}});
   for(const [i,d] of perDie.entries()){
    const stage=f=>f.startsWith('20:')?0:f.startsWith('12:')?1:f.startsWith('face:')?2:9;
    const order=d.seq.map(stage);
    assert.ok(order.every((v,k)=>k===0||v>=order[k-1]),name+' die '+i+' fall->impact->face order '+d.seq.join(' '));
    assert.ok(!order.includes(9),name+' die '+i+' only source frames');
    assert.ok(d.seq.filter(f=>f.startsWith('20:')).every(f=>table.fall.includes(f.slice(3))),name+' die '+i+' slot-20 frames');
    assert.ok(d.seq.filter(f=>f.startsWith('12:')).every(f=>table.impact.includes(f.slice(3))),name+' die '+i+' slot-12 frames');
    assert.ok(d.seq.filter(f=>f.startsWith('12:')).length>=8,name+' die '+i+' plays the impact keys');
    assert.equal(d.seq.at(-1),'face:'+(Number(d.eye)-1),name+' die '+i+' lands on its VERIFIED face');
   }
   const firstScored=trace.find(x=>x.phase==='scored'||x.phase==='attack');
   const firstAttack=trace.find(x=>x.poses.attacker==='attack');
   const firstOutcome=trace.find(x=>x.phase==='outcome');
   const rolling=trace.filter(x=>x.phase==='dice');
   assert.ok(rolling.length>5,name+' a visible rolling phase');
   assert.ok(rolling.every(x=>x.totals.every(v=>v==='hidden')),name+' totals hidden while rolling');
   assert.ok(rolling.every(x=>x.poses.attacker==='idle'),name+' attacker waits while dice roll');
   assert.ok(firstScored&&firstScored.totals.every(v=>v==='visible'),name+' totals shown on landing');
   assert.ok(firstAttack&&firstAttack.t>=rolling.at(-1).t,name+' lunge after landing');
   // Source timing begins at the pose call, but this trace observes the
   // FIRST visible attack at requestAnimationFrame. A throttled landscape
   // WebKit paint can be observed 50ms late. Verify the ACTUAL last native
   // frame and allow an 80ms first-paint measurement uncertainty, rather
   // than rejecting a fully-rendered source sequence on timestamp alone.
   const nativeKeys=(firstAttack?.nativeAttackSequence||'').split(',').filter(Boolean);
   const finalKey=nativeKeys.at(-1);
   assert.ok(nativeKeys.length>1&&finalKey,name+' real CHR attack source sequence');
   assert.ok(trace.some(x=>x.phase==='attack'&&x.nativeAttackFrame===finalKey),
    name+' original last CHR attack frame '+finalKey+' visible before outcome');
   const visibleMs=firstOutcome?.t-firstAttack?.t;
   const minimum=Math.max(900,firstAttack.lungeMs-80);
   assert.ok(firstOutcome&&visibleMs>=minimum,
    name+' original full lunge with WebKit first-paint tolerance '+JSON.stringify({
     attackAt:firstAttack.t,outcomeAt:firstOutcome?.t,visibleMs,
     nativeMs:firstAttack.lungeMs,minimum,finalKey}));
   assert.ok(!trace.some(x=>x.clipped),name+' no roll frame leaves the viewport');
   const rec={view:name,dice:dieCount,rollMs:rolling.at(-1).t-rolling[0].t,attackAt:firstAttack.t,outcomeAt:firstOutcome.t,
    lungeMs:firstAttack.lungeMs,perDie:perDie.map(d=>({eye:d.eye,frames:d.seq.length,first:d.seq[0],last:d.seq.at(-1)}))};
   // bot-only battle: auto-confirm after landing
   const bot=await page.evaluate(async()=>{
    const T=window.__ROG_TEST__;document.querySelector('.leaf-native-battle-actions button')?.click();
    await new Promise(r=>setTimeout(r,400));
    const m=T.getMatch();m.players.forEach(p=>{p.bot=true});m.players[0].team=['c_0040'];m.players[1].team=['c_0063'];T.setMatch(m);
    let landedAt=null,removedAt=null;const t0=performance.now();
    const p=T.resolveBattle(m.players[0],m.players[1],false);
    while(performance.now()-t0<8000){const s=document.getElementById('battle-visual');
     if(s&&s.dataset.battleDice==='landed'&&landedAt===null)landedAt=performance.now()-t0;
     if(!s&&landedAt!==null){removedAt=performance.now()-t0;break}
     await new Promise(r=>setTimeout(r,30))}
    await p;return {landedAt:Math.round(landedAt),removedAt:Math.round(removedAt)}});
   assert.ok(bot.landedAt>0&&bot.removedAt>bot.landedAt,name+' bot battle confirms only after landing '+JSON.stringify(bot));
   assert.ok(bot.removedAt-bot.landedAt>=900+600,name+' bot battle shows the full lunge and the outcome '+JSON.stringify(bot));
   rec.botAutoConfirm=bot;
   await page.screenshot({path:'r14-battle-roll-'+name+'-'+engine+'.png'}).catch(()=>{});
   assert.deepEqual(errors,[]);
   out.views.push(rec);console.log(JSON.stringify(rec));
   await ctx.close();
  }
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(out,null,1)+'\n');
  console.log('R14 BATTLE ORIGINAL ROLL PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('R14 BATTLE ORIGINAL ROLL FAILED',e.stack||e);process.exit(1)});
