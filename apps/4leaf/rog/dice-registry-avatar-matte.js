'use strict';
/* Original 2002 Registry SAVA image: historical PLAYER rail avatar, not a
 * Genesis OBS chessman or CardData card. Leave source img URLs unchanged,
 * apply only original bright-green chroma alpha via an image MASK.
 */
(function(){
 const cache=new Map(),seen=new WeakSet();
 const selector='#battle-player-panels .battle-side-portrait img';
 const srcOf=img=>img.getAttribute('src')||'';
 const isNative=src=>/^\.\/original\/Registry\/sava\d\d\.png$/.test(src);
 function sourceMask(img){
  if(img.naturalWidth!==75||img.naturalHeight!==141)
   throw Error('Unexpected genuine SAVA dimensions');
  const canvas=document.createElement('canvas');
  canvas.width=75;canvas.height=141;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  if(!ctx)throw Error('Canvas unavailable');
  ctx.drawImage(img,0,0);
  const pixels=ctx.getImageData(0,0,75,141);
  let removed=0;
  for(let i=0;i<pixels.data.length;i+=4){
   const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
   const chroma=g>=220&&r<90&&b<95&&g>r*1.8&&g>b*1.8;
   pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=255;
   pixels.data[i+3]=chroma?0:255;
   if(chroma)removed++;
  }
  if(removed<1000)throw Error('Source image has no bright-green matte');
  ctx.putImageData(pixels,0,0);
  return {url:canvas.toDataURL('image/png'),removed};
 }
 function apply(img){
  if(!img.isConnected)return;
  const src=srcOf(img);
  if(!isNative(src)){img.dataset.registryChroma='different-source';return}
  if(location.protocol==='file:'){
   // file:// taints the original local PNG canvas on Chromium.
   img.dataset.registryChroma='source-file-fallback';return;
  }
  try{
   let item=cache.get(src);
   if(!item){item=sourceMask(img);cache.set(src,item)}
   img.style.maskImage='url("'+item.url+'")';
   img.style.webkitMaskImage='url("'+item.url+'")';
   img.style.maskSize='100% 100%';
   img.style.webkitMaskSize='100% 100%';
   img.dataset.registryChroma='ready';
   img.dataset.registryChromaRemoved=String(item.removed);
   img.dataset.registrySourceRole='player-hud-avatar';
  }catch(error){
   img.dataset.registryChroma='fallback';
   console.warn('Original SAVA matte fallback',src,String(error?.message||error));
  }
 }
 function update(){
  for(const img of document.querySelectorAll(selector)){
   if(seen.has(img))continue;
   seen.add(img);
   if(img.complete&&img.naturalWidth===75){apply(img);continue}
   img.addEventListener('load',()=>apply(img),{once:true});
   img.addEventListener('error',()=>{img.dataset.registryChroma='load-error'},{once:true});
  }
 }
 function init(){
  const root=document.getElementById('battle-player-panels');
  if(!root)return;
  update();
  new MutationObserver(update).observe(root,{childList:true,subtree:true});
 }
 if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',init,{once:true});
 else init();
 window.__LEAF_REGISTRY_CHROMA__={getState:()=>({
  cachedSources:cache.size,
  rails:[...document.querySelectorAll(selector)].map(img=>({
   src:srcOf(img),state:img.dataset.registryChroma||'pending',
   removed:Number(img.dataset.registryChromaRemoved)||0
  }))
 })};
})();
