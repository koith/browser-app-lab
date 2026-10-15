'use strict';
// Native ChatRoom.pak foreground registration. The archived 3t and 5t source
// PNG sizes are VERIFIED; x/y placements are inferred from recovered backdrops,
// NOT presented as original screen-pixel registration (unlike room4).
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  const samples=[
   {background:3,file:'room3t',native:[272,102],placed:[261,363],depth:80},
   {background:5,file:'room5t',native:[176,128],placed:[307,357],depth:78}
  ];
  for(const spec of samples){
   await page.evaluate(background=>{
    window.__LEAF_SOCIAL__.openRegion('north');
    window.__ROG_TEST__.go('rooms');
    window.__LEAF_SOCIAL__.createRoom('원본 분리 탁자 검증 '+background,background,12);
   },spec.background);
   await page.waitForFunction(file=>{
    const canvas=document.querySelector('.social-room-foreground');
    return canvas?.dataset.source===file&&canvas.dataset.ready==='true';
   },spec.file,{timeout:18000});
   const measured=await page.locator('.social-room-foreground').evaluate(canvas=>{
    const paint=canvas.getContext('2d',{willReadFrequently:true})
       .getImageData(0,0,canvas.width,canvas.height).data;
    let opaque=0,clear=0,keyLeak=0;
    for(let i=0;i<paint.length;i+=4){
     if(paint[i+3]<10)clear++;else opaque++;
     if(paint[i]>=242&&paint[i+1]<=18&&paint[i+2]<=18&&paint[i+3]>0)keyLeak++;
    }
    const frame=document.querySelector('#social-image-frame');
    const backdrop=getComputedStyle(frame).backgroundImage;
    return {
     source:canvas.dataset.source,
     native:[canvas.width,canvas.height],
     css:[Number.parseFloat(canvas.style.width),Number.parseFloat(canvas.style.height)],
     placed:[Number.parseFloat(canvas.style.left),Number.parseFloat(canvas.style.top)],
     depth:Number.parseInt(canvas.style.zIndex,10),
     opaque,clear,keyLeak,backdrop,
     userCount:document.querySelectorAll('.social-avatar').length
    };
   });
   assert.equal(measured.source,spec.file,'recovered native foreground is used');
   assert.deepEqual(measured.native,spec.native,'source archive pixel dimensions');
   assert.deepEqual(measured.css,spec.native,
    'native 1:1 bitmap: do not stretch 272x102 or 176x128 into guessed giant props');
   assert.deepEqual(measured.placed,spec.placed,
    'reconstructed central foreground anchor remains fixed relative to recovered art');
   assert.equal(measured.depth,spec.depth,
    'independent original furniture layer retains seat occlusion depth');
   assert.ok(measured.opaque>300&&measured.clear>300,
    'visible source artwork and transparent red mask both survive composition');
   assert.equal(measured.keyLeak,0,'source red chroma-key must be removed');
   assert.ok(measured.backdrop.includes('/original/ChatRoom/room'+spec.background+'.png'),
    'scene uses original room-specific 794x528 background');
   assert.equal(measured.userCount,1,'no fabricated chat users');
   await page.screenshot({path:'leaf-native-room'+spec.background+'-furniture.png'});
   // Clicking an empty source-floor location teleports, not linear animation.
   const before=await page.locator('.social-avatar.self').evaluate(el=>el.dataset.seat);
   await page.locator('#social-image-frame').click({position:{x:150,y:485},force:true});
   const after=await page.locator('.social-avatar.self').evaluate(el=>({
    seat:el.dataset.seat,transition:getComputedStyle(el).transitionDuration
   }));
   assert.ok(Number.isInteger(Number(after.seat)),'native source room has a snapped seat');
   assert.ok(after.transition.split(',').every(x=>Number.parseFloat(x)===0),
    'seat changes are instantaneous, not linear walking animations');
   console.log('NATIVE FURNITURE',JSON.stringify({file:spec.file,before,after,measured}));
  }
  assert.deepEqual(errors,[],'no unhandled page errors in either native ChatRoom');
  console.log('ROOM3/5 NATIVE FOREGROUND PASS: correct source pixels, 1:1 scale, real occupancy and teleport');
 }finally{await browser.close()}
})().catch(e=>{console.error('ROOM3/5 FOREGROUND FAILED',e.stack||e);process.exit(1)});
