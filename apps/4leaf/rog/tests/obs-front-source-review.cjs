'use strict';
/* OBS front-direction visual audit regression — original pixels only.
 * 0 is visibly back/side on the sampled authentic OBS sprites; assert that
 * source 25 (and 1045/18) replaces the default backward idle rotation.
 * Non-reviewed character direction and historical EXE FPS remain OPEN.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
const {readFileSync}=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:920},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
   window.ORIGINAL_LEAF_OBS_FRAMES,null,{timeout:15000});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const verified={'0040':25,'0042':25,'0043':25,'0044':25,'0045':18,
   '0046':25,'0048':25,'0049':25,'0051':25,'0052':25,
   '0053':25,'0054':25,'0055':25,'0056':25,'0058':25,
   '0059':25,'0060':25,'0061':25,'0062':25,'0064':25};
  const proofs=[];
  for(const [id,expected] of Object.entries(verified)){
   const state=await page.evaluate(id=>{
    const match=window.__ROG_TEST__.getMatch();
    match.players[0].team[0]='c_'+id;
    window.__ROG_TEST__.drawGame();
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const img=pawn.querySelector('img.leaf-chess-original-obs');
    const source=window.ORIGINAL_LEAF_OBS_FRAMES[id];
    const f=source.frames.find(x=>x.index===Number(pawn.dataset.actorFrame));
    const style=getComputedStyle(img),matrix=new DOMMatrixReadOnly(style.transform);
    return {id,index:Number(pawn.dataset.actorFrame),url:img.getAttribute('src'),
     index0:source.frames.find(x=>x.index===0)?.url,
     provenance:pawn.dataset.sourceFacingEvidence,
     sequence:pawn.dataset.sourceFrameSequence,
     actual:pawn.dataset.actorRig,cssFlipY:matrix.m22,
     width:img.getBoundingClientRect().width,height:img.getBoundingClientRect().height,
     original:f?.sha256||null};
   },id);
   assert.equal(state.index,expected,'verified native front 2002 packet for '+id);
   assert.ok(state.url.endsWith('/'+(id==='0042'?'1042':id==='0045'?'1045':'1'+id.slice(1))+'-'+
    String(expected).padStart(2,'0')+'.png'),JSON.stringify(state));
   assert.ok(!state.url.includes('-00.png'), 'the old back-facing source must not be visible at idle');
   assert.equal(state.actual,'original-obs-sprite');
   assert.equal(state.sequence,String(expected),'do not animate backward 0..3 packets as idle');
   assert.ok(state.provenance.startsWith('visual-original-OBS-reviewed/front/'));
   assert.ok(state.cssFlipY<0,'exact FLIP_TOP_BOTTOM source PNG needs upright on-screen transform');
   assert.ok(state.width>=10&&state.height>=35,'native body must remain visible');
   proofs.push(state);
  }
  const sourceCoverage=await page.evaluate(()=>{
   const all=Object.entries(window.ORIGINAL_LEAF_OBS_FRAMES);
   const with25=all.filter(([,m])=>m.frames?.some(f=>f.index===25)).length;
   const missing=all.filter(([,m])=>!m.frames?.some(f=>f.index===25)).map(([id])=>id);
   return {models:all.length,with25,missing};
  });
  assert.equal(sourceCoverage.models,92);
  assert.ok(sourceCoverage.with25>=60);
  // Visual before/after comparison: archived native 2004 screenshot next
  // to actual running board + source character sheet via single QA artifact.
  const originalBattle='data:image/jpeg;base64,'+
   readFileSync(path.resolve(__dirname,'../../assets/battle.jpg')).toString('base64');
  await page.evaluate(reference=>{
   const wrap=document.createElement('div');
   wrap.id='obs-visual-audit';
   wrap.style.cssText='position:fixed;left:0;top:0;z-index:99999;width:100vw;height:100vh;'+
    'display:flex;gap:14px;align-items:flex-start;background:#17132e;padding:18px;color:white';
   const original=new Image();original.src=reference;
   original.style.cssText='width:46vw;max-width:640px;object-fit:contain';
   const live=document.getElementById('game').cloneNode(true);
   live.style.cssText='position:relative!important;width:46vw;height:600px;display:block';
   wrap.append(original,live);document.body.append(wrap);
  },originalBattle);
  await page.waitForFunction(()=>document.querySelector('#obs-visual-audit>img')?.naturalWidth===800,
   null,{timeout:12000});
  await page.screenshot({path:'leaf-obs-original-battle-vs-front-native-web.png'});
  assert.deepEqual(errors,[]);
  console.log('ORIGINAL OBS VISUALLY REVIEWED FRONT IDLE PASS '+
   JSON.stringify({verified:proofs.map(x=>({id:x.id,front:x.index,source:x.url})),sourceCoverage}));
 }finally{await browser.close()}
})().catch(e=>{console.error('OBS FRONT SOURCE QA FAILED',e.stack||e);process.exit(1)});
