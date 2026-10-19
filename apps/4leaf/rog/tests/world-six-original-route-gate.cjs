'use strict';
/* Actual WorldMap source & route acceptance for ALL six clickable places.
 * Not a screenshot collage: each source bitmap, scene transition, backlink,
 * and the real user's selected original Registry avatar is tested in Chromium.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const errors=[];page.on('pageerror',x=>errors.push(x.message));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_SOCIAL__&&window.__LEAF_LOBBY__);
  const regions=['street','knights','north','south','dice','my4leaf'];
  const proof=await page.evaluate(()=>{
   const stage=document.querySelector('#leaf-world-stage'),sprites=[...stage.querySelectorAll('.world-sprite')];
   const image=stage.querySelector('.world-backdrop');
   return {stage:[stage.offsetWidth,stage.offsetHeight],source:image?.getAttribute('src'),
    regions:[...stage.querySelectorAll('.world-location')].map(b=>b.dataset.region),
    sourceSprites:sprites.length,captions:stage.querySelectorAll('.world-map-caption').length};
  });
  assert.deepEqual(proof.stage,[796,528]);
  assert.equal(proof.source,'./original/WorldMap/worldmapback.png');
  assert.deepEqual(proof.regions,regions,'the original six native map regions are real click targets');
  assert.equal(proof.sourceSprites,6);
  assert.equal(proof.captions,0,'never paint duplicate region labels on source bitmap');
  const snapshots=[];
  const back=async()=>{
   await page.waitForSelector('#sky:not(.hidden)');
   assert.equal(await page.locator('#leaf-world-stage .world-location').count(),6);
  };
  await page.locator('[data-region="street"]').click();
  await page.waitForSelector('#city:not(.hidden)');
  assert.equal(await page.locator('#street-track .street-artwork').getAttribute('src'),
   './original/MainStreet/back.png');
  snapshots.push({region:'street',scene:'city',source:'MainStreet/back.png'});
  await page.locator('#street-back').click();await back();
  await page.locator('[data-region="knights"]').click();
  await page.waitForSelector('#rooms:not(.hidden)');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'knighttown');
  assert.equal(await page.locator('.knight-district-hotspot').count(),6);
  assert.match(await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage),
   /original\\/KnightTown\\/knightback\\.png/);
  snapshots.push({region:'knights',scene:'rooms:knighttown',source:'KnightTown/knightback.png'});
  await page.locator('#social-back').click();await back();
  for(const region of ['north','south']){
   await page.locator('[data-region="'+region+'"]').click();
   await page.waitForSelector('#rooms:not(.hidden)');
   assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),region);
   assert.equal(await page.locator('.social-district-hotspot').count(),8);
   const image=await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage);
   assert.ok(image.includes('original/ChatTown/'+region+'back.png'));
   assert.equal(await page.locator('#social-image-frame').evaluate(el=>el.offsetHeight),404);
   assert.equal(await page.locator('#dice-channels.hidden').count(),1,'ChatTown not the Genesis dice channel selector');
   snapshots.push({region,scene:'rooms:town',source:'ChatTown/'+region+'back.png'});
   await page.locator('[data-route="sky"]').first().click();await back();
  }
  await page.locator('[data-region="dice"]').click();
  await page.waitForSelector('#dice-channels:not(.hidden)');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28);
  assert.match(await page.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage),
   /original\\/Region\\/regionback\\.png/);
  await page.locator('#dice-channels [data-channel="ispin:1"]').click();
  await page.waitForSelector('#lobby:not(.hidden)');
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:1');
  await page.locator('#lobby-channel-change').click();
  await page.locator('#dice-channel-back').click();await back();
  snapshots.push({region:'dice',scene:'channels:genesis/lobby',source:'Region/regionback.png'});
  await page.locator('[data-region="my4leaf"]').click();
  const profile=page.locator('#world-profile-modal');
  await profile.waitFor();
  let avatar=await profile.locator('.world-profile-body img').evaluate(img=>({
   src:img.getAttribute('src'),index:img.dataset.avatarIndex,
   source:img.dataset.originalSourceMember
  }));
  assert.equal(avatar.src,'./original/Registry/sava00.png');
  assert.equal(avatar.index,'0');
  await profile.locator('.world-profile-heading button').click();await back();
  // Registry persists source avatar choice in storage; a reloaded scene
  // must use the true source ID from the user's currently selected avatar.
  await page.evaluate(()=>localStorage.setItem('leaf_social_avatar','2'));
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState?.().avatar===2);
  await page.locator('[data-region="my4leaf"]').click();
  avatar=await page.locator('#world-profile-modal .world-profile-body img').evaluate(img=>({
   src:img.getAttribute('src'),index:img.dataset.avatarIndex,source:img.dataset.originalSourceMember
  }));
  assert.deepEqual(avatar,{src:'./original/Registry/sava06.png',
   index:'2',source:'Registry/sava06.png'},'My4LEAF portrait must match actual selected Registry avatar, not show a fabricated sava00 duplicate');
  await page.locator('#world-profile-modal .world-profile-heading button').click();
  await back();
  snapshots.push({region:'my4leaf',scene:'actual user Registry profile',source:avatar.source});
  assert.equal(snapshots.length,6);
  assert.deepEqual(errors,[],'no JS exceptions during full real WorldMap route tour');
  console.log('ALL SIX REAL 4LEAF WORLD ROUTES PASS '+JSON.stringify({source:proof,snapshots}));
  await page.screenshot({path:'leaf-world-six-routes-finish.png'});
 }finally{await browser.close()}
})().catch(x=>{console.error('SIX WORLD ROUTES QA FAILED',x.stack||x);process.exit(1)});
