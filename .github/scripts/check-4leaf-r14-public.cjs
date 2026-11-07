'use strict';
// Public Pages acceptance after R14 reaches main. Branch CI alone cannot
// certify the user's live browser version or PWA update.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {chromium,webkit}=require('playwright');
const base='https://koith.github.io/browser-app-lab/apps/4leaf/rog/';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
// The push job checks out the EXACT main commit that changed app-version.
// Never freeze this QA to beta67: future R15+ releases must still work.
const current=JSON.parse(fs.readFileSync(path.join(__dirname,'../../apps/4leaf/rog/app-version.json'),'utf8'));
const expected=current.version,cache=current.pwaCache;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function waitForPublishedVersion(){
 const until=Date.now()+12*60_000;let observed='';
 do{
  try{
   const res=await fetch(base+'app-version.json?qa='+Date.now(),{cache:'no-store'});
   if(!res.ok)throw Error('HTTP '+res.status);
   const json=await res.json();observed=json.version+' / '+json.pwaCache;
   if(json.version===expected&&json.pwaCache===cache){
    const sw=await fetch(base+'sw.js?qa='+Date.now(),{cache:'no-store'});

    if(sw.ok&&(await sw.text()).includes("const REVISION='"+cache+"'")){
     // Pages can expose the new version before the entire original CHR
     // artwork has propagated. Verify executable AND original PNG SHA bytes
     // instead of accepting a version label as deployment completion.
     const sourceRoot=path.resolve(__dirname,'../../apps/4leaf/rog');
     const attested=[
      'native-card-action-sequences.js',
      'original/OBS/referenced/obs-1026-002.png',
      'original/OBS/referenced/obs-1029-002.png'
     ];
     let ready=true;
     for(const relative of attested){
      const expectedBytes=fs.readFileSync(path.join(sourceRoot,relative));
      const live=await fetch(base+relative+'?asset_ready='+Date.now(),{cache:'no-store'});
      if(!live.ok){observed='original asset HTTP '+live.status+' '+relative;ready=false;break}
      const bytes=Buffer.from(await live.arrayBuffer());
      if(relative.endsWith('.png')&&bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'){
       observed='non-PNG actor asset '+relative;ready=false;break;
      }
      if(crypto.createHash('sha256').update(bytes).digest('hex')!==
         crypto.createHash('sha256').update(expectedBytes).digest('hex')){
       observed='original asset SHA mismatch '+relative;ready=false;break;
      }
     }
     if(ready){console.log('PUBLIC_EXACT_ACTOR_JS_AND_PNG_READY',json.version);return json}
    }
   }
  }catch(e){observed=String(e)}
  console.log('PUBLIC_RELEASE_NOT_READY',observed);
  await sleep(20_000);
 }while(Date.now()<until);
 throw Error('Pages did not publish '+expected+'/'+cache+'; last '+observed);
}
(async()=>{
 const meta=await waitForPublishedVersion();
 const browser=await engine.launch(engine===chromium?{headless:true,args:['--no-sandbox']}:{headless:true});
 const context=await browser.newContext({viewport:engine===webkit?{width:390,height:844}:{width:800,height:600},
  serviceWorkers:'block',hasTouch:engine===webkit,isMobile:engine===webkit});
 const page=await context.newPage(),errors=[],invalid=[],recoveredCSS=[];
 const sourceRoot=path.resolve(__dirname,'../../apps/4leaf/rog');
 const basePath=new URL(base).pathname;
 const sha256=b=>crypto.createHash('sha256').update(b).digest('hex');
 function localSource(url){
  const p=new URL(url);
  if(!p.href.startsWith(base)||!p.pathname.startsWith(basePath))return null;
  const relative=decodeURIComponent(p.pathname.slice(basePath.length));
  if(!relative||relative.includes('..')||relative.startsWith('/')||relative.includes('\\'))return null;
  const source=path.resolve(sourceRoot,relative);
  return source.startsWith(sourceRoot+path.sep)?{source,relative}:null;
 }
 // Transient Github Pages CSS 503: only supply the actual stylesheet to the
 // browser before layout if a retry matches this commit's exact SHA256.
 await context.route(/\.css(?:[?#]|$)/i,async route=>{
  const url=route.request().url();
  if(!url.startsWith(base)){await route.continue();return}
  let first;
  try{first=await route.fetch({timeout:15000})}
  catch(e){await route.continue();return}
  if(![429,502,503,504].includes(first.status())){
   await route.fulfill({response:first});return;
  }
  const file=localSource(url);
  if(!file||!file.relative.endsWith('.css')||!fs.existsSync(file.source)){
   await route.fulfill({response:first});return;
  }
  const expected=sha256(fs.readFileSync(file.source));
  for(let i=1;i<=4;i++){
   try{
    await sleep(i*350);
    const retryUrl=url+(url.includes('?')?'&':'?')+'css_retry='+i+'_'+Date.now();
    const response=await route.fetch({url:retryUrl,timeout:15000});
    const body=await response.body();
    if(response.status()===200&&sha256(body)===expected){
     await route.fulfill({response,status:200,body});
     recoveredCSS.push({relative:file.relative,sha256:expected});
     return;
    }
   }catch(e){console.warn('PUBLIC_CSS_RETRY',file.relative,String(e).slice(0,100))}
  }
  await route.fulfill({response:first});
 });
 // Match the real, already-passing WorldMap->DiceChannel CI entry scenario.
 // A live production backend may be reachable independently from GitHub
 // Pages; the game-start acceptance must not depend on external login.
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('response',r=>{if(r.status()>=400&&r.url().startsWith(base))invalid.push(r.status()+' '+r.url())});
 const press=async loc=>engine===webkit?loc.tap():loc.click();
 try{
  const response=await page.goto(base+'?qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:45000});
  assert.ok(response?.ok(),'public entrypoint must load');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_FALL__&&
   window.__LEAF_BATTLE_DICE_ROLL__&&window.__LEAF_NATIVE_CARD_ACTIONS__,null,{timeout:30000});
  assert.equal(await page.locator('meta[name="leaf-revival-version"]').getAttribute('content'),expected);
  // Real WorldMap source hit -> Ispin channel -> native READY -> real roll.
  const world=page.locator('.world-location[data-region="dice"]');
  assert.equal(await world.count(),1,'original WorldMap dice hit region must exist');
  const hit=await world.boundingBox();
  assert.ok(hit&&hit.width>10&&hit.height>10);
  // 2002 source hit-mask is not necessarily active at the exact centre
  // of its box. Exercise three interior sprite-hit pixels as in the
  // passing world-to-dice-real-user-start.cjs test (not a JS route bypass).
  for(const [x,y] of [[.5,.5],[.35,.42],[.6,.7]]){
   if(await page.locator('#dice-channels:not(.hidden)').count())break;
   await (engine===webkit?world.tap({position:{x:Math.round(hit.width*x),y:Math.round(hit.height*y)}})
     :world.click({position:{x:Math.round(hit.width*x),y:Math.round(hit.height*y)}}));
   await page.waitForTimeout(200);
  }
  await page.waitForSelector('#dice-channels:not(.hidden)');
  await press(page.locator('#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]'));
  await page.waitForSelector('#lobby:not(.hidden)');
  await press(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#point-limit').selectOption('12');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await press(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
  assert.equal(await page.locator('#board-nodes .tile').count(),104);
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position);
  await press(page.locator('#roll-btn'));
  await page.waitForFunction(pos=>{
   const m=window.__ROG_TEST__?.getMatch?.();
   return !!m&&m.lastRoll?.length>0&&m.players[0].position>pos;
  },before,{timeout:30000});
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__?.originalRollTable?.(6),null,{timeout:30000});
  // Source-native duel, no altered combat values: two distinct CHR bodies.
  await page.evaluate(()=>{const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=['c_0042'];m.players[1].team=['c_0045'];T.setMatch(m);T.drawGame();
   T.resolveBattle(m.players[0],m.players[1],false)});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice==='rolling',null,{timeout:15000});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice==='landed',null,{timeout:20000});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battlePhase==='outcome',null,{timeout:18000});

  // R17 switches to the source-native outcome pose when battlePhase changes;
  // the new frame's PNG decode is asynchronous even when the 3D/duel state
  // has advanced. Observe actual decoded ORIGINAL pixels, not a mock frame.
  // A missing/failed CDN image must still fail; we do not fabricate frames.
  await page.waitForFunction(()=>{
   const stage=document.querySelector('#battle-visual');
   if(!stage||stage.dataset.battlePhase!=='outcome')return false;
   const actors=[...stage.querySelectorAll('.leaf-battle-chessman')];
   return actors.length===2&&actors.every(a=>
    a.dataset.actorRig==='original-obs-sprite'&&
    (a.querySelector('img.leaf-chess-original-obs')?.naturalWidth||0)>0);
  },null,{timeout:25000}).catch(async e=>{
   const diagnostic=await page.evaluate(()=>{
    const stage=document.querySelector('#battle-visual');
    return [...(stage?.querySelectorAll('.leaf-battle-chessman')||[])].map(a=>({
     card:a.dataset.chessmanId,rig:a.dataset.actorRig,load:a.dataset.actorSourceLoad,
     img:a.querySelector('img.leaf-chess-original-obs')?.src||'',
     width:a.querySelector('img.leaf-chess-original-obs')?.naturalWidth||0
    }));
   });
   throw Error('Public native CHR decode did not recover: '+JSON.stringify({
    actors:diagnostic,assetErrors:invalid.slice(-12),cause:String(e)}));
  });
  const scene=await page.evaluate(()=>{const s=document.querySelector('#battle-visual');
   const dice=[...s.querySelectorAll('.battle-visual-die.battle-die-has-original')];
   return {dice:dice.length,landed:dice.every(d=>d.dataset.battleRoll==='landed'),
    actors:[...s.querySelectorAll('.leaf-battle-chessman')].map(a=>({
     card:a.dataset.chessmanId,rig:a.dataset.actorRig,
     image:a.querySelector('img.leaf-chess-original-obs')?.naturalWidth||0,
     frameUrl:a.querySelector('img.leaf-chess-original-obs')?.currentSrc||'',
     originalMember:a.dataset.actorSource||'',
     result:a.dataset.duelResult||'',
     slot:a.dataset.sourceNativeSlot||'',
     duration:Number(a.dataset.sourceNativeDurationMs)||0,
     provenance:a.dataset.sourceFrameSequenceProvenance||'',
     action:a.dataset.sourceActionTable||''})),
    totals:[...s.querySelectorAll('.battle-visual-total')].map(t=>getComputedStyle(t).visibility)}});
  assert.ok(scene.dice>0&&scene.landed,'native source dice must land');
  assert.deepEqual(scene.actors.map(a=>a.card),['0042','0045']);
  assert.ok(scene.actors.every(a=>a.rig==='original-obs-sprite'&&a.image>0),'native CHR bodies must decode');

  // R17: exact public rendered source frames, not just a decodable image.
  // The original CHR source slots/ticks are VERIFIED; using them as
  // victory/hurt is still WEB-INFERRED until an EXE action map is recovered.
  assert.deepEqual(scene.actors.map(a=>a.slot).sort(),['13','14'],
   'published fight must play R17 original native outcome slots 13 and 14');
  for(const a of scene.actors){
   const member=({'0042':'1026','0045':'1029'})[a.card];
   assert.ok(member,'unexpected native duel actor '+a.card);
   assert.equal(a.slot,a.result==='win'?'14':'13',
    'published outcome must use its own CHR source slot');
   assert.ok(a.duration>=960,'published original CHR ticks were lost');
   assert.match(a.provenance,/VERIFIED.*INFERRED/,'must distinguish real source from WEB outcome mapping');
   assert.match(a.action,/native-CHR-duel-(hurt|victory)-candidate-slot(13|14)/);
   assert.ok(a.originalMember.includes('/'+member+'.obs'),
    'published duel borrowed another CHR body for '+a.card);
   const selected=localSource(a.frameUrl);
   assert.ok(selected&&selected.relative.startsWith('original/OBS/')&&
     selected.relative.endsWith('.png')&&fs.existsSync(selected.source),
     'displayed original outcome frame must resolve into the source archive '+a.frameUrl);
   const res=await context.request.get(a.frameUrl,{timeout:15000});
   assert.equal(res.status(),200,'published outcome PNG unavailable: '+a.frameUrl);
   const bytes=await res.body();
   assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a',
     'published native outcome frame has invalid PNG signature');
   assert.equal(sha256(bytes),sha256(fs.readFileSync(selected.source)),
     'published CHR outcome pixels differ from the archived source SHA '+a.card);
  }
  console.log('R17_PUBLIC_OUTCOME_SOURCE_SHA_PASS',JSON.stringify(scene.actors.map(a=>({
   card:a.card,slot:a.slot,result:a.result,member:a.originalMember,
   width:a.image,frameUrl:a.frameUrl
  }))));
  assert.ok(scene.totals.every(t=>t==='visible'),'totals visible after landing');
  if(engine===webkit)await page.setViewportSize({width:750,height:342});
  const button=page.locator('.leaf-native-battle-actions button, #modal-buttons button',{hasText:'결과 확인'}).first();
  await button.waitFor({state:'visible',timeout:10000});
  const hittable=await button.evaluate(b=>{const r=b.getBoundingClientRect(),p=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   return r.top>=0&&r.bottom<=innerHeight&&(p===b||b.contains(p))});
  assert.ok(hittable,'result button must be completely visible on iPhone landscape');
  await press(button);
  await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:10000});
  assert.deepEqual(errors,[],'public runtime must not throw');
  // Retry only transient original PNG responses, with byte-perfect source
  // SHA256; permanent 404, HTML error page, missing/mismatched content FAIL.
  // Transient CSS retries occurred BEFORE layout in the network interception.
  const unrecovered=[];
  for(const item of [...new Set(invalid)]){
   const [statusText,...parts]=item.split(' '),url=parts.join(' ');
   const file=localSource(url);
   if(![429,502,503,504].includes(Number(statusText))||!file||
      !file.relative.endsWith('.png')||!fs.existsSync(file.source)){
    unrecovered.push(item);continue;
   }
   const expectedSHA=sha256(fs.readFileSync(file.source));
   let valid=false,last='not-checked';
   for(let i=1;i<=4;i++){
    try{
     const retry=url+(url.includes('?')?'&':'?')+'original_png_retry='+i+'_'+Date.now();
     const res=await context.request.get(retry,{timeout:15000});
     const bytes=await res.body();
     valid=res.status()===200&&bytes.subarray(0,8).toString('hex')==='89504e470d0a1a0a'&&
      sha256(bytes)===expectedSHA;
     last=res.status()+' '+sha256(bytes).slice(0,12);
     if(valid)break;
    }catch(e){last=String(e)}
    await sleep(i*600);
   }
   if(!valid)unrecovered.push(item+'; source SHA retry='+last);
   else console.log('PUBLIC_ORIGINAL_PNG_SHA256_REVALIDATED',file.relative,expectedSHA);
  }
  assert.deepEqual(unrecovered,[],'public game must load or recover exact source assets');
  const appliedCSS=await page.evaluate(names=>names.map(name=>({
   name,loaded:[...document.querySelectorAll('link[rel="stylesheet"]')].some(l=>{
    try{return new URL(l.href).pathname.endsWith('/'+name)&&!!l.sheet}
    catch(e){return false}
   })
  })),recoveredCSS.map(x=>x.relative));
  assert.ok(appliedCSS.every(x=>x.loaded),
   'recovered original CSS must be present in live layout: '+JSON.stringify(appliedCSS));
  console.log('R14_PUBLIC_REAL_GAME_PASS',JSON.stringify({browser:engine.name(),release:meta.version,pwa:meta.pwaCache,scene,hittable,transientAssetErrors:invalid.length,recoveredCSS}));
 }catch(e){await page.screenshot({path:'4leaf-r14-public-fail-'+engine.name()+'.png',fullPage:true}).catch(()=>{});throw e}
 finally{await browser.close()}
})().catch(e=>{console.error('R14_PUBLIC_REAL_GAME_FAILURE',e.stack||e);process.exitCode=1});
