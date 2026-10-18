'use strict';
/* Source-integrity regression: 26 archival DMP paths exist, 25 have a
 * historical title/associated event records. 0170 is a GENUINE 135-cell
 * route without verified title or event table, not a made-up level. Ensure
 * users can play it without mutating the immutable source metadata.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const pageUrl=process.env.FOURLEAF_TEST_URL||
 'file://'+path.resolve(__dirname,'../index.html');
async function exercise(browser,mobile){
 const context=await browser.newContext({
  viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'
 });
 try{
  const page=await context.newPage(),errors=[];
  page.on('pageerror',err=>errors.push(String(err)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(pageUrl);
  await page.waitForFunction(()=>window.ORIGINAL_LEAF_MAPS&&
   window.ORIGINAL_LEAF_MAP_INFO&&window.__ROG_TEST__&&window.__LEAF_CAMERA__);
  const evidence=await page.evaluate(()=>{
   const paths=window.ORIGINAL_LEAF_MAPS,archival=window.ORIGINAL_LEAF_MAP_INFO,
    live=window.__ROG_TEST__.getSourceMaps();
   return {
    pathCount:Object.keys(paths).length,
    verifiedNames:Object.keys(archival).length,
    source0170Length:paths['0170']?.length,
    archival0170:archival['0170']||null,
    label:live['0170']?.title,
    status:live['0170']?.metadataStatus
   };
  });
  assert.equal(evidence.pathCount,26,'2002 source contains 26 real paths');
  assert.equal(evidence.verifiedNames,25,'do not falsify the source title archive');
  assert.equal(evidence.source0170Length,135,'original unnamed 0170 contains 135 actual DMP cells');
  assert.equal(evidence.archival0170,null,'historical title remains unverified');
  assert.match(evidence.label,/원본 DMP 0170/);
  assert.equal(evidence.status,'ARCHIVE-MAP-PRESENT/TITLE-UNVERIFIED');
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  const options=await page.locator('#map-select option').evaluateAll(list=>
   list.map(x=>({value:x.value,id:x.dataset.originalMapId,
     verified:x.dataset.historicalTitleVerified})));
  const archival=options.filter(x=>x.id&&x.id!=='__RANDOM__');
  assert.equal(archival.length,26,'all 26 true DMP routes must be offered in lobby');
  const target=archival.filter(x=>x.id==='0170');
  assert.equal(target.length,1,'unnamed historical map exposed exactly once');
  assert.equal(target[0].verified,'false','do not misrepresent original title');
  await page.locator('#map-select').selectOption(target[0].value);
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes>.tile').length===135);
  const state=await page.evaluate(()=>{
   const game=window.__ROG_TEST__,match=game.getMatch();
   const tiles=[...document.querySelectorAll('#board-nodes>.tile')];
   const rows=window.ORIGINAL_LEAF_MAPS['0170'];
   const camera=window.__LEAF_CAMERA__.getState();
   return {
    map:match.map,cells:match.tiles.length,route:camera.path?.length,
    routeBounds:camera.routeBounds,eventsClaimed:window.ORIGINAL_LEAF_TILES?.['0170']?.length||0,
    matchesSource:tiles.length===rows.length&&tiles.every((tile,i)=>
     Number(tile.dataset.dmpX)===rows[i][0]&&
     Number(tile.dataset.dmpY)===rows[i][1]&&
     tile.offsetWidth===145&&tile.offsetHeight===97),
    sourceLabels:tiles.filter(t=>t.dataset.originalArt).length,
    visible:tiles.filter(t=>getComputedStyle(t).visibility!=='hidden').length
   };
  });
  assert.equal(state.map,target[0].value);
  assert.equal(state.cells,135);
  assert.equal(state.route,135);
  assert.ok(state.matchesSource,'the exact original 0170 path + native TIS pixels stay unaltered');
  assert.equal(state.eventsClaimed,0,'there is no original event metadata; do not manufacture it');
  assert.equal(state.sourceLabels,135,'all platforms remain genuine 2002 tile PNG art');
  assert.ok(state.routeBounds&&state.visible>=1,'map really draws live camera-reachable TIS cells');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:mobile?'leaf-original-dmp0170-mobile.png':'leaf-original-dmp0170-desktop.png'});
  console.log('ORIGINAL UNNAMED DMP0170 PLAYABLE PASS '+JSON.stringify({mobile,...evidence,...state}));
 }finally{await context.close()}
}
(async()=>{const b=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{await exercise(b,false);await exercise(b,true)}
 finally{await b.close()}
})().catch(err=>{console.error('DMP0170 ORIGINAL REGRESSION FAILED',err.stack||err);process.exit(1)});
