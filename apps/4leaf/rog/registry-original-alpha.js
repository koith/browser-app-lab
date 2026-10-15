/* Original Registry/sava00..sava86 graphics use vivid green chroma key.
 * Recover the transparency from actual source pixels. Keep the original IMG
 * src (never a static screenshot or another artist's substitute) and apply
 * a cached pixel-perfect alpha mask to all live original avatar instances.
 *
 * Same-origin canvas readback is supported by GitHub Pages / localhost. The
 * offline file:// archive may forbid reading images via its security model:
 * preserve the playable original source in that environment without throwing.
 */
(function(){
 'use strict';
 const RE=/\/original\/Registry\/sava(?:0[0-6]|8[0-6])\.png(?:\?.*)?$/i;
 const SOURCE_ATTR='data-leaf-sava-mask';
 const cache=new Map();
 const tracked=new WeakSet();
 const masksAvailable=typeof HTMLCanvasElement!=='undefined';
 function isSprite(img){return img instanceof HTMLImageElement&&RE.test(new URL(img.src,location.href).pathname)}
 async function fromSource(src){
  const image=new Image();
  await new Promise((resolve,reject)=>{
   image.onload=resolve;image.onerror=reject;
   image.src=src;
   if(image.complete&&image.naturalWidth)resolve();
  });
  const canvas=document.createElement('canvas');
  canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  if(!ctx)throw new Error('No 2d canvas context');
  ctx.drawImage(image,0,0);
  const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
  const data=pixels.data;let cut=0;
  for(let i=0;i<data.length;i+=4){
   const r=data[i],g=data[i+1],b=data[i+2];
   // Source PNG uses pure #00ff00; allow a little keyed antialias fringe,
   // but do not remove real midtone greens from original costumes.
   if(g>=225&&r<=50&&b<=50&&g>r*2.5&&g>b*2.5){
    data[i+3]=0;cut++;
   }else{
    data[i+3]=data[i+3]; // Preserve any alpha already in the source asset.
   }
  }
  if(!cut)throw new Error('No chroma pixels in Registry source');
  ctx.putImageData(pixels,0,0);
  return {url:canvas.toDataURL('image/png'),keyed:cut,width:canvas.width,height:canvas.height};
 }
 function promiseFor(src){
  if(!cache.has(src))cache.set(src,fromSource(src).catch(error=>{
   cache.delete(src);
   if(location.protocol!=='file:')console.warn('4LEAF source Registry alpha:',error.message);
   return null;
  }));
  return cache.get(src);
 }
 async function apply(img){
  if(!img.isConnected||!isSprite(img))return;
  const src=img.src;
  img.dataset.leafSavaMask='loading';
  const mask=await promiseFor(src);
  if(!img.isConnected||img.src!==src)return;
  if(!mask){img.dataset.leafSavaMask='unsupported';return}
  const value='url("'+mask.url+'")';
  img.style.maskImage=value;
  img.style.webkitMaskImage=value;
  img.style.maskSize='100% 100%';
  img.style.webkitMaskSize='100% 100%';
  img.dataset.leafSavaMask='true';
  img.dataset.leafOriginalSprite=src.split('/').pop().split('?')[0];
 }
 function track(node){
  if(node.nodeType!==1)return;
  const all=node.matches?.('img')?[node]:[];
  if(node.querySelectorAll)all.push(...node.querySelectorAll('img'));
  for(const img of all){
   if(!isSprite(img)||tracked.has(img))continue;
   tracked.add(img);
   img.addEventListener('load',()=>apply(img));
   if(img.complete&&img.naturalWidth)apply(img);
  }
 }
 function boot(){
  if(!masksAvailable)return;
  track(document.documentElement);
  new MutationObserver(records=>{
   for(const record of records){
    if(record.type==='attributes'){
     const img=record.target;
     if(!isSprite(img))continue;
     img.style.maskImage='';img.style.webkitMaskImage='';
     if(img.complete&&img.naturalWidth)apply(img);
    }else for(const node of record.addedNodes)track(node);
   }
  }).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['src']});
 }
 window.__LEAF_REGISTRY_ALPHA__={
  apply,refresh:()=>track(document.documentElement),
  getState:()=>({cached:cache.size,masked:document.querySelectorAll('img['+SOURCE_ATTR+'="true"]').length,
   source:'original/Registry/sava*.png',sourceKey:'#00ff00'})
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
 else boot();
})();
