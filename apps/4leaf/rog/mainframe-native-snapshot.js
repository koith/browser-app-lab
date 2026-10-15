'use strict';
/* The original archived 4LEAF MainFrame.pak contains snaplogo.png (161x51)
   and snapnumber.png (72x10). The independent 161x51 watermark appears
   at precisely (316,472) in sky.jpg, chat.jpg and chat_ref.jpg at scale 1.
   Use live PNG sprites with native green-key alpha, NEVER screen captures.
   The historical screenshot's 2003/2004 clock text is not replayed:
   a real current timestamp is assembled from the extracted digit atlas. */
(function(){
 const LOGO='./original/MainFrame/snaplogo.png';
 const DIGITS='./original/MainFrame/snapnumber.png';
 const nativeWidth=161,nativeHeight=51;
 let sheetLogo=null,sheetDigits=null,ticker=null;
 const imageSheet=(url,width,height)=>{
  let retries=0;
  return new Promise((resolve,reject)=>{
   const img=new Image();
   const request=()=>{
    img.src=url+(retries?'?retry='+retries+'&at='+Date.now():'');
   };
   img.onload=()=>{
    try{
     if(img.naturalWidth!==width||img.naturalHeight!==height)
      throw Error('Original MainFrame atlas geometry differs from archive');
     const canvas=document.createElement('canvas');
     canvas.width=width;canvas.height=height;
     const ctx=canvas.getContext('2d',{willReadFrequently:true});
     ctx.drawImage(img,0,0);
     const pixels=ctx.getImageData(0,0,width,height);
     for(let p=0;p<pixels.data.length;p+=4){
      const r=pixels.data[p],g=pixels.data[p+1],b=pixels.data[p+2];
      // Original saturated-green chroma key, preserving blue clover and white
      // outline pixels around the actual 4LEAF source bitmap.
      if(g>=150&&r<145&&b<155&&g>r*1.35&&g>b*1.35)
       pixels.data[p+3]=0;
     }
     ctx.putImageData(pixels,0,0);
     resolve(canvas);
    }catch(error){reject(error)}
   };
   img.onerror=()=>{
    if(retries<5){
     retries++;
     setTimeout(request,Math.min(1800,220*2**retries));
    }else reject(Error('Original MainFrame art unavailable: '+url));
   };
   request();
  });
 };
 function getLogo(){
  if(!sheetLogo)sheetLogo=imageSheet(LOGO,161,51).catch(error=>{
   sheetLogo=null;throw error;
  });
  return sheetLogo;
 }
 function getDigits(){
  if(!sheetDigits)sheetDigits=imageSheet(DIGITS,72,10).catch(error=>{
   sheetDigits=null;throw error;
  });
  return sheetDigits;
 }
 function timestamp(){
  const date=new Date(),pad=n=>String(n).padStart(2,'0');
  return pad(date.getFullYear()%100)+'.'+pad(date.getMonth()+1)+'.'+
   pad(date.getDate())+' '+pad(date.getHours())+':'+pad(date.getMinutes());
 }
 const glyphIndex=char=>{
  if(char>='0'&&char<='9')return char.charCodeAt(0)-48;
  if(char==='.')return 10;
  if(char===':')return 11;
  return -1;
 };
 function paintDigits(canvas,atlas){
  if(!canvas?.isConnected)return;
  const ctx=canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);
  let left=0;
  for(const char of timestamp()){
   const i=glyphIndex(char);
   if(i>=0){ctx.drawImage(atlas,i*6,0,6,10,left,0,6,10);left+=6}
   else left+=4;
  }
  canvas.dataset.ready='true';
  canvas.dataset.liveTime=timestamp();
 }
 function refresh(){
  if(!sheetDigits)return;
  sheetDigits.then(atlas=>{
   for(const canvas of document.querySelectorAll('.leaf-native-snapnumber'))
    paintDigits(canvas,atlas);
  }).catch(()=>{});
 }
 function mount(scene){
  if(!scene||scene.querySelector(':scope > .leaf-native-snaplogo'))return;
  const logo=document.createElement('canvas');
  logo.className='leaf-native-snaplogo';
  logo.width=nativeWidth;logo.height=nativeHeight;
  logo.setAttribute('aria-label','원본 포리프 스냅 로고');
  logo.dataset.ready='loading';
  const clock=document.createElement('canvas');
  clock.className='leaf-native-snapnumber';
  clock.width=90;clock.height=10;
  clock.setAttribute('aria-hidden','true');
  clock.dataset.ready='loading';
  scene.append(logo,clock);
  getLogo().then(atlas=>{
   if(!logo.isConnected)return;
   logo.getContext('2d').drawImage(atlas,0,0);
   logo.dataset.ready='true';
   logo.dataset.source='MainFrame/snaplogo.png';
  }).catch(error=>{
   logo.dataset.ready='error';
   console.warn('4LEAF recovered snap logo:',error.message);
  });
  getDigits().then(atlas=>paintDigits(clock,atlas)).catch(error=>{
   clock.dataset.ready='error';
   console.warn('4LEAF recovered snap-number atlas:',error.message);
  });
  if(!ticker)ticker=setInterval(refresh,30000);
 }
 window.__LEAF_NATIVE_SNAPSHOT__={
  mount,refresh,
  getState:()=>({
   logos:document.querySelectorAll('.leaf-native-snaplogo').length,
   times:document.querySelectorAll('.leaf-native-snapnumber').length
  })
 };
})();
