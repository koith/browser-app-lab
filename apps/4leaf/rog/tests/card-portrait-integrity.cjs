'use strict';
/* Card portrait integrity (audit 2026-11-01).
 * Checks a property of the RENDERED result, not a provenance label:
 *  1. no CardData face is shown for two different characters;
 *  2. the removed (sourceId%59)+1 formula can never come back silently;
 *  3. cards with no sourced portrait show the original IMG.pak card back.
 * Passing this does NOT mean portraits are correct: the 7 legacy entries are
 * unsourced until the CHR record dump provides a real portrait field. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__ROG_TEST__.imageFor);
  const rows=await page.evaluate(()=>{
   const T=window.__ROG_TEST__;
   return (window.ORIGINAL_LEAF_CHESSMEN||[]).map(c=>({id:c.id,name:c.name,
    src:T.imageFor('c_'+c.id),evidence:T.portraitEvidence('c_'+c.id)}));
  });
  assert.ok(rows.length>=90,'original CHR roster loaded');
  const byFace=new Map();
  for(const r of rows){
   if(!r.src.includes('/CardData/'))continue;
   const owners=byFace.get(r.src)||[];owners.push(r.id);byFace.set(r.src,owners);
  }
  const shared=[...byFace].filter(([,ids])=>ids.length>1);
  assert.deepEqual(shared,[],'one CardData face must not be shown for two characters');
  for(const r of rows){
   const formula='./original/CardData/chm_'+((Number(r.id)%59)+1)+'.png';
   if(r.evidence==='none')assert.equal(r.src,'./original/IMG/avatarback.png',
    r.id+' has no sourced portrait and must show the original card back');
   if(r.evidence==='none')assert.notEqual(r.src,formula,r.id+' uses the removed formula');
  }
  const legacy=rows.filter(r=>r.evidence!=='none').map(r=>r.id);
  assert.ok(legacy.length<=7,'legacy unsourced portraits may only shrink: '+legacy);
  assert.deepEqual(errors,[]);
  console.log('CARD PORTRAIT INTEGRITY PASS',JSON.stringify({roster:rows.length,
   legacyUnsourced:legacy,neutral:rows.length-legacy.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
