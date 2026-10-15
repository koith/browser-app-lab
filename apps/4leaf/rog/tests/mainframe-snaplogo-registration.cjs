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
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
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
  for(const [name,result] of Object.entries(results.matches)){
   assert.deepEqual([result.exact.x,result.exact.y,result.exact.scale],[316,472,1],
    'real screenshot '+name+' must register exact recovered snaplogo pixel anchor');
  }
  await page.waitForFunction(()=>document.querySelector('#leaf-world-stage > .leaf-native-snaplogo')?.dataset.ready==='true'
   &&document.querySelector('#leaf-world-stage > .leaf-native-snapnumber')?.dataset.ready==='true',null,{timeout:12000});
  const geometry=await page.locator('#leaf-world-stage > .leaf-native-snaplogo').evaluate(c=>{
   const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
   let visible=0,transparent=0,green=0;
   for(let i=0;i<data.length;i+=4){
    if(data[i+3]===0)transparent++;else{
     visible++;
     if(data[i+1]>180&&data[i]<100&&data[i+2]<100)green++;
    }
   }
   const s=getComputedStyle(c);
   return {width:c.width,height:c.height,left:parseFloat(s.left),top:parseFloat(s.top),
    source:c.dataset.source,visible,transparent,green};
  });
  assert.deepEqual([geometry.left,geometry.top,geometry.width,geometry.height],[316,472,161,51]);
  assert.equal(geometry.source,'MainFrame/snaplogo.png');
  assert.ok(geometry.visible>1000&&geometry.transparent>100,
   'retain native logo strokes but remove original chroma-key green background');
  assert.equal(geometry.green,0,'do not display bright-green atlas matte');
  const digits=await page.locator('#leaf-world-stage > .leaf-native-snapnumber').evaluate(el=>({
   size:[el.width,el.height],time:el.dataset.liveTime,ready:el.dataset.ready
  }));
  assert.deepEqual(digits.size,[90,10],'timestamp is composed from native 6x10 glyphs');
  assert.match(digits.time,/^\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}$/);
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원본 스냅 로고 겹침 검증',4);
  });
  await page.waitForFunction(()=>document.querySelector('#rooms .social-interior > .leaf-native-snaplogo')?.dataset.ready==='true',null,{timeout:12000});
  const inRoom=await page.locator('#rooms .social-interior > .leaf-native-snaplogo').evaluate(el=>{
   const s=getComputedStyle(el);
   return [parseFloat(s.left),parseFloat(s.top),el.width,el.height];
  });
  assert.deepEqual(inRoom,[316,472,161,51],'chat uses identical archived MainFrame watermark pixel registration');
  console.log('ORIGINAL MAINFRAME SOURCE SNAPLOGO LIVE PASS',JSON.stringify({geometry,digits,inRoom}));

  console.log('MAINFRAME ORIGINAL SNAPLOGO SCREENSHOT REGISTRATION',JSON.stringify(results));
 }finally{await browser.close()}
})().catch(e=>{console.error('4LEAF SOURCE BRAND REGISTRATION FAILED',e.stack||e);process.exit(1)});
