'use strict';
// The true 4LEAF lower-center watermark in both archived WorldMap and ChatRoom
// screenshots is recovered as MainFrame/snaplogo.png (161x51, green-key).
// Quantify its target screenshot anchor before adding it as a live separate
// sprite; NEVER draw the historical screenshot itself onto the game scene.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  const fixture=p=>fs.readFileSync(path.resolve(__dirname,p)).toString('base64');
  const inputs={
   logo:'data:image/png;base64,'+fixture('../original/MainFrame/snaplogo.png'),
   sky:'data:image/jpeg;base64,'+fixture('../../assets/sky.jpg'),
   chat:'data:image/jpeg;base64,'+fixture('../../assets/chat.jpg'),
   chatRef:'data:image/jpeg;base64,'+fixture('../../assets/chat_ref.jpg')
  };
  const results=await page.evaluate(async input=>{
   const load=async src=>{
    const i=new Image();i.src=src;await i.decode();
    const c=document.createElement('canvas');c.width=i.naturalWidth;c.height=i.naturalHeight;
    const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(i,0,0);
    return {w:c.width,h:c.height,d:ctx.getImageData(0,0,c.width,c.height).data};
   };
   const logo=await load(input.logo);
   const tests={sky:await load(input.sky),chat:await load(input.chat),chatRef:await load(input.chatRef)};
   const samples=[];
   for(let y=0;y<logo.h;y+=2)for(let x=0;x<logo.w;x+=2){
    const i=(y*logo.w+x)*4,r=logo.d[i],g=logo.d[i+1],b=logo.d[i+2],a=logo.d[i+3];
    if(a<30||(g>=180&&r<115&&b<125&&g>r*1.4))continue;
    samples.push([x,y,r,g,b]);
   }
   const search=(photo,scale,x0,x1,y0,y1,step)=>{
    let best={score:Infinity,x:null,y:null,scale};
    for(let y=y0;y<=y1;y+=step)for(let x=x0;x<=x1;x+=step){
     let sum=0;
     for(const [ix,iy,r,g,b] of samples){
      const px=x+Math.round(ix*scale),py=y+Math.round(iy*scale);
      if(px<0||px>=photo.w||py<0||py>=photo.h){sum+=180;continue}
      const k=(py*photo.w+px)*4;
      sum+=Math.min(180,Math.abs(photo.d[k]-r)+Math.abs(photo.d[k+1]-g)+Math.abs(photo.d[k+2]-b));
     }
     const score=sum/samples.length;
     if(score<best.score)best={score,x,y,scale};
    }
    return best;
   };
   const matches={};
   for(const [key,photo] of Object.entries(tests)){
    const candidates=[.94,1,1.06,1.12].map(scale=>search(photo,scale,280,355,442,478,2));
    const winner=candidates.reduce((a,b)=>a.score<b.score?a:b);
    const exact=search(photo,winner.scale,winner.x-4,winner.x+4,winner.y-4,winner.y+4,1);
    matches[key]={candidates,exact};
   }
   return {source:[logo.w,logo.h],samples:samples.length,matches};
  },inputs);
  assert.deepEqual(results.source,[161,51]);
  assert.ok(results.samples>200);
  console.log('MAINFRAME ORIGINAL SNAPLOGO SCREENSHOT REGISTRATION',JSON.stringify(results));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF SOURCE BRAND REGISTRATION FAILED',e.stack||e);process.exit(1)});
