'use strict';
/* Card portrait integrity, source-own-body audit 2026-11-09.
 * None of the 2002 CardData/chm_N face mappings have confirmed CHR IDs.
 * Require exact owned CHR source frame 0, or original IMG cardback for 0156.
 * This does not claim a historical CardData facial-to-CHR mapping. */
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
  assert.equal(rows.length,98,'genuine full CHR roster including missing 0156');
  const mapped=await page.evaluate(()=>Object.fromEntries(
   (window.ORIGINAL_LEAF_CHESSMEN||[]).map(card=>
    [card.id,window.__LEAF_CHR_BODY_MAP__?.resolve?.(card.id)
     ?.frames?.find(frame=>frame.index===0)?.url||null])));
  const sourceOwners=new Map();
  for(const r of rows){
   const exact=mapped[r.id],expected=exact||'./original/IMG/avatarback.png';
   assert.equal(r.src,expected,r.id+' card source must match its own original CHR member');
   assert.ok(!r.src.includes('/CardData/chm_'),r.id+' unsourced CardData face is forbidden');
   assert.equal(r.evidence,exact?
    'verified-CHR-own-body-not-CardData-portrait':'no-verified-CardData-portrait');
   if(exact){const owners=sourceOwners.get(r.src)||[];owners.push(r.id);
    sourceOwners.set(r.src,owners);}
  }
  assert.equal(sourceOwners.size,97,'97 unique original source-owned body thumbnail URLs');
  assert.deepEqual([...sourceOwners].filter(([,ids])=>ids.length>1),[],
   'each original body frame may belong to only one CHR card');
  assert.deepEqual(rows.filter(r=>r.src==='./original/IMG/avatarback.png').map(r=>r.id),
   ['0156'],'no fake body for absent OBS2/1222 source');
  assert.deepEqual(errors,[]);
  console.log('CARD PORTRAIT CHR OWN-MEMBER SOURCE INTEGRITY PASS',JSON.stringify({
   cards:rows.length,verifiedBodyCards:sourceOwners.size,missing:['0156']}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
