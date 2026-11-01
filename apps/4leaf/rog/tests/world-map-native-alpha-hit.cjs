'use strict';
/* Live source WorldMap sprites: physical click must not activate transparent
 * chroma-key pixels. Six original PNGs are the runtime mask, not rectangles.
 * This is a source-asset-backed improvement, not proof of 2002 EXE hit rules. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const browserType=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await browserType.launch({headless:true,
  args:browserType===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({
  viewport:{width:1280,height:900},serviceWorkers:'block',reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__ROG_TEST__&&
   [...document.querySelectorAll('#leaf-world-stage canvas.world-sprite')].length===6&&
   [...document.querySelectorAll('#leaf-world-stage canvas.world-sprite')]
    .every(s=>s.dataset.ready==='true'),null,{timeout:20000});
  const source=await page.evaluate(()=>{
   const stage=document.querySelector('#leaf-world-stage');
   const buttons=[...stage.querySelectorAll('.world-location')];
   const sprites=[...stage.querySelectorAll('canvas.world-sprite')];
   const rows=[];
   for(let i=0;i<buttons.length;i++){
    const button=buttons[i],sprite=sprites[i];
    const rect=button.getBoundingClientRect(),canvasRect=sprite.getBoundingClientRect();
    const pixels=sprite.getContext('2d',{willReadFrequently:true})
     .getImageData(0,0,sprite.width,sprite.height).data;
    let clear=null,opaque=null,sourceClear=0,sourceOpaque=0;
    const x0=Math.ceil(Math.max(rect.left,canvasRect.left))+2,
     x1=Math.floor(Math.min(rect.right,canvasRect.right))-2;
    const y0=Math.ceil(Math.max(rect.top,canvasRect.top))+2,
     y1=Math.floor(Math.min(rect.bottom,canvasRect.bottom))-2;
    for(let y=y0;y<=y1;y+=2)for(let x=x0;x<=x1;x+=2){
     const sx=Math.floor((x-canvasRect.left)*sprite.width/canvasRect.width),
      sy=Math.floor((y-canvasRect.top)*sprite.height/canvasRect.height);
     if(sx<0||sy<0||sx>=sprite.width||sy>=sprite.height)continue;
     const alpha=pixels[(sy*sprite.width+sx)*4+3];
     if(!document.elementFromPoint(x,y)?.closest('.world-location')?.isSameNode(button))continue;
     const point={x,y,source:[sx,sy],alpha};
     if(alpha===0){sourceClear++;if(!clear)clear=point}
     if(alpha===255){sourceOpaque++;if(!opaque)opaque=point}
    }
    rows.push({id:button.dataset.region,source:sprite.dataset.nativeHitMask,
     ready:sprite.dataset.ready,clear,opaque,sourceClear,sourceOpaque});
   }
   return rows;
  });
  assert.equal(source.length,6);
  assert.deepEqual(source.map(x=>x.id),
   ['street','knights','north','south','dice','my4leaf']);
  assert.ok(source.every(r=>r.ready==='true'&&r.source.startsWith('WorldMap/')));
  const candidates=source.filter(x=>x.clear&&x.opaque);
  assert.ok(candidates.length>=1,'at least one native hotspot has an honestly transparent image pixel: '+JSON.stringify(source));
  const first=candidates[0];
  await page.mouse.click(first.clear.x,first.clear.y);
  const rejected=await page.evaluate(id=>{
   const button=document.querySelector('.world-location[data-region="'+id+'"]');
   return {sky:!document.getElementById('sky').classList.contains('hidden'),
    profile:!!document.querySelector('#world-profile-modal'),
    result:button.dataset.nativeSourceHit,alpha:button.dataset.nativeSourceAlpha,
    last:button.dataset.nativeSourcePoint};
  },first.id);
  assert.equal(rejected.result,'false',
   'physical mouse on original source transparent pixel must be rejected: '+JSON.stringify({first,rejected}));
  assert.equal(rejected.sky,true,'transparent pointer cannot leave the live WorldMap');
  assert.equal(rejected.profile,false,'transparent pixel cannot open My4LEAF modal');

  // Opaque source pixel on the SAME original PNG must open the real route,
  // not just toggle a test flag.
  await page.mouse.click(first.opaque.x,first.opaque.y);
  const accepted=await page.evaluate(id=>{
   const button=document.querySelector('.world-location[data-region="'+id+'"]');
   return {sky:!document.getElementById('sky').classList.contains('hidden'),
    profile:!!document.querySelector('#world-profile-modal'),
    result:button.dataset.nativeSourceHit,alpha:button.dataset.nativeSourceAlpha};
  },first.id);
  assert.equal(accepted.result,'true',
   'original opaque source pixel remains a working click target: '+JSON.stringify({first,accepted}));
  if(first.id==='my4leaf')assert.equal(accepted.profile,true);
  else assert.equal(accepted.sky,false,'opaque original pixel activates real scene');

  // Keyboard route access must remain independent of a mouse pixel mask.
  await page.locator('[data-route="sky"]').first().click();
  await page.waitForSelector('#sky:not(.hidden)');
  await page.locator('.world-location[data-region="my4leaf"]').focus();
  await page.keyboard.press('Enter');
  assert.ok(await page.locator('#world-profile-modal').isVisible(),
   'keyboard Enter opens the source profile even with pointer mask');
  await page.locator('#world-profile-modal .world-profile-heading button').click();
  assert.deepEqual(errors,[]);
  console.log('WORLD SOURCE ALPHA PHYSICAL CLICK PASS '+JSON.stringify({
   engine:browserType.name(),tested:first.id,clear:first.clear,opaque:first.opaque,
   source:source.map(({id,sourceClear,sourceOpaque})=>({id,sourceClear,sourceOpaque}))}));
 }finally{await browser.close();}
})().catch(e=>{console.error('WORLD SOURCE ALPHA CLICK FAILED',e.stack||e);process.exit(1);});
