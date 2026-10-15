'use strict';
// Render the actual Map/mapbutton.png and Map/maplist.png sprite states on
// independent input surfaces. The original 794x404 mapback is still the
// backing scene; canvases are only hover/pressed/disabled art, never a
// pre-rendered screenshot or inert click-overlay substitute.
(function(){
 const $=id=>document.getElementById(id);
 const stage=$('dice-native-stage');
 if(!stage)return;
 const definitions=[
  {id:'lobby-create',x:28,y:317,w:220,h:72,atlasY:63},
  {id:'lobby-join',x:334,y:312,w:183,h:72,atlasY:136}
 ];
 const controls=[];
 const retryImage=(path,onload,onfailure)=>{
  const image=new Image();let retries=0;
  const request=()=>{
   if(!stage.isConnected)return;
   image.src=path+(retries?'?retry='+retries+'&at='+Date.now():'');
  };
  image.onload=()=>onload(image);
  image.onerror=()=>{
   if(retries>=4){onfailure?.();return}
   retries++;setTimeout(request,Math.min(1600,200*2**retries));
  };
  request();
 };
 function chromaCanvas(image){
  const canvas=document.createElement('canvas');
  canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(image,0,0);
  const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
  for(let i=0;i<pixels.data.length;i+=4){
   const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
   if(r<=60&&g>=225&&b<=70)pixels.data[i+3]=0;
  }
  ctx.putImageData(pixels,0,0);
  return canvas;
 }
 let sprite=null;
 function render(control){
  const disabled=control.button.getAttribute('aria-disabled')==='true';
  const state=disabled?3:control.pressed?2:(control.hover||control.focus)?1:0;
  const ctx=control.canvas.getContext('2d');
  ctx.clearRect(0,0,control.w,control.h);
  if(sprite&&state>0){
   ctx.drawImage(sprite,control.w*state,control.atlasY,control.w,control.h,
    0,0,control.w,control.h);
  }
  control.canvas.dataset.frame=String(state);
 }
 function installControl(definition){
  const button=$(definition.id);if(!button)return;
  const canvas=document.createElement('canvas');
  canvas.width=definition.w;canvas.height=definition.h;
  canvas.className='dice-original-map-button-art';
  canvas.setAttribute('aria-hidden','true');canvas.dataset.source='Map/mapbutton.png';
  button.append(canvas);
  button.dataset.source='Map/mapbutton.png';
  button.dataset.nativeX=String(definition.x);button.dataset.nativeY=String(definition.y);
  const state={...definition,button,canvas,pressed:false,hover:false,focus:false};
  controls.push(state);
  button.addEventListener('pointerenter',()=>{state.hover=true;render(state)});
  button.addEventListener('pointerleave',()=>{state.hover=false;state.pressed=false;render(state)});
  button.addEventListener('pointerdown',()=>{state.pressed=true;render(state)});
  button.addEventListener('pointerup',()=>{state.pressed=false;render(state)});
  button.addEventListener('pointercancel',()=>{state.pressed=false;render(state)});
  button.addEventListener('focus',()=>{state.focus=true;render(state)});
  button.addEventListener('blur',()=>{state.focus=false;state.pressed=false;render(state)});
  new MutationObserver(()=>render(state)).observe(button,{attributes:true,attributeFilter:['aria-disabled']});
  render(state);
 }
 definitions.forEach(installControl);
 stage.dataset.mapButtonReady='loading';
 retryImage('./original/Map/mapbutton.png',image=>{
  try{
   if(image.naturalWidth!==880||image.naturalHeight!==210)throw Error('invalid original Map button atlas');
   sprite=chromaCanvas(image);
   stage.dataset.mapButtonReady='true';
   controls.forEach(render);
  }catch(e){stage.dataset.mapButtonReady='fallback';console.warn('Original Map buttons:',e.message)}
 },()=>{stage.dataset.mapButtonReady='fallback'});
 // The original ROOM SELECT also has 402px-wide list row frames. Preserve the
 // same-origin original atlas. Default uses its dark native row, highlight
 // uses its bright row; all overlay text stays DOM, not part of the sprite.
 stage.dataset.mapListReady='loading';
 retryImage('./original/Map/maplist.png',image=>{
  try{
   if(image.naturalWidth!==402||image.naturalHeight!==77)throw Error('invalid original Map list atlas');
   const original=chromaCanvas(image);
   const frame=(sourceY)=>{
    const c=document.createElement('canvas');c.width=402;c.height=23;
    c.getContext('2d').drawImage(original,0,sourceY,402,23,0,0,402,23);
    return 'url("'+c.toDataURL('image/png')+'")';
   };
   stage.style.setProperty('--native-map-row',frame(23));
   stage.style.setProperty('--native-map-row-active',frame(0));
   stage.dataset.mapListReady='true';
  }catch(e){stage.dataset.mapListReady='fallback';console.warn('Original Map room list:',e.message)}
 },()=>{stage.dataset.mapListReady='fallback'});
 window.__LEAF_DICE_MAP_BUTTONS__={
  getState:()=>({loaded:stage.dataset.mapButtonReady,list:stage.dataset.mapListReady,
   buttons:controls.map(c=>({id:c.id,x:c.x,y:c.y,w:c.w,h:c.h,
    frame:Number(c.canvas.dataset.frame)}))})
 };
})();