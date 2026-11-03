'use strict';
/* Round4 source DMP tile/actor painter order across all map choices.
 * Default sample every 13th source cell for CI. FULL_SWEEP=1 tests every cell.
 * This is a WEB painter approximation; historical 3D/MVE mesh UNVERIFIED. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const errors=[];page.on('pageerror',x=>errors.push(x.message));
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const report=[];
 try{
  await page.goto(url);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__);
  const maps=await page.$$eval('#map-select option',opts=>opts.map(x=>x.value).filter(Boolean));
  assert.ok(maps.length>=26,'all DMP source maps selectable: '+maps.length);
  for(const map of maps){
   await page.goto(url);
   await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&
    Object.keys(window.ORIGINAL_LEAF_FULL_ACTION_FRAMES||{}).length===45);
   await page.locator('[data-route="lobby"]').first().click();
   await page.locator('#lobby-create').click();
   await page.locator('#game-mode').selectOption('hotseat');
   await page.locator('#bot-count').selectOption('3');
   await page.locator('#map-select').selectOption(map);
   await page.locator('#start-game').click();
   // Later maps share this browser's unfinished local save. Replacing it
   // is a deliberate QA action and must use the real consent button.
   if(report.length){
    await page.locator('#modal:not(.hidden)').waitFor();
    assert.match(await page.locator('#modal-title').textContent(),/진행 중인 경기 보호/);
    await page.locator('#modal-buttons button').filter({hasText:'새 경기 시작'}).click();
   }
   await page.waitForSelector('#game:not(.hidden)');
   const stride=process.env.FOURLEAF_FULL_SWEEP==='1'?1:13;
   const result=await page.evaluate(async stride=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players.forEach((p,i)=>{p.team=['c_'+['0088','0046','0078','0040'][i%4]]});
    const n=m.tiles.length,bad=[];
    const alphaCache=new Map();
    const tileAlpha=async(tile,x,y)=>{
     const src=(getComputedStyle(tile).backgroundImage.match(/url\("?(.*?)"?\)/)||[])[1];
     if(!src)return 0;
     if(!alphaCache.has(src)){
      const im=new Image();im.src=src;await im.decode();
      const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;
      const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);
      alphaCache.set(src,{w:c.width,h:c.height,p:ctx.getImageData(0,0,c.width,c.height).data});
     }
     const a=alphaCache.get(src),r=tile.getBoundingClientRect();
     const sx=Math.floor((x-r.left)/r.width*a.w),sy=Math.floor((y-r.top)/r.height*a.h);
     return sx<0||sy<0||sx>=a.w||sy>=a.h?0:a.p[(sy*a.w+sx)*4+3];
    };
    let checked=0;
    for(let index=0;index<n;index+=stride){
     m.players.forEach((p,k)=>{p.position=k===0?index:(index+(n>>1)+k)%n});
     T.setMatch(m);T.drawGame();
     const p=document.querySelector('#board-pawns .board-pawn[data-id="'+m.players[0].id+'"]');
     // Wait for real camera and painter layout to settle, not synthetic positions.
     let prev='',stable=0;
     for(let i=0;i<90;i++){
      await new Promise(resolve=>requestAnimationFrame(resolve));
      const r=p.getBoundingClientRect(),board=document.getElementById('board-nodes').getBoundingClientRect();
      const key=[r.x,r.y,board.x,board.y].join();
      stable=key===prev&&p.dataset.position===String(index)?stable+1:0;
      prev=key;if(stable>=3)break;
     }
     const img=p.querySelector('img.leaf-chess-original-obs');
     if(!img)continue;
     checked++;
     const body=img.getBoundingClientRect(),pawn=p.getBoundingClientRect();
     const z=Number(getComputedStyle(p).zIndex),center=pawn.left+pawn.width/2;
     for(const tile of document.querySelectorAll('#board-nodes>.tile')){
      if(Number(tile.style.zIndex)<=z)continue;
      const t=tile.getBoundingClientRect();
      if(Math.min(body.right,t.right)-Math.max(body.left,t.left)<=4||
         Math.min(body.bottom-8,t.bottom)-Math.max(body.top,t.top)<=4)continue;
      let count=0;
      for(let y=Math.max(body.top,t.top);y<Math.min(body.bottom-8,t.bottom);y+=3)
       for(let x=center-10;x<=center+10;x+=5)
        if(x>=t.left&&x<t.right&&await tileAlpha(tile,x,y)>128)count++;
      if(count>2)bad.push({index,frontTile:tile.dataset.tile,count});
     }
    }
    m.players.forEach(p=>{p.position=1});T.setMatch(m);T.drawGame();
    await new Promise(resolve=>setTimeout(resolve,120));
    const own=Number(document.querySelector('#board-nodes>.tile[data-tile="1"]').style.zIndex);
    const formation=[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
     row:Number(p.dataset.formationRow),z:Number(getComputedStyle(p).zIndex)}));
    return {n,bad,checked,expected:Math.ceil(n/stride),own,formation};
   },stride);
   assert.equal(result.checked,result.expected,map+' sampled original cells');
   assert.deepEqual(result.bad,[],map+' false painter overlap');
   assert.equal(result.formation.length,4);
   for(const p of result.formation)assert.ok(p.z>result.own&&p.z<=result.own+7);
   const rear=result.formation.filter(x=>x.row===1),front=result.formation.filter(x=>x.row===0);
   assert.equal(rear.length,1,map+' original formation rear');
   assert.ok(rear.every(r=>front.every(f=>r.z<f.z)),map+' rear must paint below front');
   report.push({map,checked:result.checked,cells:result.n});
  }
  assert.deepEqual(errors,[]);
  console.log('ROUND4 SOURCE DMP FORMATION QA PASS',JSON.stringify({
   maps:report.length,stride:process.env.FOURLEAF_FULL_SWEEP==='1'?1:13,
   cellsChecked:report.reduce((s,x)=>s+x.checked,0),report}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ROUND4 ALL MAP DEPTH FAILED',e.stack||e);process.exit(1)});
