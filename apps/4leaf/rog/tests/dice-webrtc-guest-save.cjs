'use strict';
/* Real Chromium guest WebRTC match acceptance.
 * Inbound data must reach localStorage BEFORE live game state changes.
 * Browser quota failures and unreadable previous saves must not be lost.
 * No production peer, network credentials, or real match records involved.
 */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {startGameWithConfirmation}=require('./game-start-confirmation.cjs');
const BASE=process.env.FOURLEAF_SMOKE_URL||'http://127.0.0.1:8765/';

test('guest accepts only durable remote games, preserves both valid and damaged saves',async t=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 t.after(()=>browser.close());
 const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
 t.after(()=>context.close());
 const page=await context.newPage();
 const pageErrors=[];page.on('pageerror',e=>pageErrors.push(String(e)));
 await page.addInitScript(()=>{
  window.LEAF_CENTRAL_API_URL='';
  const save=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){
   if(this===localStorage&&key==='rog_match'&&
      sessionStorage.getItem('__leaf_guest_match_blocked')==='1')
    throw new DOMException('Simulated guest save quota','QuotaExceededError');
   if(this===localStorage&&String(key).includes('backup_v1')&&
      sessionStorage.getItem('__leaf_guest_backup_blocked')==='1')
    throw new DOMException('Simulated recovery quota','QuotaExceededError');
   return save.call(this,key,value);
  };
 });
 await page.goto(BASE);
 await page.waitForFunction(()=>!!window.__ROG_TEST__&&!!window.__LEAF_BRIDGE__);
 await page.locator('[data-route="lobby"]').first().click();
 await page.locator('#lobby-create').click();
 await startGameWithConfirmation(page);
 const candidate=await page.evaluate(()=>{
  const oldRaw=localStorage.getItem('rog_match');
  const oldMatch=window.__LEAF_BRIDGE__.getMatch();
  const remote=structuredClone(oldMatch);
  remote.mode='network';
  remote.players[0].name='원격 호스트 안전검증';
  sessionStorage.setItem('__leaf_test_remote',JSON.stringify(remote));
  sessionStorage.setItem('__leaf_guest_match_blocked','1');
  window.__LEAF_NET__.role='guest';
  const accepted=window.__LEAF_BRIDGE__.receiveMatch(remote);
  return {oldRaw,oldName:oldMatch.players[0].name,accepted,
   stored:localStorage.getItem('rog_match'),
   live:window.__LEAF_BRIDGE__.getMatch().players[0].name};
 });
 assert.ok(candidate.oldRaw&&candidate.oldRaw.length>100,'actual existing source game is persisted');
 assert.equal(candidate.accepted,false,'denied write must reject remote state');
 assert.equal(candidate.stored,candidate.oldRaw,'old saved bytes survive quota denial');
 assert.equal(candidate.live,candidate.oldName,'old in-memory match must remain authoritative');
 assert.equal((await page.locator('#modal-title').textContent()).trim(),
  '연결된 경기 저장 실패','user sees a truthful save failure rather than phantom game');
 await page.locator('#modal-buttons button').filter({hasText:'확인'}).click();
 const retry=await page.evaluate(()=>{
  sessionStorage.removeItem('__leaf_guest_match_blocked');
  const remote=JSON.parse(sessionStorage.getItem('__leaf_test_remote'));
  const accepted=window.__LEAF_BRIDGE__.receiveMatch(remote);
  return {accepted,stored:localStorage.getItem('rog_match'),
   live:window.__LEAF_BRIDGE__.getMatch().players[0].name,
   target:JSON.stringify(remote)};
 });
 assert.equal(retry.accepted,true,'same actual guest update succeeds after quota recovery');
 assert.equal(retry.stored,retry.target,'remote match is durably committed before drawing');
 assert.equal(retry.live,'원격 호스트 안전검증');
 await page.reload();await page.waitForFunction(()=>!!window.__ROG_TEST__);
 assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch()?.players[0]?.name),
  '원격 호스트 안전검증','guest state survives a full page restart');

 // Older malformed bytes must be archived rather than overwritten by
 // a successfully writable new guest game.
 const damaged='{"old":"do not erase","players":[';
 await page.evaluate(raw=>{
  localStorage.setItem('rog_match',raw);
  sessionStorage.setItem('__leaf_guest_backup_blocked','1');
 },damaged);
 await page.reload();await page.waitForFunction(()=>!!window.__LEAF_BRIDGE__);
 const refused=await page.evaluate(()=>{
  window.__LEAF_NET__.role='guest';
  const remote=JSON.parse(sessionStorage.getItem('__leaf_test_remote'));
  const accepted=window.__LEAF_BRIDGE__.receiveMatch(remote);
  return {accepted,stored:localStorage.getItem('rog_match'),
   backup:localStorage.getItem('rog_match_invalid_backup_v1'),
   live:window.__LEAF_BRIDGE__.getMatch()};
 });
 assert.equal(refused.accepted,false,'missing recovery backup must block incoming game');
 assert.equal(refused.stored,damaged,'malformed previous save bytes cannot be erased');
 assert.equal(refused.backup,null,'failed backup is not counted as a successful copy');
 assert.equal(refused.live,null,'guest game must not be activated before backup');
 assert.equal((await page.locator('#modal-title').textContent()).trim(),'기존 경기 보존 실패');
 await page.locator('#modal-buttons button').filter({hasText:'확인'}).click();
 const recovered=await page.evaluate(()=>{
  sessionStorage.removeItem('__leaf_guest_backup_blocked');
  const remote=JSON.parse(sessionStorage.getItem('__leaf_test_remote'));
  const accepted=window.__LEAF_BRIDGE__.receiveMatch(remote);
  return {accepted,backup:localStorage.getItem('rog_match_invalid_backup_v1'),
   current:localStorage.getItem('rog_match')};
 });
 assert.equal(recovered.accepted,true,'retry must work without reloading after permission recovery');
 assert.equal(recovered.backup,damaged,'corrupt original saved byte-for-byte before new game');
 assert.equal(JSON.parse(recovered.current).players[0].name,'원격 호스트 안전검증');
 assert.deepEqual(pageErrors,[],'no unhandled browser errors');
});
