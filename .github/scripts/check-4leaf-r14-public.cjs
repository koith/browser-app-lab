'use strict';
// Public Pages acceptance after R14 reaches main. Branch CI alone cannot
// certify the user's live browser version or PWA update.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
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
    if(sw.ok&&(await sw.text()).includes("const REVISION='"+cache+"'"))return json;
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
 const page=await context.newPage(),errors=[],invalid=[];
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
  await press(page.locator('.world-location[data-region="dice"]'));
  await page.waitForSelector('#dice-channels:not(.hidden)');
  await press(page.locator('#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]'));
  await page.waitForSelector('#lobby:not(.hidden)');
  await press(page.locator('#lobby-create'));
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await press(page.locator('#start-game'));
  await page.waitForSelector('#game:not(.hidden)');
  assert.equal(await page.locator('#board-nodes .tile').count(),104);
  const before=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position);
  await press(page.locator('#roll-btn'));
  await page.waitForFunction(pos=>window.__ROG_TEST__?.getMatch()?.players?.[0]?.position>pos,before,{timeout:30000});
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__?.originalRollTable?.(6),null,{timeout:30000});
  // Source-native duel, no altered combat values: two distinct CHR bodies.
  await page.evaluate(()=>{const T=window.__ROG_TEST__,m=T.getMatch();
   m.players[0].team=['c_0042'];m.players[1].team=['c_0045'];T.setMatch(m);T.drawGame();
   T.resolveBattle(m.players[0],m.players[1],false)});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice==='rolling',null,{timeout:15000});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battleDice==='landed',null,{timeout:20000});
  await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.battlePhase==='outcome',null,{timeout:18000});
  const scene=await page.evaluate(()=>{const s=document.querySelector('#battle-visual');
   const dice=[...s.querySelectorAll('.battle-visual-die.battle-die-has-original')];
   return {dice:dice.length,landed:dice.every(d=>d.dataset.battleRoll==='landed'),
    actors:[...s.querySelectorAll('.leaf-battle-chessman')].map(a=>({
     card:a.dataset.chessmanId,rig:a.dataset.actorRig,
     image:a.querySelector('img.leaf-chess-original-obs')?.naturalWidth||0})),
    totals:[...s.querySelectorAll('.battle-visual-total')].map(t=>getComputedStyle(t).visibility)}});
  assert.ok(scene.dice>0&&scene.landed,'native source dice must land');
  assert.deepEqual(scene.actors.map(a=>a.card),['0042','0045']);
  assert.ok(scene.actors.every(a=>a.rig==='original-obs-sprite'&&a.image>0),'native CHR bodies must decode');
  assert.ok(scene.totals.every(t=>t==='visible'),'totals visible after landing');
  if(engine===webkit)await page.setViewportSize({width:750,height:342});
  const button=page.locator('.leaf-native-battle-actions button, #modal-buttons button',{hasText:'결과 확인'}).first();
  await button.waitFor({state:'visible',timeout:10000});
  const hittable=await button.evaluate(b=>{const r=b.getBoundingClientRect(),p=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   return r.top>=0&&r.bottom<=innerHeight&&(p===b||b.contains(p))});
  assert.ok(hittable,'result button must be completely visible on iPhone landscape');
  await press(button);
  await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:10000});
  assert.deepEqual(errors,[]);assert.deepEqual(invalid,[]);
  console.log('R14_PUBLIC_REAL_GAME_PASS',JSON.stringify({browser:engine.name(),release:meta.version,pwa:meta.pwaCache,scene,hittable}));
 }catch(e){await page.screenshot({path:'4leaf-r14-public-fail-'+engine.name()+'.png',fullPage:true}).catch(()=>{});throw e}
 finally{await browser.close()}
})().catch(e=>{console.error('R14_PUBLIC_REAL_GAME_FAILURE',e.stack||e);process.exitCode=1});
