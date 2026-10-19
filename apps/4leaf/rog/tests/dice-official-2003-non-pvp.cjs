'use strict';
/* Original 2003-02-21 4LEAF announcement introduced [Non]Stadium,
 * [Non]한반도, [Non]악마의 달팽이 as specifically NO PLAYER-VS-PLAYER
 * maps. The 2002 archive only labels the UNPREFIXED original DMP maps.
 * Source evidence: https://4leafmemorial.geld.kr/m/908
 * Do not disable regular-source map PvP or invent a [Non] DMP source ID.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_MAP_INFO&&window.ORIGINAL_LEAF_MAPS);
  const verify=await page.evaluate(()=>{
   const rules=window.__ROG_TEST__.getMapRules();
   const archival=window.ORIGINAL_LEAF_MAP_INFO;
   const titles=Object.values(archival).map(x=>x.title);
   const mode=window.__ROG_TEST__.isNonBattleTitle;
   return {titles,ordinary:['악마의 달팽이','한반도','PK'].map(x=>
    ({name:x,non:rules[x]?.non,sourceVerified:titles.includes(x)})),
    historicalVariants:['[Non]Stadium','[Non]한반도','[Non]악마의 달팽이']
     .map(x=>({name:x,noPvP:mode(x),hasTrueDmp:titles.includes(x)})),
    falsePositive:['Stadium','한반도','악마의 달팽이','Non악마의 달팽이']
     .map(x=>({name:x,noPvP:mode(x)}))};
  });
  assert.ok(verify.ordinary.every(o=>o.sourceVerified&&!o.non),
   '2002 archive normal map titles MUST allow actual user battles');
  assert.ok(verify.historicalVariants.every(x=>x.noPvP&&!x.hasTrueDmp),
   'ONLY later official [Non] variants disable PvP; do not forge absent route metadata');
  assert.ok(verify.falsePositive.every(x=>!x.noPvP));
  // A real two-human match on a recovered original source DMP map.
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('한반도');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const battle=await page.evaluate(()=>{
   const api=window.__ROG_TEST__,match=api.getMatch();
   const index=match.tiles.findIndex((x,i)=>i>0&&i<match.tiles.length-1&&x==='normal');
   if(index<0)throw Error('original normal DMP route has no passable tile');
   match.players[0].position=index;match.players[1].position=index;
   const pending=api.resolveTile(match.players[0]);
   return {map:match.map,index,players:match.players.length,
    activeBattle:document.querySelector('#battle-visual')!==null,
    tiles:match.tiles.length,
    promise:pending instanceof Promise};
  });
  assert.equal(battle.map,'한반도');
  assert.ok(battle.tiles>=10);
  assert.ok(battle.activeBattle&&battle.promise,
   'original unprefixed 한반도 source map MUST permit genuine player PvP on same tile');
  const after=await page.locator('#battle-visual').evaluate(el=>({
   present:el.isConnected,source:el.dataset.nativeBattlePodium,
   userBodies:el.querySelectorAll('.leaf-battle-chessman').length
  }));
  assert.ok(after.present&&after.userBodies>=2,'live battle scene uses genuine combat participants');
  await page.screenshot({path:'leaf-2003-official-non-pvp-vs-normal-battle.png'});
  assert.deepEqual(errors,[],'no non-battle source event runtime exceptions');
  console.log('4LEAF OFFICIAL 2003 [Non] PVP SOURCE RULE PASS',JSON.stringify({verify,battle,after}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF OFFICIAL [Non] PVP RULE FAILED',e.stack||e);process.exit(1)});
