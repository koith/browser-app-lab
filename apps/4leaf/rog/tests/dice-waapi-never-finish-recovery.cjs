'use strict';
/* Browser regression: Web Animations can be indefinitely suspended by
 * background tabs or WebKit/PWA. The visual die must NEVER freeze actual
 * player turns. Simulator rejects no source sprites and fixes no die rolls:
 * only the WAAPI Animation.finished promises remain forever pending.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await browserType.launch({headless:true,args:browserType===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__&&window.__ROG_TEST__);
  const result=await page.evaluate(async()=>{
   const api=window.__LEAF_DICE_FALL__,before=api.getState(),original=Element.prototype.animate;
   let cancellations=0,simulated=0;
   Element.prototype.animate=function(...args){
    if(this.classList.contains('leaf-fall-piece')||this.classList.contains('leaf-fall-cube')){
     simulated++;
     return {finished:new Promise(()=>{}),cancel(){cancellations++}};
    }
    return original.apply(this,args);
   };
   const start=performance.now();
   try{
    const result=await Promise.race([
     api.roll([2,4],{sides:[6,4]}),
     new Promise((_,reject)=>setTimeout(()=>reject(Error('Original turn blocked by WAAPI forever')),6500))
    ]);
    return {result,duration:performance.now()-start,simulated,cancellations,
     before:before.complete,after:api.getState(),layer:document.querySelector('#leaf-dice-fall-layer')?.dataset.phase};
   }finally{Element.prototype.animate=original}
  });
  assert.deepEqual(result.result,[2,4],'same authoritative D6/D4 results, even with frozen animations');
  assert.ok(result.duration>950&&result.duration<6200,'presentation safeguard must be bounded: '+JSON.stringify(result));
  assert.equal(result.simulated,4,'both drop and spin of two actual dice were suspended');
  assert.equal(result.cancellations,4,'all suspended WAAPI animations must be explicitly cancelled');
  assert.equal(result.after.active,false,'subsequent real dice rolls cannot be blocked');
  assert.deepEqual(result.after.last,[2,4]);
  assert.deepEqual(result.after.lastSides,[6,4]);
  assert.equal(result.after.complete,result.before+1);
  assert.equal(result.layer,'idle');
  // A subsequent ordinary D6 roll must still be available and have correct
  // original landing face values after the watchdog path completed.
  const again=await page.evaluate(async()=>{
   const api=window.__LEAF_DICE_FALL__,next=await api.roll([5],{sides:6});
   return {next,state:api.getState()};
  });
  assert.deepEqual(again.next,[5]);
  assert.equal(again.state.active,false);
  assert.deepEqual(again.state.last,[5]);
  assert.equal(again.state.complete,result.after.complete+1);
  assert.deepEqual(errors,[]);
  console.log('4LEAF_WAAPI_NEVER_FINISHES_REAL_DICE_RECOVERY_PASS',JSON.stringify({
   browser:browserType.name(),elapsedMs:Math.round(result.duration),animations:result.simulated,
   cancelled:result.cancellations,authoritativeRolls:[result.result,again.next],reusable:true
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_WAAPI_NEVER_FINISHES_REAL_DICE_RECOVERY_FAIL',e.stack||e);process.exit(1)});
