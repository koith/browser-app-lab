'use strict';
/* ACT-03 acceptance, source limits strict:
 * 97 recovered source-owned CHR animation bodies, 17 original OBS table
 * slots, all directions and actions (including 13-16 unclassified slots).
 * Historical EXE action meaning/FPS is NOT inferred as proven. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const mode=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (mode==='webkit'?webkit:chromium).launch({
  headless:true,args:mode==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_NATIVE_CARD_ACTIONS__&&window.__LEAF_CHR_BODY_MAP__);
  const report=await page.evaluate(()=>{
   const map=window.__LEAF_CHR_BODY_MAP__,api=window.__LEAF_NATIVE_CARD_ACTIONS__;
   const ids=Object.keys(map.cards).sort();
   let verified=0,unclassified=0,held=0,originalKeys=0;
   const failures=[];
   const cases=[['idle','toward',{}],['walk','toward',{}],['walk','away',{}],
    ['walk','left',{}],['walk','right',{}],['attack','toward',{}],
    ['hurt','toward',{}],['victory','toward',{}],
    ['attack','toward',{duel:true,side:'attacker'}],
    ['attack','toward',{duel:true,side:'defender'}],
    ['hurt','toward',{duel:true,side:'defender'}],
    ['victory','toward',{duel:true,side:'attacker'}]];
   for(const id of ids){
    const body=map.resolve(id),table=api.table(id);
    if(id==='0156'){
     if(body||table)failures.push(id+' missing source must not borrow another body');
     continue;
    }
    if(!body||!table||table.anims.length!==17){failures.push(id+' bad source table');continue;}
    const sourceSet=new Set(body.frames);
    const extras=api.sourceExtraSlots(id);
    if(!extras||extras.length!==4||extras.some(x=>x.role!=='UNVERIFIED/NO_ORIGINAL_ACTION_NAME'))
     failures.push(id+' fabricated 13-16 outcome role');
    else unclassified+=4;
    for(const [action,travel,context] of cases){
     const seq=api.sequenceFor(body,id,action,travel,context);
     if(!seq){
      failures.push(id+'/'+action+'/'+travel+' no original source-safe stance');
      continue;
     }
     if(!seq.every(x=>sourceSet.has(x)))
      failures.push(id+'/'+action+' foreign actor source frame');
     if(!seq.nativeEvidence||!/(?:INFERRED|UNVERIFIED)/.test(seq.nativeEvidence))
      failures.push(id+'/'+action+' poses claim historic action evidence');
     if(!String(seq.nativeMilliseconds).includes('UNVERIFIED'))
      failures.push(id+'/'+action+' timing falsely source-verified');
     if(!String(seq.nativeEffects).includes('UNVERIFIED'))
      failures.push(id+'/'+action+' EXE effects falsely source-verified');
     if(seq.nativeSlot==='none'||seq.nativeSlot==='empty')held++;
     originalKeys+=seq.length;
     verified++;
    }
   }
   return {cards:ids.length,sourceBodies:ids.filter(id=>map.resolve(id)).length,
    missing:ids.filter(id=>!map.resolve(id)),actions:verified,unclassified,
    held,verifiedOriginalFrames:originalKeys,
    chronology:api.getState(),failures};
  });
  assert.equal(report.cards,98);
  assert.equal(report.sourceBodies,97);
  assert.deepEqual(report.missing,['0156']);
  assert.equal(report.unclassified,388,'97 x 4 source slots retained as UNVERIFIED');
  assert.equal(report.actions,97*12,'all recovered body and action candidates use own original frames');
  assert.deepEqual(report.failures,[]);
  assert.equal(report.chronology.tableBodies,97);
  assert.equal(report.chronology.originalKeysAndTicks,'VERIFIED');
  assert.equal(report.chronology.outcomeRole,'INFERRED/WEB-only');
  assert.equal(report.chronology.originalTickMilliseconds,'UNVERIFIED');
  assert.deepEqual(errors,[]);
  console.log('R25_ORIGINAL_97_ACTORS_12_ACTION_CASES_SOURCE_SAFE_PASS',JSON.stringify({
   mode,actors:report.sourceBodies,actionCases:report.actions,
   sourceFrameReferences:report.verifiedOriginalFrames,unclassifiedNativeSlots:report.unclassified,
   sourceEmptyHolds:report.held,actualEXEOriginalPoseSemantics:'UNVERIFIED'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R25_ACT03_SOURCE_SAFETY_FAIL',e.stack||e);process.exit(1)});
