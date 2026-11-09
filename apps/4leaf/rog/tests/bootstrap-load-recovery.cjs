'use strict';
/* Real-browser fault injection: a failed essential parser-blocking script
 * must not strand the user at an unresponsive WorldMap. Verify recovery only
 * once, safe fallback on a persistent outage, and genuine post-retry clicks.
 * No __ROG_TEST__.go() navigation shortcuts are used. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},
   isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const page=await context.newPage();
  let failures=0,visits=0;
  page.on('framenavigated',frame=>{
   if(frame===page.mainFrame()&&frame.url().startsWith(base))visits++;
  });
  await page.route('**/world-map.js',async route=>{
   if(failures++===0)await route.abort('failed');
   else await route.continue();
  });
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_BOOT_RECOVERY__?.state==='ready'
    && window.__ROG_TEST__&&window.__LEAF_WORLD__&&window.__LEAF_SOCIAL__&&window.__LEAF_LOBBY__,
    null,{timeout:35000});
  assert.equal(visits,2,'first missing critical script must trigger exactly ONE automatic retry');
  assert.ok(failures>=2,'critical script was actually requested again on reload');
  assert.equal(await page.locator('#leaf-bootstrap-recovery-alert').count(),0,
   'successfully recovered app must not show a false error banner');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem(
   '4leaf-bootstrap-retry:'+document.querySelector('meta[name="leaf-revival-version"]').content)),
   null,'successful return clears the retry guard');
  await page.locator('.world-location[data-region="north"]').tap();
  await page.locator('#rooms:not(.hidden)').waitFor({timeout:15000});
  assert.ok(await page.locator('#rooms:not(.hidden)').count()===1,
   'recovered WorldMap button must open actual ChatTown');
  console.log('4LEAF_BOOT_RECOVERY_ONE_FAILURE_PASS',JSON.stringify({visits,failures}));
  await context.close();

  const second=await browser.newContext({viewport:{width:390,height:844},
   isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const broken=await second.newPage();
  let brokenVisits=0;
  broken.on('framenavigated',frame=>{
   if(frame===broken.mainFrame()&&frame.url().startsWith(base))brokenVisits++;
  });
  await broken.route('**/world-map.js',route=>route.abort('failed'));
  await broken.goto(base,{waitUntil:'domcontentloaded'});
  await broken.locator('#leaf-bootstrap-recovery-alert[role="alert"]').waitFor({timeout:35000});
  assert.equal(brokenVisits,2,'persistent failure must make one automatic retry, not an endless loop');
  assert.equal(await broken.locator('#leaf-bootstrap-recovery-alert button').textContent(),
   '다시 불러오기','persistent failure exposes an accessible manual retry');
  await broken.waitForTimeout(1100);
  assert.equal(brokenVisits,2,'persistent outage must not silently reload again');
  console.log('4LEAF_BOOT_RECOVERY_PERSISTENT_FAILURE_PASS',
   JSON.stringify({visits:brokenVisits}));

  // Static status copy must match actual supported features and clearly
  // distinguish original-server matchmaking from WebRTC direct play.
  // Social Chat dynamically replaces the original placeholder scene after
  // boot; inspect the actual shipped HTML source rather than demanding
  // deleted placeholders remain in the live post-render DOM.
  const sourceHtml=await broken.evaluate(()=>fetch('./index.html').then(r=>r.text()));
  assert.ok(sourceHtml.includes('WebRTC를 이용한 기기 간 2인 직접 대전을 지원합니다.'));
  assert.ok(sourceHtml.includes('채팅은 실제 서버 연결 시 다른 이용자에게 실시간으로 전달됩니다.'));
  assert.ok(!sourceHtml.includes('실제 접속자와 연결되지 않습니다.'));
  console.log('4LEAF_LIVE_CAPABILITY_COPY_PASS');
  await second.close();
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF_BOOT_RECOVERY_QA_FAILED',e.stack||String(e));process.exit(1)});
