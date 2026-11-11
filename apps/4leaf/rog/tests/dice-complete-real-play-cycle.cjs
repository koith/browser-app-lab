'use strict';
/* Real Dice player journey. Controls are clicked in Chromium/WebKit;
 * never use __ROG_TEST__.go(), setMatch(), finishGame() or mutate game
 * positions. 'round' validates 1 complete human+AI turn cycle on 4LEAF.
 * 'finish' chooses the shortest ORIGINAL DMP map at room creation, plays
 * turns through actual original dice/events to natural victory, validates
 * native Result UI, then returns to room selection. Accelerate wallclock
 * timers only in the longer finish acceptance, not game-state logic. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const mode=process.env.FOURLEAF_CYCLE_MODE||'round';
const mobile=process.env.FOURLEAF_MOBILE==='1';
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
const fs=require('node:fs');
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  hasTouch:mobile,isMobile:mobile,serviceWorkers:'block'});
 const page=await context.newPage();const errors=[];let rolls=0,modalChoices=0,cycleSteps=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 page.on('console',m=>{if(m.type()==='error'&&m.text().includes('dice turn failed'))errors.push(m.text())});
 const get=()=>page.evaluate(()=>{
  const m=window.__ROG_TEST__?.getMatch?.();
  return m?{mode:m.mode,map:m.map,botAutoplay:m.botAutoplay,round:m.round,
   finished:m.finished,winner:m.winner,active:m.active,players:m.players.map(p=>({
    name:p.name,bot:p.bot,pos:p.position,items:p.items?.length,jail:p.jail})),
   lastRoll:m.lastRoll?.length||0,route:document.querySelector('.scene:not(.hidden)')?.id,
   result:!!document.getElementById('leaf-original-match-result'),
   blocked:!document.getElementById('modal')?.classList.contains('hidden')}:null;
 });
 const press=el=>mobile?el.tap():el.click();
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  if(mode==='finish'){
   await page.addInitScript(()=>{
    let seed=0x5e17;
    Math.random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
    const realTimeout=window.setTimeout.bind(window);
    window.setTimeout=(fn,ms,...args)=>realTimeout(fn,Math.min(Number(ms)||0,55),...args);
   });
  }
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_LOBBY__&&window.__ROG_TEST__&&window.__LEAF_WORLD__,null,{timeout:30000});
  const world=page.locator('.world-location[data-region="dice"]');
  let entered=false;const rect=await world.boundingBox();
  for(const [rx,ry]of[[.5,.5],[.35,.42],[.6,.7]]){
   if(await page.locator('#dice-channels:not(.hidden)').count()){entered=true;break;}
   await (mobile?world.tap({position:{x:rect.width*rx,y:rect.height*ry}}):
    world.click({position:{x:rect.width*rx,y:rect.height*ry}}));
   await page.waitForTimeout(90);
  }
  assert.ok(entered||await page.locator('#dice-channels:not(.hidden)').count());
  await press(page.locator('#dice-channels [data-channel="ispin:1"]'));
  await page.locator('#lobby:not(.hidden)').waitFor();
  await press(page.locator('#lobby-create'));
  await page.locator('#dice-lobby-scene.config-open').waitFor();
  assert.equal(await page.locator('#game-mode').inputValue(),'ai',
   'new solo room must DEFAULT to actual AI auto-opponent, not manual 2-player hotseat');
  if(mode==='finish'){
   const candidates=await page.locator('#map-select option').evaluateAll(options=>options
    .map(x=>({value:x.value,length:Number(/(\d+)\s*칸/.exec(x.textContent)?.[1])||999}))
    .filter(x=>x.length>=10&&x.length<500&&x.value!=='__RANDOM__')
    .sort((a,b)=>a.length-b.length));
   assert.ok(candidates.length>0,'original DMP source map paths must be enumerated');
   await page.locator('#map-select').selectOption(candidates[0].value);
   console.log('ORIGINAL_FULL_GAME_MAP',JSON.stringify(candidates[0]));
  }else await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#bot-count').selectOption('1');
  await press(page.locator('#start-game'));
  await page.locator('#game:not(.hidden)').waitFor({timeout:22000});
  let s=await get();
  assert.equal(s.mode,'ai');assert.equal(s.botAutoplay,true);
  assert.equal(s.players.length,2);
  assert.deepEqual(s.players.map(p=>p.bot),[false,true]);
  assert.ok(s.players[0].pos===0&&s.players[1].pos===0);
  assert.ok(await page.locator('#board-nodes>.tile').count()>=10);
  const startedMap=s.map,initialRounds=s.round;
  const start=Date.now();
  while(!s.finished&&(mode==='finish'?rolls<110:!s.round||s.round<initialRounds+1)){
   const popup=page.locator('#modal:not(.hidden)');
   if(await popup.count()){
    const title=await page.locator('#modal-title').textContent();
    if(title?.includes('게임 종료'))break;
    const button=page.locator('#modal-buttons button').first();
    if(await button.isVisible()){await press(button);modalChoices++}
   }
   if(s.active===0&&!s.blocked){
    const roll=page.locator('#roll-btn');
    if(await roll.isEnabled()&&await roll.isVisible()){
     await press(roll);rolls++;
     cycleSteps.push({roll:rolls,round:s.round,position:s.players[0].pos});
    }
   }
   await page.waitForTimeout(90);
   s=await get();
   if(Date.now()-start>(mode==='finish'?360000:55000))break;
  }
  if(mode==='round'){
   assert.ok(s.round>=initialRounds+1||s.finished,
    'after a real human roll, the computer must roll automatically and return turn to human');
   assert.ok(rolls>=1,'one actual original dice button was clicked');
   assert.ok(s.players[1].pos>0||s.finished,
    'computer must move its own pawn without a second human click');
   assert.deepEqual(errors,[]);
   console.log('DICE_REAL_HUMAN_AI_COMPLETE_ROUND_PASS',JSON.stringify({
    engine:engine.name(),mobile,rolls,s,elapsed:Date.now()-start}));
   // Reload and room resume must BOTH leave saved AI opponents paused.
   // The visible in-game toggle is the sole explicit opt-in for autoplay.
   const oldRound=s.round;
   await page.reload({waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_LOBBY__&&window.__LEAF_WORLD__);
   let afterReload=await get();
   assert.equal(afterReload.botAutoplay,false,
    'reloading alone must not silently run background bot dice turns');
   const world2=page.locator('.world-location[data-region="dice"]');
   const bounds=await world2.boundingBox();
   for(const [rx,ry] of [[.5,.5],[.35,.42],[.6,.7]]){
    if(await page.locator('#dice-channels:not(.hidden)').count())break;
    await (mobile?world2.tap({position:{x:bounds.width*rx,y:bounds.height*ry}}):
     world2.click({position:{x:bounds.width*rx,y:bounds.height*ry}}));
   }
   await page.locator('#dice-channels:not(.hidden)').waitFor();
   await press(page.locator('#dice-channels [data-channel="ispin:1"]'));
   await page.locator('#lobby:not(.hidden)').waitFor();
   const saved=page.locator('#lobby-room-list .lobby-room-row[data-match="saved"]');
   assert.equal(await saved.count(),1,'actual saved AI room must appear in same channel');
   await press(saved);
   await page.locator('#game:not(.hidden)').waitFor();
   afterReload=await get();
   assert.equal(afterReload.botAutoplay,false,
     'entering saved room must not restart computer rolls without distinct consent');
    const aiToggle=page.locator('#dice-ai-autoplay-toggle');
    assert.equal(await aiToggle.getAttribute('aria-pressed'),'false',
     'restored AI opponent is visibly paused');
    await press(aiToggle);
    afterReload=await get();
    assert.equal(afterReload.botAutoplay,true,
     'explicit user toggle click resumes computer opponent autonomy');
    assert.equal(await aiToggle.getAttribute('aria-pressed'),'true');
    const resumeStart=Date.now();
   await page.waitForFunction(()=>!document.querySelector('#roll-btn')?.disabled&&
    window.__ROG_TEST__?.getMatch?.()?.active===0,null,{timeout:22000});
   await press(page.locator('#roll-btn'));
   // A genuinely random source DMP tile may open battle, ability, event or
   // other user-decision dialogs. The first round already handles these.
   // Do the same after reload: never call internal game-state shortcuts.
   const nextRoundDeadline=Date.now()+60000;
   let resumed=await get();
   while(!resumed.finished&&!(resumed.round>oldRound&&resumed.active===0)&&Date.now()<nextRoundDeadline){
    const popup=page.locator('#modal:not(.hidden)');
    if(await popup.count()){
     const option=page.locator('#modal-buttons button').first();
     if(await option.isVisible()){await press(option);modalChoices++}
    }
    await page.waitForTimeout(100);
    resumed=await get();
   }
   assert.ok(resumed.finished||(resumed.round>oldRound&&resumed.active===0),
    'a real resumed match must resolve any original DMP choice dialog and finish another human+AI turn: '+JSON.stringify({resumed,modalChoices}));
   assert.ok(resumed.round>oldRound||resumed.finished);
   assert.deepEqual(errors,[]);
   console.log('DICE_SAVED_AI_EXPLICIT_TOGGLE_NEXT_ROUND_PASS',JSON.stringify({
    engine:engine.name(),mobile,oldRound,resumedRound:resumed.round,
    botAutoplay:resumed.botAutoplay,elapsed:Date.now()-resumeStart}));
  }else{
   assert.equal(s.finished,true,'unmodified original DMP game must reach natural winner: '+JSON.stringify({rolls,s}));
   assert.ok(s.winner>=0&&s.winner<s.players.length);
   await page.locator('#leaf-original-match-result').waitFor({timeout:8000});
   assert.ok((await page.locator('#leaf-original-match-result').textContent()).includes('GP'),
    'real result UI must show winner and reward state');
   await page.screenshot({path:'leaf-dice-full-game-result-'+engine.name()+'.png'});
   await press(page.locator('#modal-buttons button').filter({hasText:'다시 시작'}));
   await page.locator('#lobby:not(.hidden)').waitFor({timeout:10000});
   assert.ok(s.players.some(p=>p.pos>0));
   console.log('DICE_REAL_MATCH_NATURAL_WIN_TO_RESTART_PASS',JSON.stringify({
    engine:engine.name(),map:startedMap,rolls,modalChoices,final:s,
    elapsed:Date.now()-start}));
  }
  assert.deepEqual(errors,[],'gameplay must not leave JavaScript dice exceptions');
 }catch(e){
  console.error('DICE_PLAY_LOOP_FAILED',e.stack||String(e));
  console.error('DICE_PLAY_LOOP_TRACE',JSON.stringify({mode,rolls,modalChoices,cycleSteps,errors,s:await get().catch(()=>null)}));
  await page.screenshot({path:'leaf-dice-cycle-fail-'+engine.name()+(mobile?'-phone':'')+'.png',fullPage:true}).catch(()=>{});
  throw e;
 }finally{await browser.close();}
})().catch(()=>process.exit(1));
