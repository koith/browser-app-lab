'use strict';
/* 19 real recovered CHR bodies: 662 original PNG SHA-256 checks and live
 * Chromium/WebKit game actors (not portraits or synthetic placeholders).
 * Historical action labels and frame milliseconds still UNVERIFIED.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const root=path.resolve(__dirname,'..');
const context={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'original/OBS/referenced/chr-bodies-manifest.js'),'utf8'),context);
const records=context.window.ORIGINAL_LEAF_RECOVERED_CHR_BODIES;
const members=[...Array.from({length:15},(_,i)=>'obs/'+(1025+i)),'obs/1041','obs/1057','obs2/1212','obs3/1256'];
const cards=['0040',...Array.from({length:14},(_,i)=>String(i+42).padStart(4,'0')),'0058','0074','0138','0159'];
assert.equal(cards.length,19);assert.equal(Object.keys(records).length,19);
let validPngs=0;
for(const member of members){
 const row=records[member],parts=member.split('/'),pak=parts[0],id=parts[1];
 assert.ok(row,'missing source member '+member);
 assert.equal(row.originalMember,pak.toUpperCase()+'.pak/'+id+'.obs');
 assert.match(row.sourceSHA256,/^[0-9a-f]{64}$/);
 assert.equal(row.blocks.length,1);
 const block=row.blocks[0];
 assert.equal(block.frameCount,block.frames.length);
 assert.match(block.paletteSHA256,/^[0-9a-f]{64}$/);
 block.frames.forEach((f,index)=>{
  const expected='./original/OBS/referenced/'+pak+'-'+id+'-'+String(index).padStart(3,'0')+'.png';
  assert.equal(f.index,index);assert.equal(f.url,expected);
  const bytes=fs.readFileSync(path.join(root,expected.slice(2)));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),f.sha256,
   'original sprite byte mismatch '+expected);
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(bytes.readUInt32BE(16),f.width);
  assert.equal(bytes.readUInt32BE(20),f.height);
  validPngs++;
 });
}
assert.equal(validPngs,662,'every recovered original source PNG must be checked');
(async()=>{
 const browser=await engine.launch({headless:true,...(engine===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&window.__LEAF_GENESIS_ACTORS__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const state=await page.evaluate(()=>window.__LEAF_CHR_BODY_MAP__.getState());
  assert.equal(state.resolvedSourceCards,97);
  assert.equal(state.recovered20261103Cards.length,19);
  assert.equal(state.recovered20261103FrameCount,662);
  assert.equal(await page.evaluate(()=>window.__LEAF_CHR_BODY_MAP__.resolve('0156')),null,
   '0156 missing real source must never be invented');
  const observed=[];
  for(let i=0;i<19;i++){
   const card=cards[i],source=members[i];
   const data=await page.evaluate(card=>{
    const obj=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    const match=window.__ROG_TEST__.getMatch();
    match.players[0].team=['c_'+card];
    window.__ROG_TEST__.drawGame();
    return {source:obj?.originalMember,frames:obj?.frames?.length,
     recovered:obj?.recoveredOriginal20261103};
   },card);
   assert.equal(data.source,source.split('/')[0].toUpperCase()+'.pak/'+source.split('/')[1]+'.obs');
   assert.equal(data.recovered,true,'render original body for card '+card);
   await page.waitForFunction(card=>{
    const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const img=actor?.querySelector('img.leaf-chess-original-obs');
    return actor?.dataset.chessmanId==='c_'+card&&
     actor.dataset.actorRig==='original-obs-sprite'&&
     actor.dataset.actorSourceLoad==='ready'&&
     img?.naturalWidth>0&&img?.naturalHeight>0;
   },card,{timeout:12000});
   const displayed=await page.evaluate(()=>{
    const actor=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    return actor?.querySelector('img.leaf-chess-original-obs')?.getAttribute('src');
   });
   assert.ok(displayed?.startsWith('./original/OBS/referenced/'+source.replace('/','-')+'-'),
    'visible source must belong to the same CHR body '+card+': '+displayed);
   observed.push({card,source,frames:data.frames});
  }
  assert.deepEqual(errors,[],'all 19 actual recovered actors remain error-free');
  console.log('R12 REAL ORIGINAL 19 CHR BODIES 662 PNG PASS',JSON.stringify({
   engine:engine.name(),validPngs,total:state.resolvedSourceCards,missing:'0156',observed}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R12 RECOVERED CHR BODIES FAILED',e.stack||e);process.exit(1)});
