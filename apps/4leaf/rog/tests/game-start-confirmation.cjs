'use strict';
// Exercise the real user-facing replacement flow. A pending local match is
// protected by an explicit dialog; tests must not wait forever for #game.
const assert=require('node:assert/strict');
async function startGameWithConfirmation(page,{expectSaved=false,verifyCancel=false}={}){
 await page.locator('#start-game').click();
 const modal=page.locator('#modal:not(.hidden)');
 const protectedMatch=await modal.isVisible();
 if(expectSaved)assert.equal(protectedMatch,true,
  'new-game flow MUST ask before replacing a live saved match');
 if(protectedMatch){
  assert.equal((await page.locator('#modal-title').textContent()).trim(),
   '진행 중인 경기 보호','unexpected modal must never be dismissed as a saved-match confirmation');
  if(verifyCancel){
   const before=await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch()));
   await modal.locator('#modal-buttons button').filter({hasText:'기존 경기 유지'}).click();
   assert.equal(await page.locator('#modal').isVisible(),false,'cancel closes protection dialog');
   assert.equal(await page.evaluate(()=>JSON.stringify(window.__ROG_TEST__.getMatch())),before,
    'cancelling replacement leaves the entire active match exactly untouched');
   await page.locator('#start-game').click();
   await modal.waitFor({state:'visible'});
   assert.equal((await page.locator('#modal-title').textContent()).trim(),'진행 중인 경기 보호');
  }
  await modal.locator('#modal-buttons button').filter({hasText:'새 경기 시작'}).click();
 }
 await page.waitForSelector('#game:not(.hidden)',{timeout:15000});
 return {replaced:protectedMatch};
}
module.exports={startGameWithConfirmation};
