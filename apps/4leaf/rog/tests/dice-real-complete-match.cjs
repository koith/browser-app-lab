'use strict';
/* Real complete Genesis Dice game: native WorldMap -> Region -> Map room ->
 * Room READY -> two player turn cycle -> GOAL result -> native lobby replay.
 * No test-only __ROG_TEST__.setMatch, synthetic dice, hidden go(), or false
 * finished flag: only source buttons and real mouse interactions. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.stack||String(e)));
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 let clicks=0,maxRound=1,botObserved=false,humanObserved=false,earlyCycle=false;
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__ROG_TEST__,null,{timeout:30000});
  await page.locator('.world-location[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  await page.locator('#lobby-create').click();
  assert.equal(await page.locator('#game-mode').inputValue(),'ai',
   'single human must default to AUTO COMPUTER opponent; manual 2-player mode previously stalled');
  await page.locator('#bot-count').selectOption('1');
  // This 34-cell No Item ORIGINAL DMP source is the shortest verified
  // map. Prove the complete match without using an artificial finish API.
  await page.locator('#map-select').selectOption('No Item');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)',{timeout:20000});
  let initial=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   return {mode:m.mode,map:m.map,total:m.tiles.length,bot:m.players[1].bot,
    botAutoplay:m.botAutoplay,players:m.players.length};
  });
  assert.deepEqual([initial.mode,initial.map,initial.total,initial.bot,initial.botAutoplay,
   initial.players],['ai','No Item',34,true,true,2]);
  // The previous UI tests ended HERE or after the first human roll. This
  // drives EVERY human turn until a genuine source goal event completes.
  const deadline=Date.now()+7*60*1000;
  let lastChange=Date.now(),lastSignature='',lastReason='';
  while(Date.now()<deadline){
   const state=await page.evaluate(()=>{
    const m=window.__ROG_TEST__?.getMatch();
    const md=document.getElementById('modal');
    return {
     round:m?.round,active:m?.active,finished:m?.finished,winner:m?.winner,
     botAutoplay:m?.botAutoplay,positions:m?.players?.map(p=>p.position),
     history:m?.history?.slice(-8)||[],historySize:m?.history?.length||0,
     canRoll:!document.getElementById('roll-btn').disabled,
     modal:md&&!md.classList.contains('hidden')?
       {title:document.getElementById('modal-title')?.textContent,
        choices:[...document.querySelectorAll('#modal-buttons button')].map(b=>b.textContent)}:null,
     message:m?.message
    };
   });
   maxRound=Math.max(maxRound,state.round||0);
   const signature=JSON.stringify([state.round,state.active,state.positions,
    state.historySize,state.finished,state.modal?.title]);
   if(signature!==lastSignature){lastChange=Date.now();lastSignature=signature}
   const recent=state.history.join(' ');
   if(recent.includes('컴퓨터')||recent.includes('COM ')||recent.includes('컴퓨터 1'))botObserved=true;
   if(state.historySize>0&&clicks>0)humanObserved=true;
   if(state.round>=2)earlyCycle=true;
   if(state.finished){
    assert.ok(maxRound>=2,'a full human/opponent turn cycle occurred before finish');
    assert.ok(clicks>=2,'real human used native roll button multiple turns');
    assert.ok(humanObserved,'source game created actual turn history');
    await page.locator('#leaf-original-match-result').waitFor({timeout:12000});
    assert.equal(await page.locator('#leaf-original-match-result table tbody tr').count(),2,
     'genuine final screen has two original match participants');
    const result=await page.locator('#leaf-original-match-result').textContent();
    assert.ok(result.includes('COMPLETE')&&result.includes('GP')&&result.includes('WIN RATE'),
     'actual original winResult sprite layout must be shown');
    await page.screenshot({path:'leaf-dice-complete-result.png'});
    const again=page.locator('#modal-buttons button',{hasText:'다시 시작'});
    await again.click();
    await page.locator('#lobby:not(.hidden)').waitFor({timeout:12000});
    await page.locator('#lobby-create').click();
    assert.equal(await page.locator('#start-game').isVisible(),true);
    console.log('4LEAF_DICE_COMPLETE_MATCH_AND_REPLAY_PASS',JSON.stringify({
     map:initial.map,total:initial.total,rounds:maxRound,humanRolls:clicks,
     winner:state.winner,finalPositions:state.positions,resultShown:true,replayReady:true,
     botEvidence:botObserved,errors:errors.length}));
    assert.deepEqual(errors,[],'no JS errors while finishing a real match');
    return;
   }
   if(state.modal){
    const selector=page.locator('#modal-buttons button');
    const options=state.modal.choices;
    const idx=options.findIndex(x=>!/(취소|포기|나가기)/.test(x));
    if(idx>=0){await selector.nth(idx).click();lastReason='resolved modal '+state.modal.title;}
    else throw Error('modal with no actionable choice: '+JSON.stringify(state.modal));
   }else if(state.active===0&&state.canRoll){
    await page.locator('#roll-btn').click();
    clicks++;
    lastReason='clicked native human dice turn '+clicks;
   }else{
    await page.waitForTimeout(250);
    lastReason='waiting for real original dice, animation or AI bot turn';
   }
   if(Date.now()-lastChange>35000)
    throw Error('gameplay stalled >35s, '+JSON.stringify({state,clicks,lastReason}));
  }
  throw Error('source gameplay failed to complete before 7 min: '+JSON.stringify({
   clicks,maxRound,botObserved,earlyCycle,lastReason}));
 }catch(error){
  console.error('4LEAF_DICE_COMPLETE_MATCH_FAIL',error.stack||String(error));
  await page.screenshot({path:'leaf-dice-cycle-failure.png',fullPage:true}).catch(()=>{});
  throw error;
 }finally{await browser.close()}
})().catch(()=>process.exit(1));
