'use strict';
// Source-vs-contemporary screenshot registration of ChatRoom/room4t.png.
// Screenshot apps/4leaf/assets/chat_ref.jpg shows the real wooden room4.
// Historical pixels, not a pasted screenshot, determine foreground geometry.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  const measured=await page.evaluate(async()=>{
   const load=async url=>{
    const img=new Image();img.src=url;await img.decode();
    const canvas=document.createElement('canvas');
    canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(img,0,0);
    return {w:canvas.width,h:canvas.height,data:ctx.getImageData(0,0,canvas.width,canvas.height).data};
   };
   const reference=await load('../assets/chat_ref.jpg');
   const art=await load('./original/ChatRoom/room4t.png');
   const pixels=[];
   for(let y=1;y<art.h-1;y+=3)for(let x=1;x<art.w-1;x+=3){
    const i=(y*art.w+x)*4,r=art.data[i],g=art.data[i+1],b=art.data[i+2],a=art.data[i+3];
    if(a<50||(r>=238&&g<25&&b<25))continue;
    pixels.push([x,y,r,g,b]);
   }
   // Robust clipped RGB L1 prevents real people sitting in front of the table
   // from unfairly overpowering the background/table alignment signal.
   const search=(scale)=>{
    let best={score:Infinity,x:-1,y:-1,scale};
    for(let y=330;y<=455;y+=2)for(let x=295;x<=525;x+=2){
     let total=0;
     for(const p of pixels){
      const px=x+Math.round(p[0]*scale),py=y+Math.round(p[1]*scale);
      if(px<0||px>=reference.w||py<0||py>=reference.h){total+=180;continue}
      const k=(py*reference.w+px)*4;
      const difference=Math.abs(reference.data[k]-p[2])+Math.abs(reference.data[k+1]-p[3])+Math.abs(reference.data[k+2]-p[4]);
      total+=Math.min(180,difference);
     }
     const score=total/pixels.length;
     if(score<best.score)best={score,x,y,scale};
    }
    return best;
   };
   const scans=[1,1.12,1.24,1.36].map(search);
   return {reference:[reference.w,reference.h],native:[art.w,art.h],sampleCount:pixels.length,
    scans,best:scans.reduce((a,b)=>a.score<b.score?a:b)};
  });
  assert.deepEqual(measured.reference,[794,528],'historical room reference is native 794x528');
  assert.deepEqual(measured.native,[115,103],'actual source room4 table bitmap has native 115x103 pixels');
  assert.ok(measured.sampleCount>100,'original table is not just a red matte');
  console.log('ROOM4 ARCHIVE SCREENSHOT FURNITURE REGISTRATION',JSON.stringify(measured));
 }finally{await browser.close()}
})().catch(e=>{console.error('ROOM4 REGISTRATION FAILED',e.stack||e);process.exit(1)});
