'use strict';
// Source-vs-contemporary screenshot registration of ChatRoom/room4t.png.
// Screenshot apps/4leaf/assets/chat_ref.jpg shows the real wooden room4.
// Historical pixels, not a pasted screenshot, determine foreground geometry.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
  // Test the actual local/peer room renderer without joining public Render.
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  // The standalone ROG test server intentionally exposes only rog/, not
  // neighboring apps/4leaf/assets/. Give Chromium the authentic JPEG bytes.
  const encoded=(name)=>fs.readFileSync(path.resolve(__dirname,name)).toString('base64');
  const refSrc='data:image/jpeg;base64,'+encoded('../../assets/chat_ref.jpg');
  const altSrc='data:image/jpeg;base64,'+encoded('../../assets/chat.jpg');
  const artSrc='data:image/png;base64,'+encoded('../original/ChatRoom/room4t.png');
  const measured=await page.evaluate(async({refSrc,altSrc,artSrc})=>{
   const load=async url=>{
    const img=new Image();img.src=url;await img.decode();
    const canvas=document.createElement('canvas');
    canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(img,0,0);
    return {w:canvas.width,h:canvas.height,data:ctx.getImageData(0,0,canvas.width,canvas.height).data};
   };
   const reference=await load(refSrc);
   const second=await load(altSrc);
   const art=await load(artSrc);
   const pixels=[];
   for(let y=1;y<art.h-1;y+=3)for(let x=1;x<art.w-1;x+=3){
    const i=(y*art.w+x)*4,r=art.data[i],g=art.data[i+1],b=art.data[i+2],a=art.data[i+3];
    if(a<50||(r>=238&&g<25&&b<25))continue;
    pixels.push([x,y,r,g,b]);
   }
   // Robust clipped RGB L1 prevents real people sitting in front of the table
   // from unfairly overpowering the background/table alignment signal.
   const search=(scale,photo=reference,x0=295,x1=525,y0=330,y1=455,step=2)=>{
    let best={score:Infinity,x:-1,y:-1,scale};
    for(let y=y0;y<=y1;y+=step)for(let x=x0;x<=x1;x+=step){
     let total=0;
     for(const p of pixels){
      const px=x+Math.round(p[0]*scale),py=y+Math.round(p[1]*scale);
      if(px<0||px>=photo.w||py<0||py>=photo.h){total+=180;continue}
      const k=(py*photo.w+px)*4;
      const difference=Math.abs(photo.data[k]-p[2])+Math.abs(photo.data[k+1]-p[3])+Math.abs(photo.data[k+2]-p[4]);
      total+=Math.min(180,difference);
     }
     const score=total/pixels.length;
     if(score<best.score)best={score,x,y,scale};
    }
    return best;
   };
   const scans=[1,1.12,1.24,1.36].map(scale=>search(scale));
   const best=scans.reduce((a,b)=>a.score<b.score?a:b);
   const precise=search(1,reference,best.x-4,best.x+4,best.y-4,best.y+4,1);
   const altCoarse=search(1,second);
   const altPrecise=search(1,second,altCoarse.x-4,altCoarse.x+4,altCoarse.y-4,altCoarse.y+4,1);
   return {reference:[reference.w,reference.h],second:[second.w,second.h],
    native:[art.w,art.h],sampleCount:pixels.length,
    scans,best,precise,altPrecise};
  },{refSrc,altSrc,artSrc});
  assert.deepEqual(measured.reference,[794,528],'historical room reference is native 794x528');
  assert.deepEqual(measured.native,[115,103],'actual source room4 table bitmap has native 115x103 pixels');
  assert.ok(measured.sampleCount>100,'original table is not just a red matte');
  assert.deepEqual(measured.second,[794,528],'second archived player capture uses the same room geometry');
  assert.equal(measured.best.scale,1,'a native one-to-one sprite beats previously stretched furniture');
  assert.ok(Math.abs(measured.precise.x-427)<=3&&Math.abs(measured.precise.y-424)<=3,
   'source table must register at historical screenshot geometry, not old 318x345');
  assert.ok(Math.abs(measured.altPrecise.x-measured.precise.x)<=3&&
   Math.abs(measured.altPrecise.y-measured.precise.y)<=3,
   'two distinct historical chat captures must agree on furniture placement');
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원본 탁자 좌표 회귀',4);
  });
  await page.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',
   null,{timeout:12000});
  const actual=await page.locator('.social-room-foreground').evaluate(canvas=>({
   left:parseFloat(canvas.style.left),top:parseFloat(canvas.style.top),
   width:parseFloat(canvas.style.width),height:parseFloat(canvas.style.height),
   source:canvas.dataset.source,
   bitmap:[canvas.width,canvas.height],depth:parseInt(canvas.style.zIndex,10)
  }));
  assert.deepEqual([actual.left,actual.top,actual.width,actual.height],[427,425,115,103],
   'real alpha-composited foreground must use screenshot-registered native coordinate and size');
  assert.equal(actual.source,'room4t');
  assert.deepEqual(actual.bitmap,[115,103],'source foreground canvas is not pixel-stretched');
  assert.equal(actual.depth,80,'tables obscure rear actors but stay behind foreground seats');
  const avatarLabel=await page.locator('.social-avatar.self').evaluate(el=>{
   const frame=document.querySelector('#social-image-frame').getBoundingClientRect();
   const zoom=frame.width/794;
   const label=el.querySelector('.social-avatar-name');
   const box=label.getBoundingClientRect();
   const baseline=Number.parseFloat(el.style.top)*5.28;
   return {baseline,nameTop:(box.top-frame.top)/zoom,
    height:box.height/zoom,color:getComputedStyle(label).backgroundColor,
    size:getComputedStyle(label).fontSize};
  });
  console.log('ROOM4 AVATAR LABEL RAW GEOMETRY',JSON.stringify(avatarLabel));
  assert.ok(avatarLabel.baseline-avatarLabel.nameTop>=160&&
    avatarLabel.baseline-avatarLabel.nameTop<=185,
   'historical nickname label sits above character head: '+JSON.stringify(avatarLabel));
  assert.equal(avatarLabel.color,'rgb(86, 107, 198)',
   'screenshot-based blue nameplate, no invented gold self-highlight');
  const archive=fs.readdirSync(path.resolve(__dirname,'../original/ChatRoom'));
  console.log('CHATROOM EXTRACTED ORIGINAL FILES',JSON.stringify(archive));
  console.log('ROOM4 AVATAR LABEL ALIGNMENT',JSON.stringify(avatarLabel));
  console.log('ROOM4 ARCHIVE SCREENSHOT FURNITURE REGISTRATION',JSON.stringify({...measured,rendered:actual}));
 }finally{await browser.close()}
})().catch(e=>{console.error('ROOM4 REGISTRATION FAILED',e.stack||e);process.exit(1)});
