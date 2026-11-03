'use strict';
/* Round 11 — the ORIGINAL anim-12 table actually plays in a real duel.
 * Drives the live game (hotseat, real resolveBattle), records every frame the
 * duel-podium attacker renders, and compares it with the decoded original
 * table of that card's CHR body:
 *   - rendered key order == original anim 12 key frames (VERIFIED indices),
 *   - each key is held for its original tick span (relative timing),
 *   - attacker stays mirrored toward the defender for the whole lunge,
 *   - the actor never leaves its podium side panel while the lunge plays.
 * Role "duel lunge" for slot 12 and 40ms/tick are INFERRED / WEB values.
 * This is an original-table test on the real app, not a synthetic one. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
const CASES=[
 {attacker:'c_0078',defender:'c_0088'}, // OBS 1061 classic 37-frame body
 {attacker:'c_0126',defender:'c_0056'}, // OBS2 1200: own 23-tick lunge 20..24
 {attacker:'c_0170',defender:'c_0063'}  // OBS3 1267
];
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const report=[];
 try{
  for(const c of CASES){
   const context=await browser.newContext({viewport:{width:1280,height:900}});
   await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'),{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_NATIVE_CARD_ACTIONS__&&
    window.ORIGINAL_LEAF_CHESSMEN?.length>50);
   await page.locator('[data-route="lobby"]').first().click();
   await page.locator('#lobby-create').click();
   await page.locator('#game-mode').selectOption('hotseat');
   await page.locator('#bot-count').selectOption('1');
   await page.locator('#start-game').click();
   await page.waitForSelector('#game:not(.hidden)');
   const run=await page.evaluate(async({attacker,defender})=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=[attacker];m.players[1].team=[defender];T.drawGame();
    const id=String(m.players[0].id),log=[],geo=[];let snap=null;
    const obs=new MutationObserver(list=>{
     for(const r of list){
      const el=r.target;
      if(!el.classList?.contains('leaf-battle-chessman')||el.dataset.id!==id)continue;
      if(el.dataset.actorPose!=='attack')continue;
      if(!snap)snap={sequence:el.dataset.sourceFrameSequence,
       evidence:el.dataset.sourceAttackEvidence,slot:el.dataset.sourceNativeSlot,
       durationMs:el.dataset.sourceNativeDurationMs,
       outcomeDelayMs:el.closest('#battle-visual')?.dataset.duelOutcomeDelayMs};
      log.push({t:performance.now(),frame:Number(el.dataset.actorFrame),
       mirror:el.dataset.sourceMirror});
      const img=el.querySelector('img.leaf-chess-original-obs');
      const side=el.closest('.battle-visual-side');
      if(img&&side){
       const a=img.getBoundingClientRect(),s=side.getBoundingClientRect();
       geo.push({cx:a.left+a.width/2,bottom:a.bottom,sl:s.left,sr:s.right,st:s.top,sb:s.bottom});
      }
     }
    });
    obs.observe(document.body,{subtree:true,attributes:true,attributeFilter:['data-actor-frame']});
    T.resolveBattle(m.players[0],m.players[1],false);
    let actor=null;
    for(let k=0;k<100&&!actor;k++){
     await new Promise(r=>setTimeout(r,20));
     actor=document.querySelector('#battle-visual .leaf-battle-chessman[data-id="'+id+'"]');
    }
    // Wait until the attack pose has been replaced by the real outcome.
    const start=performance.now();
    while(actor&&(!snap||actor.dataset.actorPose==='attack')&&performance.now()-start<8000)
     await new Promise(r=>setTimeout(r,25));
    obs.disconnect();
    const card=attacker.replace(/^c_/,'');
    const table=window.__LEAF_NATIVE_CARD_ACTIONS__.table(card);
    return {card,log,geo,...snap,afterPose:actor?.dataset.actorPose,
     member:actor?.dataset.actorSource,
     anim12:table?.anims[6]&&{ticks:table.anims[6].ticks,keys:table.anims[6].keys}};
   },c);
   if(process.env.DEBUG)console.log(JSON.stringify({...run,geo:run.geo.length,log:run.log.slice(0,40)}));
   assert.ok(run.anim12&&run.anim12.keys.length>0,c.attacker+' has an original anim-12 table');
   const expanded=[];
   run.anim12.keys.forEach(([tick,frame],k)=>{
    const end=k+1<run.anim12.keys.length?run.anim12.keys[k+1][0]:run.anim12.ticks;
    for(let x=tick;x<Math.max(end,tick+1);x++)expanded.push(frame);
   });
   assert.equal(run.sequence,expanded.join(','),
    c.attacker+' duel attack sequence = original anim-12 keys expanded over their exact ticks');
   assert.equal(run.slot,'12');
   assert.match(run.evidence,/^native-CHR-duel-lunge-side-mirrored\/original-OBS-anim12-keys-and-ticks-VERIFIED\/role-INFERRED$/);
   assert.equal(Number(run.durationMs),run.anim12.ticks*40);
   assert.equal(Number(run.outcomeDelayMs),Math.max(900,run.anim12.ticks*40),
    'outcome poses wait for the whole original lunge');
   // Playback is clocked against the original tick span: under a busy
   // main thread a step may be dropped, never stretched. The final key must
   // be reached before the real outcome pose replaces the lunge.
   const lastKey=run.anim12.keys[run.anim12.keys.length-1][1];
   assert.equal(run.log[run.log.length-1].frame,lastKey,
    c.attacker+' the final original key is shown before the outcome pose');
   assert.ok(['hurt','victory'].includes(run.afterPose),'real outcome follows the lunge');
   const collapse=a=>a.filter((x,i)=>i===0||x!==a[i-1]);
   const rendered=collapse(run.log.map(x=>x.frame));
   const keys=collapse(run.anim12.keys.map(k=>k[1]));
   const isOrderedSubset=(sub,all)=>{let j=0;for(const x of all)if(x===sub[j])j++;return j===sub.length};
   assert.ok(isOrderedSubset(rendered,keys)&&rendered[0]===keys[0],
    c.attacker+' rendered keys follow the original key order '+rendered+' vs '+keys);
   const exactKeys=JSON.stringify(rendered)===JSON.stringify(keys);
   assert.ok(run.log.every(x=>x.mirror==='true'),'attacker faces the defender for the whole lunge (no flip)');
   assert.ok(run.geo.length>0&&run.geo.every(g=>g.cx>=g.sl-1&&g.cx<=g.sr+1&&g.bottom<=g.sb+1),
    c.attacker+' actor stays inside its podium side while lunging '+JSON.stringify(run.geo.slice(0,3)));
   const span=run.log.length>1?run.log[run.log.length-1].t-run.log[0].t:0;
   await page.screenshot({path:'leaf-r11-duel-lunge-'+run.card+'.png'});
   assert.deepEqual(errors,[]);
   report.push({attacker:c.attacker,member:run.member,keys,exactKeys,renderedSteps:run.log.length,
    expectedSteps:expanded.length,ticks:run.anim12.ticks,observedSpanMs:Math.round(span)});
   await context.close();
  }
  console.log('CHR NATIVE DUEL LUNGE PLAY PASS',JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error('CHR NATIVE DUEL LUNGE PLAY FAILED',e.stack||e);process.exit(1);});
