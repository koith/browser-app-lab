const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 // Original player rail uses Registry/sava. Board combat actor uses OBS; party cards use CardData.\n // Screenshot reconstruction verification is local transport only; the
 // separate central-server integration suite exercises real authority.
 await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.locator('[data-route="rooms"]').first().click();
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원작 스프라이트 검증',2));
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden) .social-avatar.self img');
  // An img DOM node can exist before its original 75x141 PNG has decoded.
  // Live Pages/CDN timing is unlike localhost; never read pixels from 0x0.
  await page.waitForFunction(()=>{
   const img=document.querySelector('#rooms.classic-chat-room .social-avatar.self img');
   return img?.complete&&img.naturalWidth===75&&img.naturalHeight===141;
  },null,{timeout:25000});
  const source=await page.evaluate(()=>{
   const img=document.querySelector('#rooms .social-avatar.self img');
   const canvas=document.createElement('canvas');
   canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});
   ctx.drawImage(img,0,0);
   const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;
   let invisible=0,visible=0,leakedKey=0;
   for(let i=0;i<data.length;i+=4){
    if(data[i+3]===0)invisible++;
    else{
     visible++;
     if(data[i+1]>=225&&data[i]<50&&data[i+2]<50)leakedKey++;
    }
   }
   return {source:img.getAttribute('src'),size:[canvas.width,canvas.height],
    corner:[...ctx.getImageData(0,0,1,1).data],invisible,visible,leakedKey};
  });
  assert.ok(source.source.includes('./original/Registry/sava'),'the original source image stays unmodified');
  assert.deepEqual(source.size,[75,141],'archived SAVA actor bitmap is truly 75x141');
  assert.equal(source.corner[3],0,'the original PNG ALREADY has transparent alpha in the apparent green field');
  assert.ok(source.invisible>500&&source.visible>500,'native character silhouette remains distinct from source transparency');
  assert.equal(source.leakedKey,0,'native transparent edge has no visible chroma-key pixels');
  await page.screenshot({path:'leaf-original-transparent-sava-room.png'});
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.waitForFunction(()=>{
   const els=[...document.querySelectorAll('#game .battle-side-card.occupied img')];
   return els.length>=2&&els.every(img=>img.complete&&img.naturalWidth===75&&img.naturalHeight===141&&img.getAttribute('src').includes('/original/Registry/sava'));
  },null,{timeout:25000});
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
  assert.ok(info.occupied.every(x=>x.source.includes('/original/Registry/sava')&&x.background.includes('/original/IMG/avatarback.png')),'genuine Registry SAVA avatar portraits inside historic IMG player rails');
  assert.ok(info.occupied.every(x=>x.portrait>0&&x.cropped>0&&x.portrait<=x.cropped),'native 75x141 avatar is cropped into source player rail without distortion');
  for(let i=0;i<info.players.length;i++)assert.equal(info.occupied[i].name,info.players[i].name,'portrait names reflect actual player');
  await page.waitForFunction(()=>[...document.querySelectorAll('#game .battle-side-card.occupied img')].every(x=>x.complete&&x.naturalWidth===75&&x.naturalHeight===141&&x.getAttribute('src').includes('/original/Registry/sava')),null,{timeout:15000});
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
  console.log('ORIGINAL CHAT SAVA ALPHA + GENESIS SAVA PLAYER RAILS PASS: correct separate sources, left 1/3/5 right 2/4/6, live matches and responsive');
 }finally{await browser.close()}
})().catch(err=>{console.error('ORIGINAL PLAYER RAILS FAILED:',err.stack||err);process.exit(1)});
