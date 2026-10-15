const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>window.__LEAF_REGISTRY_ALPHA__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.locator('[data-route="rooms"]').first().click();
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원작 스프라이트 검증',2));
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden) .social-avatar.self img');
  await page.waitForFunction(()=>document.querySelector('#rooms .social-avatar.self img')?.dataset.leafSavaMask==='true',null,{timeout:15000});
  const keyed=await page.evaluate(async()=>{
   const img=document.querySelector('#rooms .social-avatar.self img');
   const state=window.__LEAF_REGISTRY_ALPHA__.getState();
   const mask=new Image();
   mask.src=img.style.maskImage.match(/url\(["']?(.*?)["']?\)/)?.[1]||'';
   await mask.decode();
   const c=document.createElement('canvas');
   c.width=mask.width;c.height=mask.height;
   const ctx=c.getContext('2d',{willReadFrequently:true});
   ctx.drawImage(mask,0,0);
   const alpha=ctx.getImageData(0,0,c.width,c.height).data;
   let transparent=0,visible=0;
   for(let i=3;i<alpha.length;i+=4){
    if(alpha[i]===0)transparent++;else visible++;
   }
   return {state,img:img.src,masked:img.dataset.leafSavaMask,transparent,visible,
    maskWidth:mask.width,maskHeight:mask.height,css:img.style.maskImage.slice(0,35)};
  });
  assert.ok(keyed.img.includes('/original/Registry/sava'),'source actor image remains unaltered');
  assert.ok(keyed.transparent>500&&keyed.visible>500,'actual green key removed without deleting original character');
  assert.ok(keyed.maskWidth>=70&&keyed.maskHeight>=130,'source asset preserved at native resolution');
  assert.ok(keyed.state.masked>=1,'native alpha cached and shared with live sprite instances');
  await page.screenshot({path:'leaf-original-chroma-key-room.png'});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const info=await page.evaluate(()=>{
   const m=window.__ROG_TEST__.getMatch();
   const cards=[...document.querySelectorAll('#game .battle-side-card')];
   return {players:m.players.map(p=>({name:p.name,position:p.position,ability:p.ability})),
    occupied:cards.filter(x=>x.classList.contains('occupied')).map(x=>({
     slot:x.dataset.slot,source:x.querySelector('img')?.getAttribute('src'),
     name:x.querySelector('b')?.textContent,
     portrait:x.querySelector('.battle-side-portrait')?.getBoundingClientRect().height,
     cropped:x.querySelector('.battle-side-portrait img')?.getBoundingClientRect().height,
     background:getComputedStyle(x).backgroundImage})),
    vacant:cards.filter(x=>x.classList.contains('vacant')).map(x=>x.querySelector('img')),
    left:[...document.querySelectorAll('.battle-team-side.left .battle-side-card')].map(x=>x.dataset.slot),
    right:[...document.querySelectorAll('.battle-team-side.right .battle-side-card')].map(x=>x.dataset.slot)
   };
  });
  assert.deepEqual(info.left,['1','3','5'],'historical screenshot has odd-numbered left player rail');
  assert.deepEqual(info.right,['2','4','6'],'historical screenshot has even-numbered right player rail');
  assert.equal(info.occupied.length,info.players.length,'only actual participants have live portraits');
  assert.ok(info.vacant.every(x=>x===null),'empty slots are not invented players');
  assert.ok(info.occupied.every(x=>x.source.includes('/original/Registry/sava')&&x.background.includes('/original/IMG/avatarback.png')),'actual recovered Registry and IMG portrait source');
  assert.ok(info.occupied.every(x=>x.portrait>0&&x.portrait<x.cropped),'portrait crops original source head without deforming 75x141 actor');
  for(let i=0;i<info.players.length;i++)assert.equal(info.occupied[i].name,info.players[i].name,'portrait names reflect actual player');
  await page.waitForFunction(()=>[...document.querySelectorAll('#game .battle-side-card.occupied img')].every(x=>x.dataset.leafSavaMask==='true'),null,{timeout:15000});
  const oldInfo=await page.locator('#game .battle-side-card.occupied').first().locator('small').textContent();
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,null,{timeout:12000});
  assert.notEqual(await page.locator('#game .battle-side-card.occupied').first().locator('small').textContent(),oldInfo,'real movement refreshes actual player portrait status');
  await page.screenshot({path:'leaf-original-side-portraits-dice.png'});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('.battle-team-side.left .battle-side-card.occupied').count(),1);
  assert.equal(await page.locator('.battle-team-side.right .battle-side-card.occupied').count(),1);
  await page.screenshot({path:'leaf-original-side-portraits-mobile.png'});
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('ORIGINAL SAVA ALPHA + PLAYER RAILS PASS: real chroma key, genuine portraits, left 1/3/5 right 2/4/6, no NPCs, active match and responsive');
 }finally{await browser.close()}
})().catch(err=>{console.error('ORIGINAL SAVA ALPHA FAILED:',err.stack||err);process.exit(1)});
