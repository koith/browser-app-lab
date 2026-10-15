'use strict';
// True archived Room/roombutton.png (493×302), independent READY/SELECT/REMAKE
// four-state sprite controls registered by chroma-keyed pixel correlation
// with Room/roomback.png (794×404). No large invented HTML buttons.
(function(){
 const stage=document.getElementById('dice-native-stage');if(!stage)return;
 const definitions=[
  {id:'lobby-config-back',name:'remake',x:200,y:306,w:123,h:42,atlasY:0},
  {id:'dice-team-picker',name:'select',x:560,y:232,w:68,h:28,atlasY:111},
  {id:'start-game',name:'ready',x:524,y:361,w:105,h:33,atlasY:78}
 ];
 const controls=[];
 let source=null;
 function paint(control){
  const {button,canvas,w,h,atlasY}=control;
  const disabled=button.disabled||button.getAttribute('aria-disabled')==='true';
  const active=button.getAttribute('aria-expanded')==='true';
  const frame=disabled?3:(control.pressed||active)?2:(control.hover||control.focus)?1:0;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);
  if(source&&frame)ctx.drawImage(source,w*frame,atlasY,w,h,0,0,w,h);
  canvas.dataset.frame=String(frame);
 }
 for(const def of definitions){
  const button=document.getElementById(def.id);if(!button)continue;
  const canvas=document.createElement('canvas');canvas.className='dice-original-room-button-art';
  canvas.dataset.source='Room/roombutton.png';canvas.setAttribute('aria-hidden','true');
  canvas.width=def.w;canvas.height=def.h;
  button.append(canvas);
  button.dataset.nativeX=String(def.x);button.dataset.nativeY=String(def.y);
  const control={...def,button,canvas,hover:false,focus:false,pressed:false};
  controls.push(control);
  button.addEventListener('pointerenter',()=>{control.hover=true;paint(control)});
  button.addEventListener('pointerleave',()=>{control.hover=false;control.pressed=false;paint(control)});
  button.addEventListener('pointerdown',()=>{control.pressed=true;paint(control)});
  button.addEventListener('pointerup',()=>{control.pressed=false;paint(control)});
  button.addEventListener('pointercancel',()=>{control.pressed=false;paint(control)});
  button.addEventListener('focus',()=>{control.focus=true;paint(control)});
  button.addEventListener('blur',()=>{control.focus=false;control.pressed=false;paint(control)});
  new MutationObserver(()=>paint(control)).observe(button,{
   attributes:true,attributeFilter:['aria-expanded','aria-disabled','disabled']});
  paint(control);
 }
 stage.dataset.roomButtonReady='loading';
 const image=new Image();let retries=0;
 const load=()=>{
  if(!stage.isConnected)return;
  image.src='./original/Room/roombutton.png'+(retries?'?retry='+retries+'&at='+Date.now():'');
 };
 image.onload=()=>{
  try{
   if(image.naturalWidth!==493||image.naturalHeight!==302)throw Error('invalid source room button atlas');
   const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
   const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
   for(let i=0;i<pixels.data.length;i+=4){
    const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
    if(r<=60&&g>=225&&b<=70)pixels.data[i+3]=0;
   }
   ctx.putImageData(pixels,0,0);
   source=canvas;stage.dataset.roomButtonReady='true';
   controls.forEach(paint);
  }catch(error){stage.dataset.roomButtonReady='fallback';console.warn('Original READY buttons:',error.message)}
 };
 image.onerror=()=>{
  if(!stage.isConnected)return;
  if(retries>=4){stage.dataset.roomButtonReady='fallback';return}
  retries++;setTimeout(load,Math.min(1600,200*2**retries));
 };
 load();
 window.__LEAF_DICE_ROOM_BUTTONS__={getState:()=>({
  loaded:stage.dataset.roomButtonReady,
  buttons:controls.map(c=>({id:c.id,name:c.name,x:c.x,y:c.y,w:c.w,h:c.h,
   frame:Number(c.canvas.dataset.frame)}))
 })};
})();
