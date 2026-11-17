'use strict';
/* End-to-end actual original CHR roster selection and persistent-save QA.
 * This guards a WEB storage failure, not an unverifiable historical rule.
 * Test each engine against the same original Room roster, not a JS mock.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
(async()=>{
 const browser=await (engine==='webkit'?webkit:chromium).launch(
  engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  const ctx=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const page=await ctx.newPage();
  const pageErrors=[];page.on('pageerror',e=>pageErrors.push(String(e)));
  await page.addInitScript(()=>{
   window.LEAF_CENTRAL_API_URL='';
   const original=Storage.prototype.setItem;
   Storage.prototype.setItem=function(k,v){
    if(k==='rog_profile'&&window.__denyProfileWrites)
     throw new DOMException('Simulated quota full','QuotaExceededError');
    return original.call(this,k,v);
   };
  });
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_DICE_ROSTER__?.getState()?.owned?.length>=4);
  const get=()=>page.evaluate(()=>({
   roster:window.__LEAF_DICE_ROSTER__.getState(),
   saved:localStorage.getItem('rog_profile'),
   match:localStorage.getItem('rog_match')
  }));
  const initial=await get();
  const spare=initial.roster.owned.find(c=>!initial.roster.team.includes(c.id));
  assert.ok(spare,'original test account has an unused source chessman');
  const testId=spare.id;
  await page.evaluate(()=>{window.__denyProfileWrites=true});
  const denied=await page.evaluate(id=>window.__LEAF_DICE_ROSTER__.equip(3,id),testId);
  assert.equal(denied,false,'an unsaved roster edit must not report success');
  const afterDeny=await get();
  assert.deepEqual(afterDeny.roster.team,initial.roster.team,'failed storage cannot change live lineup');
  assert.equal(afterDeny.saved,initial.saved,'failed storage cannot change durable source inventory');
  assert.equal(afterDeny.match,initial.match,'profile failure cannot destroy the active match record');
  assert.match(await page.locator('#modal-content').textContent(),/기존 출전 파티/);
  await page.locator('#modal-buttons button').first().click();
  await page.evaluate(()=>{window.__denyProfileWrites=false});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#dice-room-config:not(.hidden)').waitFor();
  // Use the ORIGINAL 794x404 Room/roomback CHESSMAN INFO rows,
  // not the hidden legacy HTML fallback #team-select.
  const selectedSlot=page.locator('#dice-native-selected-chessmen .dice-native-chessman-row[data-slot="3"]');
  await selectedSlot.click();
  assert.equal(await page.locator('#dice-native-stage').getAttribute('data-native-chessmen-active-slot'),'3');
  const actualNativeCard=page.locator('#dice-native-owned-chessmen .dice-native-chessman-row[data-card-id="'+testId+'"]');
  await actualNativeCard.click();
  await page.waitForFunction(id=>window.__LEAF_DICE_ROSTER__.getState().team[3]===id,testId);
  let updated=await get();
  assert.equal(updated.roster.team[3],testId,'real Room table equips fourth source actor');
  assert.equal(JSON.parse(updated.saved).team[3],testId,'new Room lineup actually persisted');
  const duplicate=await page.evaluate(id=>window.__LEAF_DICE_ROSTER__.equip(2,id),testId);
  assert.equal(duplicate,false,'one source card cannot equip in two live positions');
  assert.equal((await get()).saved,updated.saved,'rejected duplicate keeps original saved state');
  const unknown=await page.evaluate(()=>window.__LEAF_DICE_ROSTER__.equip(3,'unissued-source-id'));
  assert.equal(unknown,false,'unissued card must never be equipped');
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_DICE_ROSTER__?.getState());
  const final=await get();
  assert.equal(final.roster.team[3],testId,'source roster survives actual page reload');
  assert.ok(final.roster.team.length===4,'four real source cards remain equipped');
  assert.deepEqual(pageErrors.filter(e=>!/Failed to fetch|Load failed/.test(e)),[],
   'no unhandled roster errors');
  console.log('SOURCE ROSTER DURABLE PASS '+engine+' '+JSON.stringify({
   sourceId:testId,saveDenied:true,nativeRoomSelection:true,persistedThenReloaded:true,
   duplicateRejected:true,unissuedRejected:true
  }));
  await ctx.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE ROSTER DURABLE FAILED',e.stack||e);process.exit(1)});
