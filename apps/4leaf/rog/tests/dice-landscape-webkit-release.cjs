'use strict';
/* Real browser rendering in iPhone portrait -> landscape, not a source
 * screenshot pasted over a web view. WebKit on CI is an iOS proxy,
 * never claim this proves hardware Safari/PWA visual equivalence.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const {webkit}=require('playwright');
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},
    deviceScaleFactor:2,isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||
    'http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__);
  const version=await page.locator('meta[name="leaf-revival-version"]').getAttribute('content');
  // Do not freeze a previously released beta in a browser acceptance test:
  // compare the actual rendered build against its canonical release metadata.
  assert.equal(version,require('../app-version.json').version);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>document.querySelectorAll('#board-nodes>.tile').length===104&&
   document.querySelectorAll('#board-pawns .leaf-chess-original-obs').length===2);
  const positions=await page.evaluate(()=>window.__ROG_TEST__.getMatch().players.map(x=>x.position));
  const orientations=[];
  for(const size of [{width:390,height:844},{width:844,height:390}]){
   await page.setViewportSize(size);
   await page.waitForTimeout(300);
   const layout=await page.evaluate(()=>{
    const rect=el=>{const r=el.getBoundingClientRect();return {
      x:r.x,y:r.y,w:r.width,h:r.height,visible:r.width>8&&r.height>8}};
    const board=document.getElementById('board-area');
    const roll=document.getElementById('roll-btn');
    const source=[...document.querySelectorAll('#board-nodes>.tile')];
    const actors=[...document.querySelectorAll('#board-pawns .board-pawn')];
    return {screen:[innerWidth,innerHeight],
     board:rect(board),roll:rect(roll),
     tiles:source.length,
     original:source.every(el=>el.offsetWidth===145&&el.offsetHeight===97),
     camera:window.__LEAF_CAMERA__.getState().visible,
     rigs:actors.map(a=>a.dataset.actorRig),
     match:window.__ROG_TEST__.getMatch().players.map(p=>p.position)};
   });
   assert.deepEqual(layout.screen,[size.width,size.height]);
   assert.equal(layout.tiles,104);
   assert.ok(layout.original,'all 104 native TIS stay 145x97 when phone rotates');
   assert.ok(layout.board.visible&&layout.board.w>=125,
    'landscape must not collapse actual original DMP camera');
   assert.ok(layout.roll.visible,'actual original ROLL remains in rendered scene');
   assert.ok(layout.rigs.every(x=>x==='original-obs-sprite'),
    'both original Genesis OBS chessmen remain on scene after rotation');
   assert.deepEqual(layout.match,positions,'rotation cannot change dice results or move source players');
   assert.ok(layout.camera?.width>0&&layout.camera?.height>0);
   orientations.push(layout);
  }
  // Actually press the web rendering of the original ROLL GUI on
  // WebKit landscape. A fake screenshot or hidden button cannot do this.
  const roll=page.locator('#roll-btn');
  await roll.scrollIntoViewIfNeeded();
  const target=await roll.evaluate(el=>{
   const r=el.getBoundingClientRect();
   const top=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   return {same:top===el||el.contains(top),actual:top?.id,
      expected:el.id,rect:[r.x,r.y,r.width,r.height]};
  });
  assert.ok(target.same,'ROLL action is physically hit-testable after iPhone rotation: '+JSON.stringify(target));
  await roll.click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,
    null,{timeout:18000});
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-webkit-iphone-landscape-v084.png'});
  console.log('4LEAF WEBKIT PORTRAIT/LANDSCAPE ACTUAL ROLL PASS',
   JSON.stringify({version,orientations:orientations.map(o=>({
    screen:o.screen,board:o.board,roll:o.roll,tiles:o.tiles,actors:o.rigs})),
    rolledPosition:await page.evaluate(()=>window.__ROG_TEST__.getMatch().players[0].position)}));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF WEBKIT LANDSCAPE RELEASE FAILED',e.stack||e);process.exit(1)});
