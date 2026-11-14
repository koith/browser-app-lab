'use strict';
/* 2013 preservation of original 2002 4LEAF chessman rarity names:
 * 61 Normal + 36 Valuable, 97 independently posted archive records.
 * CHR 0156/OBS2 1222 is unverified, NEVER guesses from a score.
 * All categorized cards retain independent Naver source article URLs.
 * Actual 2002 EXE category byte not recovered; source labels state archive. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {chromium,webkit}=require('playwright');
const root=path.resolve(__dirname,'..');
const text=fs.readFileSync(path.join(root,'original/historical-chessman-ranks.js'),'utf8');
const sandbox={window:{}};
vm.runInNewContext(text,sandbox);
const original=sandbox.window.ORIGINAL_LEAF_HISTORIC_RARITIES;
const ranks=original.cards;
assert.equal(original.counts.sourcePosts,97);
assert.equal(original.counts.chrRecords,98);
assert.equal(Object.keys(ranks).length,97);
const hist=Object.values(ranks);
assert.equal(hist.filter(x=>x.rank==='normal').length,61);
assert.equal(hist.filter(x=>x.rank==='valuable').length,36);
assert.equal(new Set(hist.map(x=>x.source)).size,97);
const archiveRoster=JSON.parse(fs.readFileSync(path.join(root,'original/chessmen.json'),'utf8'));
for(const c of archiveRoster){
 const entry=ranks[c.id];
 if(c.id==='0156'){assert.equal(entry,undefined);continue}
 assert.ok(entry,'missing archived card '+c.id);
 assert.equal(entry.chrName,c.name);
 assert.ok(['normal','valuable'].includes(entry.rank));
 assert.match(entry.source,/^https:\/\/blog\.naver\.com\/kimmin9296\/\d+$/);
 assert.ok(['EXACT','ORTHOGRAPHIC-NORMALIZED','ALIAS-REVIEWED'].includes(entry.sourceMatch));
}
const legacyGuess=archiveRoster.filter(c=>ranks[c.id]&&
 (c.score>=175?'valuable':'normal')!==ranks[c.id].rank);
assert.ok(legacyGuess.length>=12,'source records must fix measurable score-threshold misclassification');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SHOP_ERA__&&window.ORIGINAL_LEAF_HISTORIC_RARITIES);
  await page.locator('[data-route="shop"]').first().click();
  await page.waitForSelector('#shop:not(.hidden)');
  const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  const sample=await page.locator('#shop-grid .shop-card:not(.shop-empty)').first().getAttribute('data-original-chr');
  assert.ok(sample,'native source row must carry original CHR id');
  async function walkRank(rank,expectedPageSize){
   await page.locator('#shop .group-tab[data-group="'+rank+'"]').click();
   const result=new Map();let pages=0;
   while(pages++<25){
    const items=await page.$$eval('#shop-grid .shop-card:not(.shop-empty)',els=>els.map(e=>({
     id:e.dataset.originalChr,rank:e.dataset.rank,evidence:e.dataset.rankEvidence,
     source:e.dataset.rankSource,sourceOwned:e.dataset.cardId,title:e.title,
     visible:!!e.getBoundingClientRect().width
    })));
    for(const row of items){
     assert.ok(!result.has(row.id),'one source original CHR appears on two pages');
     assert.equal(row.rank,rank);
     assert.ok(ranks[row.id]&&ranks[row.id].rank===rank);
     assert.equal(row.source,ranks[row.id].source);
     assert.ok(row.evidence.endsWith(ranks[row.id].sourceMatch));
     assert.ok(row.title.includes('팬사이트'));
     assert.equal(row.sourceOwned,'c_'+row.id);
     assert.equal(row.visible,true);
     result.set(row.id,row);
    }
    if(await page.locator('#shop-next').isDisabled())break;
    await page.locator('#shop-next').click();
   }
   assert.ok(pages<25);
   assert.ok(pages>=Math.ceil(result.size/expectedPageSize));
   return result;
  }
  const source2002={};
  for(const rank of ['normal','valuable']){
   const rows=await walkRank(rank,9);
   source2002[rank]=rows.size;
  }
  assert.equal(source2002.normal,61);
  assert.equal(source2002.valuable,36);
  await page.locator('#shop .group-tab[data-group="all"]').click();
  const selected=await page.locator('#shop-grid .shop-card:not(.shop-empty)').first();
  await selected.click();
  assert.ok((await page.locator('#shop-selected').textContent()).includes('2013 원본 팬사이트 기록'));
  await page.locator('#shop-era-toggle button[data-era="2004"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card').count(),8);
  const source2004={};
  for(const rank of ['normal','valuable']){
   const rows=await walkRank(rank,8);
   source2004[rank]=rows.size;
  }
  assert.equal(source2004.normal,61);
  assert.equal(source2004.valuable,36);
  await page.locator('#shop .group-tab[data-group="rare"]').click();
  assert.equal(await page.locator('#shop-grid .shop-card:not(.shop-empty)').count(),0);
  assert.equal(await page.locator('#shop-buy').isDisabled(),true);
  // The only original 98th CHR source with missing body/rank must be visible
  // in ALL, never placed in either source-confirmed Normal/Valuable list.
  await page.locator('#shop .group-tab[data-group="all"]').click();
  let missing=null,seen=new Set();
  for(let n=0;n<18;n++){
   const rows=await page.$$eval('#shop-grid .shop-card:not(.shop-empty)',nodes=>nodes.map(e=>({
    id:e.dataset.originalChr,rank:e.dataset.rank,evidence:e.dataset.rankEvidence,
    text:e.title
   })));
   for(const row of rows){
    seen.add(row.id);
    if(row.id==='0156')missing=row;
   }
   if(await page.locator('#shop-next').isDisabled())break;
   await page.locator('#shop-next').click();
  }
  assert.equal(seen.size,98);
  assert.equal(missing.rank,'unverified');
  assert.equal(missing.evidence,'UNVERIFIED-ORIGINAL-CATEGORY');
  assert.ok(missing.text.includes('등급 미확인'));
  const after=await page.evaluate(()=>JSON.parse(localStorage.getItem('rog_profile')));
  assert.equal(after.gp,before.gp);
  assert.deepEqual(after.owned,before.owned);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-r29-original-tier-61-normal-36-valuable-'+engine+'.png'});
  console.log('R29_97_ORIGINAL_RANKS_REAL_SHOP_PASS',JSON.stringify({
   engine,sourceCounts:source2002,era2004Counts:source2004,
   originalPosts:97,archivalRarityVsWrongScoreHeuristic:legacyGuess.length,
   excludedUnverifiedChr:'0156',rareUnissued:0,changedGP:0,
   publication:'2013 FAN ARCHIVE OF 2002, NOT EXE BYTE'}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R29_ORIGINAL_CHESSMAN_RANK_FAILED',e.stack||e);process.exit(1)});
