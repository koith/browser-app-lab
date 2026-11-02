'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_GENESIS_ACTORS__&&window.ORIGINAL_LEAF_EXT_ACTION_FRAMES?.['0042']?.frames.length===37);
  const result=await page.evaluate(()=>{
   const api=window.__LEAF_GENESIS_ACTORS__;
   const mount=id=>{
    const p=document.createElement('div');p.className='board-pawn';
    document.body.append(p);
    api.mount(p,{team:['c_'+id]},'./icon.svg');
    return p;
   };
   const a=mount('0059'),b=mount('0062'),c=mount('0087');
   const idle42=a.dataset.sourceFrameSequence;
   api.pose(a,'walk');
   const walk42=a.dataset.sourceFrameSequence;
   const src42=a.querySelector('img.leaf-chess-original-obs')?.getAttribute('src');
   const idle45=b.dataset.sourceFrameSequence;
   api.pose(b,'walk');
   const walk45=b.dataset.sourceFrameSequence;
   const src45=b.querySelector('img.leaf-chess-original-obs')?.getAttribute('src');
   const src87=c.querySelector('img.leaf-chess-original-obs')?.getAttribute('src');
   return {idle42,walk42,src42,idle45,walk45,src45,src87};
  });
  assert.equal(result.idle42,'22,23,24');
  assert.equal(result.walk42,'25,26,27,28,29,30');
  assert.ok(result.src42.includes('action-full-ext/1042-25.png'));
  assert.equal(result.idle45,'22,23,24');
  assert.equal(result.walk45,'25,26,27,28,29,30');
  assert.ok(result.src45.includes('action-full-ext/1045-25.png'));
  assert.ok(!String(result.src87).includes('action-full-ext/'));
  console.log('4LEAF EXTENDED ORIGINAL RUNTIME PASS',JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
