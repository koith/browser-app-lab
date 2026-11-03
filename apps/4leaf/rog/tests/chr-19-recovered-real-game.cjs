'use strict';
/* Original 2002 CHR.pak +260 -> OBS, OBS2, OBS3 exact-body restoration.
 * Read every SHA256-verified PNG file, start a real WorldMap->Region->Room
 * game, cycle all 19 formerly unpublished chessmen and ensure original
 * indexed body images load and appear in the actual board actor DOM.
 * This never claims recovered EXE action names/FPS or original 2004 styling.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {chromium,webkit}=require('playwright');
const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const mobile=process.env.FOURLEAF_MOBILE==='1';
const root=path.resolve(__dirname,'..');
const manifestScript=fs.readFileSync(path.join(root,'original/OBS/referenced/chr-bodies-manifest.js'),'utf8');
const holder={window:{}};
require('node:vm').runInNewContext(manifestScript,holder,{filename:'original CHR manifest'});
const referenced=holder.window.ORIGINAL_LEAF_RECOVERED_CHR_BODIES;
const members=[...Array.from({length:15},(_,i)=>'obs/'+(1025+i)),'obs/1041','obs/1057','obs2/1212','obs3/1256'];
const cards=[
 '0040',...Array.from({length:14},(_,i)=>String(42+i).padStart(4,'0')),
 '0058','0074','0138','0159'
];
// The 19 CHR owners are 0040, 0042–0055, 0058, 0074, 0138 and 0159.
// 0056 owns OBS 1040 (already published), never assign 1025 to '0056'.
assert.equal(cards.length,19);
assert.equal(Object.keys(referenced).length,19);
let checked=0;
for(let i=0;i<members.length;i++){
 const key=members[i],record=referenced[key],body=key.split('/')[1],pak=key.split('/')[0];
 assert.ok(record,key+' source member must be in reduced original manifest');
 assert.equal(record.originalMember,pak.toUpperCase()+'.pak/'+body+'.obs');
 assert.match(record.sourceSHA256,/^[a-f0-9]{64}$/);
 assert.equal(record.blocks.length,1);
 const block=record.blocks[0],frames=block.frames;
 assert.equal(block.frameCount,frames.length);
 assert.match(block.paletteSHA256,/^[a-f0-9]{64}$/);
 frames.forEach((f,index)=>{
  assert.equal(f.index,index);
  const expected='./original/OBS/referenced/'+pak+'-'+body+'-'+String(index).padStart(3,'0')+'.png';
  assert.equal(f.url,expected,'never borrow another CHR member art');
  const bytes=fs.readFileSync(path.join(root,expected.slice(2)));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),f.sha256,expected);
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(bytes.readUInt32BE(16),f.width);
  assert.equal(bytes.readUInt32BE(20),f.height);
  checked++;
 });
}
assert.equal(checked,662,'all 662 recovered source frames are byte-identical');
(async()=>{
 const browser=await browserType.launch({headless:true,...(browserType===chromium?{args:['--no-sandbox']}:{})});
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const tap=locator=>mobile?locator.tap():locator.click();
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_WORLD__&&
   window.__LEAF_CHR_BODY_MAP__&&window.__LEAF_GENESIS_ACTORS__,null,{timeout:16000});
  await tap(page.locator('.world-location[data-region="dice"]'));
  await tap(page.locator('#dice-channels [data-channel="ispin:1"]'));
  await tap(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#map-select').selectOption('4LEAF');
  await tap(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
  const before=await page.evaluate(()=>({
   source:window.__LEAF_CHR_BODY_MAP__.getState(),
   match:window.__ROG_TEST__.getMatch()?.map,
   missing:window.__LEAF_CHR_BODY_MAP__.resolve('0156')
  }));
  assert.equal(before.match,'4LEAF');
  assert.equal(before.source.resolvedSourceCards,97,'97 source CHR chessman body members restored');
  assert.equal(before.source.recovered20261103Cards.length,19);
  assert.equal(before.source.recovered20261103FrameCount,662);
  assert.equal(before.missing,null,'card 0156 remains source-missing, never fabricated');
  const observed=[];
  for(let i=0;i<cards.length;i++){
   const card=cards[i],member=members[i];
   const source=await page.evaluate(card=>{
    const obj=window.__LEAF_CHR_BODY_MAP__.resolve(card);
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+card];
    T.drawGame();
    return {member:obj?.originalMember,frames:obj?.frames?.length,
     recovered:obj?.recoveredOriginal20261103};
   },card);
   assert.equal(source.member,member.split('/')[0].toUpperCase()+'.pak/'+member.split('/')[1]+'.obs');
   assert.equal(source.recovered,true,card+' resolved actual published native CHR body');
   await page.waitForFunction(card=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const image=pawn?.querySelector('img.leaf-chess-original-obs');
    return pawn?.dataset.chessmanId==='c_'+card&&pawn.dataset.actorRig==='original-obs-sprite'&&
     pawn.dataset.actorOriginalModelRecovered==='true'&&
     pawn.dataset.actorSourceLoad==='ready'&&image?.naturalWidth>0&&image?.naturalHeight>0;
   },card,{timeout:14000});
   const rendered=await page.evaluate(()=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const image=pawn.querySelector('img.leaf-chess-original-obs');
    return {card:pawn.dataset.chessmanId,source:pawn.dataset.actorSource,
     rig:pawn.dataset.actorRig,src:image.getAttribute('src'),
     width:image.naturalWidth,height:image.naturalHeight};
   });
   assert.ok(rendered.src.startsWith('./original/OBS/referenced/'+member.replace('/','-')+'-'),
    card+' actual actor is from its own source package');
   observed.push({card,member,frames:source.frames,source:rendered.source});
  }
  await page.screenshot({path:'leaf-chr-19-original-recovered-'+browserType.name()+'-mobile-'+Number(mobile)+'.png'});
  assert.deepEqual(errors,[],'no runtime crashes for any of 19 original actor sources');
  console.log('4LEAF ORIGINAL CHR 19 BODIES 662 FRAMES REAL GAME PASS '+JSON.stringify({
   engine:browserType.name(),mobile,checkedPngSha256:checked,
   totalOriginalSourceBodies:before.source.resolvedSourceCards,
   stillMissingOriginalBody:'0156',observed}));
 }finally{await browser.close();}
})().catch(e=>{console.error('4LEAF ORIGINAL CHR 19 BODIES REAL GAME FAIL',e.stack||String(e));process.exit(1)});
