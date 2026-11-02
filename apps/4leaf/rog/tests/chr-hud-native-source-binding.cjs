'use strict';
/* End-to-end CHR +260 identity: right-hand native source portraits must be
 * the very same 2002 OBS member as the in-game pawn and duel, NEVER a
 * screenshot, old 0NNN=1NNN guessed body or somebody else's CardData face. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const isWebKit=process.env.FOURLEAF_BROWSER==='webkit';
 const browser=await (isWebKit?webkit:chromium).launch({headless:true,
   ...(isWebKit?{}:{args:['--no-sandbox']})});
 const page=await browser.newPage({viewport:{width:900,height:650},
   serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&
    window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const inspect=async cards=>page.evaluate(cards=>{
   const match=window.__ROG_TEST__.getMatch();
   match.players.forEach(p=>{p.team=cards.map(id=>'c_'+id)});
   window.__ROG_TEST__.drawGame();
   return [...document.querySelectorAll('#dice-native-party .dice-chessman-slot.occupied')]
    .map(slot=>{
     const img=slot.querySelector('img.dice-chessman-face'),id=slot.dataset.cardId.slice(2);
     const sourceMap=window.__LEAF_CHR_BODY_MAP__,body=sourceMap.lookup(id);
     const published=sourceMap.resolve(id);
     return {id,chr:body?.originalMember,declared:slot.dataset.chrOriginalBody,
      matched:slot.dataset.chrSourceMatch,expectedURL:published?.frames[25]?.url,
      real:slot.dataset.rightPortraitSource,frame:img?.dataset.nativeFrontFrame,
      nativeMember:img?.dataset.originalMember,url:img?.getAttribute('src'),
      parentId:match.players[match.active]?.id};
    });
  },cards);
  const live=await inspect(['0056','0059','0060']);
  assert.equal(live.length,3);
  for(const [i,member] of ['1040','1042','1043'].entries()){
   const x=live[i];assert.equal(x.chr,'OBS.pak/'+member+'.obs');
   assert.equal(x.declared,x.chr,'original CHR member identity must remain visible');
   assert.equal(x.matched,'true','only CHR +260 sourced published sprites are renderable');
   assert.equal(x.nativeMember,x.chr,'native OBS member must equal selected card source');
   assert.equal(x.real,'OBS.pak/verified-front');
   assert.equal(x.frame,'25');
   assert.equal(x.url,x.expectedURL,'right panel must not borrow another original character');
   assert.ok(x.url.endsWith('/'+member+'-25.png'),JSON.stringify(x));
  }
  await page.waitForFunction(()=>[...document.querySelectorAll(
   '#dice-native-party .dice-chessman-slot.occupied img.dice-chessman-face')]
    .every(img=>img.complete&&img.naturalWidth>5),null,{timeout:16000});
  const noBody=await inspect(['0040','0156','0056']);
  for(let i=0;i<2;i++){
   const x=noBody[i];assert.equal(x.matched,'false',x.id);
   assert.ok(x.real==='IMG/avatarback/no-sourced-portrait'||
     x.real==='CardData/legacy-roster-unsourced',JSON.stringify(x));
   assert.equal(x.nativeMember,undefined,'no made-up OBS sprite for missing PNG');
   assert.ok(x.url?.startsWith('./original/CardData/')||
    x.url==='./original/IMG/avatarback.png','unpublished actor must retain honest art');
  }
  assert.equal(noBody[0].declared,'OBS.pak/1025.obs');
  assert.equal(noBody[1].declared,'missing','CHR 0156 references an absent 1222 OBS member');
  assert.equal(noBody[2].chr,'OBS.pak/1040.obs');
  assert.equal(noBody[2].nativeMember,'OBS.pak/1040.obs');
  assert.deepEqual(errors,[],'no JS exception during real game team swaps');
  console.log('4LEAF CHR +260 RIGHT-HUD NATIVE SOURCE PASS',
    JSON.stringify({browser:isWebKit?'webkit':'chromium',published:live.length,
      genuineBodies:['1040','1042','1043'],unpublished:['0040','0156']}));
 }finally{await browser.close()}
})().catch(e=>{console.error('CHR RIGHT-HUD SOURCE REGRESSION FAILED',e.stack||e);process.exit(1)});
