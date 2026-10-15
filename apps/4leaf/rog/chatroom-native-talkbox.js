'use strict';
// ChatRoom/talkbox.png: 47x100 actual original source asset. Source x0..24,
// y0..23 is a 9-slice WHITE talk balloon, separated by red chroma-key lines;
// x25..36,y0..14 is its separate pointing tail. These are sprite COMPONENTS,
// not a static screenshot. Render any message length using the original pixels.
(function(){
 const ATLAS='./original/ChatRoom/talkbox.png';
 const image=new Image();image.decoding='async';
 const waiting=new Set();
 let ready=false,tries=0,source=null;
 function load(){
  image.src=ATLAS+(tries?'?retry='+tries+'&at='+Date.now():'');
 }
 image.onload=()=>{
  if(image.naturalWidth!==47||image.naturalHeight!==100){
   console.warn('4LEAF native speech source has unexpected dimensions');
   return;
  }
  const sheet=document.createElement('canvas');sheet.width=47;sheet.height=100;
  const ctx=sheet.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(image,0,0);
  const pixels=ctx.getImageData(0,0,47,100);
  for(let i=0;i<pixels.data.length;i+=4){
   const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
   if(r>=245&&g<=20&&b<=20)pixels.data[i+3]=0;
  }
  ctx.putImageData(pixels,0,0);
  source=sheet;ready=true;
  for(const bubble of waiting){if(bubble.isConnected)render(bubble)}
  waiting.clear();
 };
 image.onerror=()=>{
  if(tries>=5){console.warn('4LEAF original talkbox unavailable after retries');return}
  tries++;
  setTimeout(load,Math.min(2000,200*2**tries));
 };
 function render(bubble){
  if(!ready||!bubble.isConnected)return;
  const canvas=bubble.querySelector('.native-talkbox-canvas');
  if(!canvas)return;
  const width=Math.max(40,Math.ceil(bubble.offsetWidth));
  const height=Math.max(27,Math.ceil(bubble.offsetHeight));
  const tailHeight=14;
  // Canvas dimensions are source-space CSS pixels, before the game's scale
  // transform. Drawing context scales only for HiDPI; pixels stay pixel-art.
  const ratio=Math.min(3,Math.max(1,window.devicePixelRatio||1));
  canvas.width=Math.ceil(width*ratio);
  canvas.height=Math.ceil((height+tailHeight)*ratio);
  canvas.style.width=width+'px';canvas.style.height=(height+tailHeight)+'px';
  const ctx=canvas.getContext('2d',{alpha:true});
  ctx.setTransform(ratio,0,0,ratio,0,0);
  ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,width,height+tailHeight);
  const draw=(sx,sy,sw,sh,x,y,w,h)=>ctx.drawImage(source,sx,sy,sw,sh,x,y,w,h);
  // Source corner widths 9 and 10. Horizontal/vertical mid spans are 4
  // pixel patterns stretched independently for any message dimensions.
  const left=9,right=10,top=9,bottom=9;
  const midX=Math.max(1,width-left-right);
  const midY=Math.max(1,height-top-bottom);
  draw(0,0,9,9,0,0,left,top);
  draw(10,0,4,9,left,0,midX,top);
  draw(15,0,10,9,width-right,0,right,top);
  draw(0,10,9,4,0,top,left,midY);
  draw(10,10,4,4,left,top,midX,midY);
  draw(15,10,10,4,width-right,top,right,midY);
  draw(0,15,9,9,0,height-bottom,left,bottom);
  draw(10,15,4,9,left,height-bottom,midX,bottom);
  draw(15,15,10,9,width-right,height-bottom,right,bottom);
  // Original tail (12x15) is green/red keyed independently of 9-slice body.
  // Overlap 1 px at bottom to avoid a line at their join.
  draw(25,0,12,15,Math.round((width-12)/2),height-1,12,15);
  bubble.dataset.nativeTalkboxReady='true';
  bubble.dataset.nativeSource='ChatRoom/talkbox.png';
  bubble.dataset.nativeWidth=String(width);
  bubble.dataset.nativeHeight=String(height);
 }
 function apply(bubble){
  if(!bubble||bubble.classList.contains('native-talkbox-applied'))return;
  bubble.classList.add('native-talkbox-applied');
  const text=document.createElement('span');
  text.className='native-talkbox-text';text.textContent=bubble.textContent||'';
  const canvas=document.createElement('canvas');
  canvas.className='native-talkbox-canvas';
  canvas.setAttribute('aria-hidden','true');
  canvas.dataset.source='ChatRoom/talkbox.png';
  bubble.replaceChildren(canvas,text);
  // Browser text wrapping, locale font fallback and viewport scale can all
  // change bubble dimensions. Keep genuine border/corners pixel registered.
  if('ResizeObserver' in window){
   const observer=new ResizeObserver(()=>{
    if(!bubble.isConnected){observer.disconnect();waiting.delete(bubble);return}
    if(ready)render(bubble);
   });
   observer.observe(bubble);
  }
  if(ready)render(bubble);else waiting.add(bubble);
 }
 window.__LEAF_NATIVE_TALKBOX__={apply,getState:()=>({
  ready,width:source?.width||0,height:source?.height||0,waiting:waiting.size
 })};
 load();
})();
