'use strict';
/* Native 2002 source OBS frame coverage: test EVERY accepted PNG's binary
 * hash/native dimensions, then render two recovered characters in a REAL
 * playable DMP board and in the live battle overlay. The original action
 * table is not decoded; do not claim pose labels as verified.
 */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const scope={window:{ORIGINAL_LEAF_OBS_FRAMES:{}}};
vm.runInNewContext(fs.readFileSync(path.join(root,'original/OBS/animation-extra.js'),'utf8'),scope);
const recovered=scope.window.ORIGINAL_LEAF_OBS_FRAMES;
const report=JSON.parse(fs.readFileSync(path.join(root,'original/OBS/bulk-source-report.json'),'utf8'));
let files=0,totalBytes=0;
assert.equal(Object.keys(recovered).length,report.accepted,'every reported source character has a manifest entry');
assert.ok(report.accepted>=40&&report.framePNGs>=200,'broad actual OBS coverage, not a two-character proof-of-concept');
for(const [id,source] of Object.entries(recovered)){
 assert.match(id,/^\d{4}$/);
 assert.match(source.originalMember,/^1\d{3}\.obs$/);
 assert.equal(source.poseMapping.startsWith('UNVERIFIED'),true,'never falsely certify original action tables');
 assert.equal(source.horizontalScanlineOrigin.startsWith('PROVISIONAL'),true);
 assert.ok(source.frames.length>=2);
 assert.equal(source.hasVerifiedFrameZero,source.frames.some(f=>f.index===0),
   'manifest must truthfully identify whether the original zero frame was decoded');
 if(!source.hasVerifiedFrameZero){
  assert.match(source.fallbackAction||'',/^EARLIEST SOURCE FRAME ONLY/,
   'missing source frame zero is a STATIC original pixel fallback, not certified idle animation');
  assert.notEqual(source.frames[0].index,0,'never manufacture zero-index original pose');
 }
 for(const frame of source.frames){
  assert.ok(frame.url.startsWith('./original/OBS/bulk/'),'only original OBS per-frame file is accepted');
  const filename=path.resolve(root,frame.url.replace(/^\.\//,''));
  assert.ok(filename.startsWith(path.resolve(root,'original/OBS/bulk')+path.sep),'no cross-folder resource alias');
  const binary=fs.readFileSync(filename);files++;totalBytes+=binary.length;
  assert.equal(binary.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.deepEqual([binary.readUInt32BE(16),binary.readUInt32BE(20)],[frame.width,frame.height],
   'decoded bitmap keeps OBS frame-native geometry');
  assert.equal(crypto.createHash('sha256').update(binary).digest('hex'),frame.sha256,
   'every published source pixel has a reproducible extraction hash');
 }
}
assert.equal(files,report.framePNGs);
assert.equal(totalBytes,report.bytes);
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(root,'index.html'));
  await page.waitForFunction(()=>window.__ROG_TEST__&&
   window.ORIGINAL_LEAF_OBS_FRAMES?.['0043']&&
   window.ORIGINAL_LEAF_OBS_FRAMES?.['0054']);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>{
   const players=window.__ROG_TEST__.getMatch().players;
   players[0].team[0]='c_0043';
   players[1].team[0]='c_0054';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')]
   .length===2&&[...document.querySelectorAll('#board-pawns .leaf-chess-original-obs')]
   .every(img=>img.complete&&img.naturalWidth>15),null,{timeout:18000});
  const state=await page.evaluate(()=>({
   count:document.querySelectorAll('#board-nodes .tile').length,
   actors:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    id:p.dataset.chessmanId,source:p.dataset.actorSource,rig:p.dataset.actorRig,
    map:p.dataset.sourcePoseMapping,
    png:p.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
    css:getComputedStyle(p.querySelector('.leaf-chess-actor')).display,
    pixels:[p.querySelector('.leaf-chess-original-obs').naturalWidth,
            p.querySelector('.leaf-chess-original-obs').naturalHeight]
   }))
  }));
  assert.equal(state.count,104);
  assert.deepEqual(state.actors.map(x=>x.id),['0043','0054']);
  assert.ok(state.actors.every(x=>x.rig==='original-obs-sprite'&&
   x.source.startsWith('OBS/')&&x.map==='unverified'&&x.css==='none'&&
   x.png.startsWith('./original/OBS/bulk/')&&x.pixels[0]>20));
  assert.equal(await page.locator('#board-pawns img[src*="/Registry/sava"]').count(),0,
   'do not display 4LEAF social avatar as a Genesis chessman');
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>window.__LEAF_GENESIS_ACTORS__?.getState().rendered[0]
   ?.counts?.walk>0,null,{timeout:21000});
  const roll=await page.evaluate(()=>({
   active:window.__ROG_TEST__.getMatch().active,
   dice:window.__ROG_TEST__.getMatch().lastRoll
  }));
  assert.ok(roll.dice?.length>0,'source actor remains playable through genuine dice roll');
  await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   window.__ROG_TEST__.resolveBattle(m.players[0],m.players[1],false);
  });
  await page.waitForFunction(()=>[...document.querySelectorAll('#battle-visual .battle-visual-actor')]
   .length===2&&[...document.querySelectorAll('#battle-visual .leaf-chess-original-obs')]
   .every(img=>img.complete&&img.naturalWidth>20),null,{timeout:14000});
  const duel=await page.evaluate(()=>[...document.querySelectorAll('#battle-visual .battle-visual-actor')].map(a=>({
   id:a.dataset.chessmanId,
   src:a.querySelector('.leaf-chess-original-obs')?.getAttribute('src'),
   proxy:getComputedStyle(a.querySelector('.leaf-chess-actor')).display
  })));
  assert.deepEqual(duel.map(x=>x.id),['0043','0054']);
  assert.ok(duel.every(x=>x.src.startsWith('./original/OBS/bulk/')&&x.proxy==='none'));
  await page.screenshot({path:'leaf-new-original-2002-obs-body-actors.png'});
  assert.deepEqual(errors,[],'no runtime exceptions while playing native OBS PNG frames');
  console.log('NATIVE OBS 2002 BULK CHARACTER SCENE VERIFIED '+JSON.stringify({
   groups:report.accepted,framePNGs:files,shaVerified:true,cards:state.actors,roll,duel}));
 }finally{await browser.close()}
})().catch(err=>{console.error('NATIVE OBS 2002 BULK FAILED',err.stack||err);process.exit(1)});
