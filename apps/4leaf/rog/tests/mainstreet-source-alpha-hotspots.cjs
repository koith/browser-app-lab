'use strict';
/* Real MainStreet.pak source 1938x404: exact green-key pixel-hit original
 * sprite interactivity, not oversized transparent-rectangle CSS hotspots.
 * This browser acceptance compares 7 decoded native canvases, a real
 * physical pointer on transparent pavement versus original shop art.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_STREET__&&window.__ROG_TEST__);
  await page.evaluate(()=>window.__ROG_TEST__.go('city'));
  await page.waitForFunction(()=>[...document.querySelectorAll('.street-building-art')].length===7&&
   [...document.querySelectorAll('.street-building-art')].every(x=>x.dataset.ready==='true'),null,{timeout:16000});
  const audit=await page.evaluate(()=>{
   const buttons=[...document.querySelectorAll('.street-location')];
   const rows=buttons.map(button=>{
    const canvas=button.querySelector('canvas');
    const p=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
    let opaque=0,transparent=0,point=null,clear=null,fallback=null;
    const cx=canvas.width/2,cy=canvas.height/2;
    let score=Infinity,backupScore=Infinity,clearScore=Infinity;
    for(let y=4;y<canvas.height-4;y++)for(let x=4;x<canvas.width-4;x++){
     const alpha=p[(y*canvas.width+x)*4+3],dist=Math.hypot(x-cx,y-cy);
     if(alpha===255){
      opaque++;
      if(dist<backupScore){backupScore=dist;fallback={x,y};}
      // Browser MouseEvent.clientX/clientY are integer CSS pixels.
      // A 1px opaque edge can become transparent after rasterized pointer
      // rounding even though the exact SOURCE pixel is white. Select
      // actual deep SOURCE interior, not an anti-aliased 1px silhouette.
      let solid=true;
      for(let dy=-3;dy<=3&&solid;dy++)for(let dx=-3;dx<=3;dx++)
       if(p[((y+dy)*canvas.width+x+dx)*4+3]!==255){solid=false;break;}
      if(solid&&dist<score){score=dist;point={x,y};}
     }
     if(alpha===0){
      transparent++;
      const edge=x+y;
      if(edge<clearScore){clearScore=edge;clear={x,y};}
     }
    }
    if(!point)point=fallback;
    return {id:button.dataset.street,source:canvas.dataset.hitMaskSource,
     nativeSize:[canvas.width,canvas.height],opaque,transparent,point,clear,
     ready:canvas.dataset.ready};
   });
   return {sourceScene:[document.querySelector('#street-track').offsetWidth,
    document.querySelector('#street-track').offsetHeight],rows};
  });
  assert.deepEqual(audit.sourceScene,[1938,404]);
  assert.equal(audit.rows.length,7);
  assert.ok(audit.rows.every(a=>a.opaque>300&&a.transparent>100&&a.clear&&a.point),
   'all seven actual source green-key sprites must have visible AND transparent pixels');
  assert.ok(audit.rows.every(a=>a.source==='MainStreet/'+
   ({fashions:'dress',sweet:'event',magic:'card',court:'hair',
     gallery:'accessory',dandy:'dandymodern',office:'office'}[a.id])+'.png'));
  const magic=audit.rows.find(a=>a.id==='magic');
  assert.ok(magic);
  const send=async point=>page.evaluate(({point})=>{
   const button=document.querySelector('[data-street="magic"]');
   const canvas=button.querySelector('canvas');
   const rect=canvas.getBoundingClientRect();
   button.dispatchEvent(new MouseEvent('click',{bubbles:true,
    detail:1,clientX:rect.left+(point.x+.5)*rect.width/canvas.width,
    clientY:rect.top+(point.y+.5)*rect.height/canvas.height}));
   return {cityVisible:!document.querySelector('#city').classList.contains('hidden'),
    shopVisible:!document.querySelector('#shop').classList.contains('hidden'),
    hit:button.dataset.lastSourceHit,
    sourcePixel:button.dataset.lastSourcePixel,
    active:document.querySelector('#where')?.textContent,
    classes:document.querySelector('#shop').className};
  },{point});
  let result=await send(magic.clear);
  assert.equal(result.cityVisible,true,'clicking a transparent pixel is original open street, not a shop');
  assert.equal(result.shopVisible,false,'transparent source pixels never open a fake shop rectangle');
  result=await send(magic.point);
  assert.equal(result.hit,'true','opaque native source location click must pass actual PNG mask: '+JSON.stringify({result,magic}));
  assert.equal(result.shopVisible,true,'hitting opaque original Magic Carden bitmap opens the actual card shop: '+JSON.stringify({result,magic}));
  await page.evaluate(()=>window.__ROG_TEST__.go('city'));
  await page.waitForFunction(()=>!document.querySelector('#city').classList.contains('hidden'));
  // Use PHYSICAL pointer for open pavement panning, not DOM event simulation.
  // Ensure the real source building remains in the viewport at normal zoom.
  const pointer=await page.evaluate(point=>{
   const btn=document.querySelector('[data-street="magic"]');
   const canvas=btn.querySelector('canvas');
   const rect=canvas.getBoundingClientRect();
   return {x:rect.left+(point.x+.5)*rect.width/canvas.width,
    y:rect.top+(point.y+.5)*rect.height/canvas.height,
    before:window.__LEAF_STREET__.getState().x,
    viewport:document.querySelector('#street-viewport').getBoundingClientRect().toJSON()};
  },magic.clear);
  assert.ok(pointer.x>=pointer.viewport.x&&pointer.x<pointer.viewport.x+pointer.viewport.width&&
   pointer.y>=pointer.viewport.y&&pointer.y<pointer.viewport.y+pointer.viewport.height,
   'source transparent corner must lie inside the genuinely visible scene');
  await page.mouse.move(pointer.x,pointer.y);
  await page.mouse.down();
  await page.mouse.move(pointer.x+80,pointer.y,{steps:4});
  await page.mouse.up();
  const after=await page.evaluate(()=>window.__LEAF_STREET__.getState().x);
  assert.ok(Math.abs(after-pointer.before)>30,
   'dragging a transparent green-key source building corner must pan 1938px panorama: '+
   JSON.stringify({pointer,after}));
  assert.ok(await page.locator('#city:not(.hidden)').isVisible());
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'leaf-mainstreet-original-seven-transparent-hotspots.png'});
  console.log('NATIVE MAINSTREET EXACT GREEN-KEY HIT PASS '+JSON.stringify({
   images:audit.rows.map(a=>({id:a.id,source:a.source,
    opaque:a.opaque,transparent:a.transparent,size:a.nativeSize})),
   streetPan:[pointer.before,after]}));
 }finally{await browser.close()}
})().catch(e=>{console.error('NATIVE MAINSTREET SOURCE ALPHA QA FAILED',e.stack||e);process.exit(1)});
