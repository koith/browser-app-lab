'use strict';
/* Every chessman slot must use the same CHR.pak offset+260 body source as the
 * board and duel. Source-verified original pixels or the card's own authentic
 * fallback are allowed. Never conflate CardData 0NNN with OBS 1NNN.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',err=>errors.push(err.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
   window.__LEAF_CHR_BODY_MAP__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const census=await page.evaluate(()=>{
   const map=window.__LEAF_CHR_BODY_MAP__;
   const ids=Object.keys(map.cards);
   return {total:ids.length,published:ids.filter(id=>!!map.resolve(id)).length,
    uniqueNewMembers:new Set(ids.map(id=>map.lookup(id).originalMember).filter(Boolean)).size,
    missing:map.getState().missingOriginalMembers};
  });
  assert.equal(census.total,98);
  assert.equal(census.published,78);
  assert.equal(census.uniqueNewMembers,97);
  assert.deepEqual(census.missing,['0156']);
  const cases=[
   ['0056','OBS.pak/1040.obs','1040',25,true],
   ['0059','OBS.pak/1042.obs','1042',25,true],
   ['0060','OBS.pak/1043.obs','1043',25,true],
   ['0062','OBS.pak/1045.obs','1045',18,true],
   ['0088','OBS.pak/1071.obs','1071',25,true],
   ['0125','OBS2.pak/1199.obs','1199',25,false],
   ['0170','OBS3.pak/1267.obs','1267',34,false],
   ['0040','OBS.pak/1025.obs',null,null,false],
   ['0156',null,null,null,false],
  ];
  const report=[];
  for(const [card,body,shown,frame,visuallyReviewed] of cases){
   const sample=await page.evaluate(card=>{
    const test=window.__ROG_TEST__,match=test.getMatch();
    match.active=0;match.players[0].team=['c_'+card,'c_0059','c_0060'];
    test.setMatch(match);
    const slot=document.querySelector('#dice-native-party .dice-chessman-slot.occupied');
    const img=slot?.querySelector('img.dice-chessman-face');
    const original=window.__LEAF_CHR_BODY_MAP__;
    const m=original.lookup(card),source=original.resolve(card);
    const visualKey=original.assetKey(card);
    const audit=window.__LEAF_GENESIS_ACTORS__.getState().originalFrontVisualAudited;
    const idx=visualKey&&Object.hasOwn(audit,visualKey)?audit[visualKey]:null;
    const originalFrame=idx===null?
     window.__LEAF_NATIVE_CARD_ACTIONS__.frontFrame(source,card):
     source?.frames?.find(f=>f.index===idx);
    const expected=originalFrame?.url||null;
    return {card,observedCard:slot?.dataset.cardId,
     originalChrBody:slot?.dataset.originalChrBody,
     sourceAvailability:slot?.dataset.chrBodySource,
     art:slot?.dataset.sourceCardArtwork,source:slot?.dataset.rightPortraitSource,
     image:img?.getAttribute('src'),originalMember:img?.dataset.originalMember,
     frame:img?.dataset.nativeFrontFrame,
     approved:slot?.dataset.rightPortraitFacingEvidence,
     expected,lookup:m?.originalMember||null,published:!!source};
   },card);
   assert.equal(sample.observedCard,'c_'+card,JSON.stringify(sample));
   assert.equal(sample.lookup,body,card+' CHR membership');
   assert.equal(sample.originalChrBody,body||
    (card==='0156'?'CHR-body-missing':'CHR-body-unverified'));
   if(shown){
    assert.equal(sample.sourceAvailability,'published-and-hash-gated');
    assert.equal(sample.source,visuallyReviewed?
     'OBS.pak/verified-front':'CHR-OBS/native-keyframe-role-inferred',
     JSON.stringify(sample));
    assert.equal(sample.approved,visuallyReviewed?'visually-reviewed':
     'original-18-byte-frame-index-VERIFIED/orientation-INFERRED',card);
    assert.equal(sample.frame,String(frame),card);
    assert.equal(sample.originalMember,body,card);
    assert.equal(sample.image,sample.expected,card);
    const sourceFilename=visuallyReviewed?
     shown+'-'+frame+'.png':
     (body.startsWith('OBS2')?'obs2-':'obs3-')+
      shown+'-'+String(frame).padStart(3,'0')+'.png';
    assert.ok(sample.image.endsWith('/'+sourceFilename),JSON.stringify(sample));
   }else{
    assert.ok(!sample.image?.includes('/OBS/'),JSON.stringify(sample));
    assert.equal(sample.image,sample.art,'same card artwork, no unrelated OBS');
    assert.notEqual(sample.source,'OBS.pak/verified-front',card);
    assert.equal(sample.sourceAvailability,sample.published?
     'published-and-hash-gated':'original-body-unpublished-or-unavailable');
   }
   report.push({card,body,display:sample.source,image:sample.image});
  }
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#dice-native-party .dice-chessman-slot.occupied img')]
   .every(img=>img.complete&&img.naturalWidth>0),null,{timeout:18000});
  assert.deepEqual(errors,[]);
  console.log('CHR ORIGINAL 98-CARD PARTY HUD SOURCE IDENTITY PASS',
   JSON.stringify({census,report}));
 }finally{await browser.close()}
})().catch(error=>{
 console.error('CHR ORIGINAL PARTY HUD IDENTITY FAILED',error.stack||error);
 process.exit(1);
});