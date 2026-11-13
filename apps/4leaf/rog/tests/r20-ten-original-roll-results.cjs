'use strict';
/* Live Chromium/WebKit: original block-0 fall (slot 20) and own-palette
 * impact (slot 12) followed by verified original final pip face.
 * Original frame indices/ticks VERIFIED; mapping fall/impact and ms INFERRED.
 * No dice roll result or match-state mutation is allowed.
 */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_FALL__&&window.ORIGINAL_LEAF_DICE_BLOCKS);
  const verified=await page.evaluate(()=>window.__LEAF_DICE_FALL__.diceBlocksReady);
  assert.deepEqual(verified,{'1171':true,'1223':true},
   'both original D6/D4 block SHA-256 sets must pass');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const before=await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch()));
  const report={};
  for(const [sides,result] of [...Array.from({length:4},(_,i)=>[4,i+1]),...Array.from({length:6},(_,i)=>[6,i+1])]){
   const out=await page.evaluate(async({sides,result})=>{
    const table=window.__LEAF_DICE_FALL__.originalRollTable(sides);
    if(!table)return {failure:'no native original table '+sides};
    const log=[];
    const observe=new MutationObserver(()=>{
     const piece=document.querySelector('#leaf-dice-fall-layer .leaf-fall-piece');
     const img=piece?.querySelector('img');
     if(img)log.push({phase:piece.dataset.rollPhase||'',frame:img.dataset.frame||'',url:img.getAttribute('src')});
    });
    observe.observe(document.body,{subtree:true,attributes:true,attributeFilter:['src','data-frame']});
    let piece=null;
    const watch=setInterval(()=>{piece=document.querySelector('#leaf-dice-fall-layer .leaf-fall-piece')||piece},5);
    let values;
    try{values=await window.__LEAF_DICE_FALL__.roll([result],{sides})}
    finally{clearInterval(watch);observe.disconnect()}
    const face=(sides===4?window.__LEAF_DICE_FALL__.originalD4():
     window.__LEAF_DICE_FALL__.originalD6()).faces[result-1];
    return {values,log,face:face.url,
     tumble:piece?.dataset.tumbleSource,role:piece?.dataset.rollTableRole,
     fall:table.fall.frames.map(f=>f.block+':'+f.index),
     impact:table.impact.frames.map(f=>f.block+':'+f.index),
     member:table.member,sounds:table.impact.sounds};
   },{sides,result});
   assert.ok(!out.failure,JSON.stringify(out));
   assert.deepEqual(out.values,[result],'original animation must not modify engine result');
   assert.equal(out.tumble,'original-OBS-'+out.member+'/slot20-fall+slot12-impact');
   assert.match(out.role,/frames-and-ticks-VERIFIED\/fall-impact-role-INFERRED\/ms-UNVERIFIED/);
   const falls=out.log.filter(x=>x.phase==='fall/slot20'&&x.frame.includes(':')).map(x=>x.frame);
   const impacts=out.log.filter(x=>x.phase==='impact/slot12'&&x.frame.includes(':')).map(x=>x.frame);
   const ordered=(seen,ref)=>{let i=0;for(const val of seen){while(i<ref.length&&ref[i]!==val)i++;if(i===ref.length)return false}return true};
   assert.ok(falls.length>=2,'slot-20 source tumble must render multiple original frames: '+falls);
   assert.ok(falls.every(x=>out.fall.includes(x)),'no unverified source outside slot 20');
   assert.ok(impacts.length>=3&&ordered(impacts,out.impact),
    'slot-12 source impact must progress in original key order: '+impacts);
   assert.equal(impacts.at(-1),out.impact.at(-1),'source impact must reach final original key');
   assert.equal(out.log.at(-1).url,out.face,'die rests on engine-predetermined verified D4/D6 pip face');
   assert.deepEqual(out.sounds,[[1,2125]],'impact 2125 is archived only, NOT guessed audio');
   report['D'+sides+'-'+result]={fallObserved:falls.length,impactObserved:impacts.length};
  }
  assert.equal(Object.keys(report).length,10,'all D4x4 + D6x6 original result faces must be checked');
  assert.equal(await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch())),before,
   'presentation cannot mutate real saved match or RNG');
  const tampered=await page.evaluate(async()=>{
   const m=window.ORIGINAL_LEAF_DICE_BLOCKS.members['1171'];
   const old=m.blocks[0].frames[0].sha256;
   m.blocks[0].frames[0].sha256='0'.repeat(64);
   const script=document.createElement('script');
   script.src='./dice-fall.js?integrity-test='+Date.now();
   await new Promise((resolve,reject)=>{script.onload=resolve;script.onerror=reject;document.head.append(script)});
   const ready=await window.__LEAF_DICE_FALL__.diceBlocksReady;
   const rejected=window.__LEAF_DICE_FALL__.originalRollTable(6)===null;
   m.blocks[0].frames[0].sha256=old;
   return {ready,rejected};
  });
  assert.equal(tampered.ready['1171'],false);
  assert.equal(tampered.rejected,true,'tampered original dice block must be refused');
  assert.deepEqual(errors,[],'source roll must not throw browser errors');
  console.log('R20_ALL_TEN_ORIGINAL_D4_D6_RESULTS_PASS',JSON.stringify({engine:engine.name(),report}));
 }finally{await browser.close()}
})().catch(e=>{console.error('REAL ORIGINAL D4/D6 ROLL TABLE FAILED',e.stack||e);process.exit(1)});
