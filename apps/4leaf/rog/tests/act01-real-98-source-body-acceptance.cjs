'use strict';
/* ACT-01 acceptance: real CHR+260 source bodies, exactly one explicit
 * missing 2002 OBS2/1222, zero fabricated CSS humanoids in live 98-card
 * game roster. This does NOT assert original action/FPS or 3D meshes. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),sandbox={window:{}};
for(const p of [
 'original/OBS/action-full/manifest.js',
 'original/OBS/action-full-ext/manifest.js',
 'original/OBS/obs23-actors/manifest.js',
 'original/OBS/referenced/chr-bodies-manifest.js',
 'chr-body-source-map.js'
])vm.runInNewContext(fs.readFileSync(path.join(root,p),'utf8'),sandbox,{filename:p});
const api=sandbox.window.__LEAF_CHR_BODY_MAP__;
const ids=Object.keys(api.cards).sort();
assert.equal(ids.length,98,'98 distinct original CHR card records');
let checked=0;
for(const id of ids){
 const row=api.lookup(id),body=api.resolve(id);
 if(id==='0156'){
  assert.equal(body,null,'0156 has no 1222.obs in the SHA1-verified installer');
  assert.equal(row.member,'1222');
  continue;
 }
 assert.ok(body,'archived original full-body missing: '+id);
 assert.equal(body.originalMember,row.originalMember,
  'source body must be owned by this CHR record: '+id);
 const f=body.frames.find(x=>x.index===0);
 assert.ok(f&&f.url.startsWith('./original/OBS/')&&
  Number.isFinite(f.originX)&&Number.isFinite(f.originY)&&f.width>0&&f.height>0,
  'actual source frame with exact origin: '+id);
 const bytes=fs.readFileSync(path.join(root,f.url.slice(2)));
 assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 assert.equal(bytes.readUInt32BE(16),f.width);
 assert.equal(bytes.readUInt32BE(20),f.height);
 assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),f.sha256);
 checked++;
}
assert.equal(checked,97);
const css=fs.readFileSync(path.join(root,'genesis-chessman-actors.css'),'utf8');
assert.match(css,/\[data-actor-rig="original-obs-sprite"\].*\.leaf-chess-actor/s,
 'genuine source rigs must hide the WEB fabricated CSS anatomy');
assert.match(css,/\[data-actor-rig="original-card-portrait-fallback"\].*\.leaf-chess-actor/s,
 'unrecovered actor must show a real archived placeholder, not a CSS humanoid');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',
   {waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CHR_BODY_MAP__&&
   window.__LEAF_GENESIS_ACTORS__,null,{timeout:30000});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#start-game').click();
  await page.locator('#game:not(.hidden)').waitFor();
  const out=await page.evaluate(async ids=>{
   const T=window.__ROG_TEST__,api=window.__LEAF_CHR_BODY_MAP__;
   const results=[];const delay=()=>new Promise(resolve=>requestAnimationFrame(resolve));
   for(const id of ids){
    const m=T.getMatch();
    m.players[0].team=['c_'+id];
    m.players[1].team=['c_0056'];
    T.setMatch(m);T.drawGame();await delay();
    const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
    if(!p)throw Error('rendered pawn missing '+id);
    const rig=p.querySelector('.leaf-chess-actor');
    const cssVisible=rig&&getComputedStyle(rig).display!=='none';
    const img=p.querySelector('img.leaf-chess-original-obs');
    const fallback=p.querySelector('img.leaf-chess-original-card-fallback');
    if(id!=='0156'&&img&&!img.complete)
      await img.decode().catch(()=>{});
    if(id==='0156'&&fallback&&!fallback.complete)
      await fallback.decode().catch(()=>{});
    results.push({id,rig:p.dataset.actorRig,
     cssVisible,source:p.dataset.actorSource,
     original:!!api.resolve(id),
     image:img&&!img.hidden?img.getAttribute('src'):null,
     decoded:!!(img&&img.complete&&img.naturalWidth>0),
     fallback:fallback&&!fallback.hidden?fallback.getAttribute('src'):null});
   }
   return results;
  },ids);
  assert.equal(out.length,98);
  for(const o of out){
   assert.equal(o.cssVisible,false,'CSS humanoid visible for '+o.id);
   if(o.id==='0156'){
    assert.equal(o.original,false);
    assert.equal(o.rig,'original-card-portrait-fallback');
    assert.equal(o.fallback,'./original/IMG/avatarback.png');
    assert.equal(o.image,null,'no fabricated 0156 body');
   }else{
    assert.equal(o.original,true,o.id);
    assert.equal(o.rig,'original-obs-sprite',o.id);
    assert.equal(o.decoded,true,'genuine OBS image failed to decode: '+o.id);
    assert.ok(o.image.startsWith('./original/OBS/'),o.id);
   }
  }
  assert.deepEqual(errors,[],'actual game no page JS errors');
  console.log('ACT01_REAL_98_ACTOR_NO_CSS_PASS',JSON.stringify({
   archiveSHA1:'86526d89679ae39b85fe9808da97ad871b7888d9',
   roster:98,sourceVerified:97,sourceMissing:'0156/OBS2-1222',
   fakeCSSBodies:out.filter(x=>x.cssVisible).length,
   runtimeSourceBodies:out.filter(x=>x.decoded).length,
   initialPngSha256Checked:checked
  }));
 }finally{await browser.close()}
})().catch(e=>{console.error('ACT01_ACCEPTANCE_FAILED',e.stack||String(e));process.exitCode=1});
