'use strict';
/* Real browser acceptance: a corrupt/finished match MUST NOT be overwritten
 * when browser quota/privacy mode prevents byte-for-byte recovery backup.
 * The next user retry after storage becomes writable can start normally.
 * No mocks of the game, rules, rendering or page navigation. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

const BASE=process.env.FOURLEAF_SMOKE_URL||'http://127.0.0.1:8765/';
const cases=[
 {name:'truncated JSON',raw:'{"version":5,"map":"4LEAF","players":[',backup:'rog_match_invalid_backup_v1'},
 {name:'schema-invalid JSON',raw:JSON.stringify({version:5,map:'4LEAF',players:[],history:['do not delete']}),backup:'rog_match_invalid_backup_v1'},
 {name:'completed match',raw:JSON.stringify({version:5,map:'4LEAF',finished:true,history:['completed outcome remains']}),
  backup:'rog_match_finished_backup_v1'}
];

test('real game start fails closed if and only if prior-game archival cannot be written',async t=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 t.after(()=>browser.close());
 for(const scenario of cases){
  await t.test(scenario.name,async()=>{
   const context=await browser.newContext({serviceWorkers:'block',viewport:{width:1280,height:900}});
   try{
    const page=await context.newPage();
    await page.addInitScript(()=>{
     window.LEAF_CENTRAL_API_URL='';
     const original=Storage.prototype.setItem;
     Storage.prototype.setItem=function(key,value){
      if(this===localStorage&&String(key).includes('backup_v1')&&
       sessionStorage.getItem('__leaf_recovery_write_blocked')==='1'){
       throw new DOMException('Simulated browser full quota','QuotaExceededError');
      }
      return original.call(this,key,value);
     };
    });
    await page.goto(BASE);
    await page.waitForFunction(()=>Boolean(window.__ROG_TEST__));
    await page.evaluate(raw=>{
     localStorage.setItem('rog_match',raw);
     sessionStorage.setItem('__leaf_recovery_write_blocked','1');
    },scenario.raw);
    await page.reload();
    await page.waitForFunction(()=>Boolean(window.__ROG_TEST__));
    assert.equal(await page.evaluate(()=>window.__ROG_TEST__.getMatch()),null,
     'bad/inactive prior saved match must not become playable');
    await page.locator('[data-route="lobby"]').first().click();
    await page.locator('#lobby-create').click();
    await page.locator('#start-game').click();
    await page.locator('#modal:not(.hidden)').waitFor({timeout:6000});
    assert.equal((await page.locator('#modal-title').textContent()).trim(),'기존 경기 보존 실패');
    assert.equal(await page.locator('#game').isVisible(),false,'never start an unsaveable match');
    const refused=await page.evaluate(key=>({
     saved:localStorage.getItem('rog_match'),backup:localStorage.getItem(key),
     match:window.__ROG_TEST__.getMatch()
    }),scenario.backup);
    assert.equal(refused.saved,scenario.raw,'the exact previous bytes are still recoverable');
    assert.equal(refused.backup,null,'failed backup must not invent a success marker');
    assert.equal(refused.match,null,'failed preflight must not mutate active match');
    await page.locator('#modal-buttons button').filter({hasText:'확인'}).click();
    // Browser quota restored: retry the EXACT same user action, no page reload.
    await page.evaluate(()=>sessionStorage.removeItem('__leaf_recovery_write_blocked'));
    await page.locator('#start-game').click();
    await page.waitForSelector('#game:not(.hidden)',{timeout:15000});
    const accepted=await page.evaluate(key=>({
     saved:localStorage.getItem('rog_match'),backup:localStorage.getItem(key),
     match:window.__ROG_TEST__.getMatch()
    }),scenario.backup);
    assert.equal(accepted.backup,scenario.raw,
     'successful retry must first save the original damaged/completed bytes exactly');
    assert.ok(accepted.match&&!accepted.match.finished&&accepted.match.players.length>=2);
    assert.deepEqual(JSON.parse(accepted.saved).players.map(p=>p.name),
     accepted.match.players.map(p=>p.name),'new game persisted, not just shown on screen');
    await page.reload();
    await page.waitForFunction(()=>Boolean(window.__ROG_TEST__));
    const restored=await page.evaluate(()=>window.__ROG_TEST__.getMatch());
    assert.ok(restored&&restored.map===accepted.match.map,
     'new game survives reload after safe backup');
    assert.equal(await page.evaluate(key=>localStorage.getItem(key),scenario.backup),
     scenario.raw,'recovery copy remains untouched after reload');
    console.log('CORRUPT SAVE PREFLIGHT PASS',scenario.name);
   }finally{await context.close();}
  });
 }
});
