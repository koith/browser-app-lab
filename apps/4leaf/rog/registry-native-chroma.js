'use strict';
/* Source-preserving bright-green transparency of 2002 Registry/savaNN.
 * Original PNG pixels/bytes and src stay unchanged. Instead, a computed
 * alpha mask strips ONLY saturated green connected to the exterior.
 * No picture redraw or invented character sprites. Masks cache by source.
 * file:// has canvas origin restrictions: leave raw archive playable.
 */
(function(){
 const cache=new Map();
 const isSava=src=>/^\.\/original\/Registry\/sava\d{2}\.png$/.test(src);
 function maskRGBA(data,width,height){
  const mark=new Uint8Array(width*height),queue=new Int32Array(width*height);
  let first=0,last=0;
  const green=i=>{
   const p=i*4,r=data[p],g=data[p+1],b=data[p+2],a=data[p+3];
   return a>24&&g>=155&&g>=r*1.75&&g>=b*1.75&&r<105&&b<105;
  };
  const visit=i=>{
   if(i<0||i>=mark.length||mark[i]||!green(i))return;
   mark[i]=1;queue[last++]=i;
  };
  for(let x=0;x<width;x++){visit(x);visit((height-1)*width+x)}
  for(let y=1;y<height-1;y++){visit(y*width);visit(y*width+width-1)}
  while(first<last){
   const i=queue[first++],x=i%width,y=(i-x)/width;
   if(x>0)visit(i-1);if(x+1<width)visit(i+1);
   if(y>0)visit(i-width);if(y+1<height)visit(i+width);
  }
  // Alter ONLY the temporary mask bitmap alpha. The original sprite
  // texture, palette, RGB pixels and source identity remain unmodified.
  for(let i=0;i<mark.length;i++)data[i*4+3]=mark[i]?0:255;
  return last;
 }
 function derive(src){
  if(cache.has(src))return cache.get(src);
  const job=new Promise(resolve=>{
   if(location.protocol==='file:'){resolve(null);return}
   const img=new Image();
   img.onload=()=>{
    try{
     if(!img.naturalWidth||!img.naturalHeight||img.naturalWidth>300||img.naturalHeight>300)
      throw Error('Unexpected original Registry image dimensions');
     const canvas=document.createElement('canvas');
     canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
     const ctx=canvas.getContext('2d',{willReadFrequently:true});
     ctx.drawImage(img,0,0);
     const bitmap=ctx.getImageData(0,0,canvas.width,canvas.height);
     const removed=maskRGBA(bitmap.data,canvas.width,canvas.height);
     if(!removed){resolve(null);return}
     ctx.putImageData(bitmap,0,0);
     resolve({url:canvas.toDataURL('image/png'),removed});
    }catch{resolve(null)}
   };
   img.onerror=()=>resolve(null);
   img.src=src;
  });
  cache.set(src,job);return job;
 }
 function apply(element,source){
  if(!element||!isSava(source))return;
  element.dataset.nativeRegistrySource=source;
  element.dataset.registryChroma='loading';
  derive(source).then(mask=>{
   if(!element.isConnected||element.dataset.nativeRegistrySource!==source)return;
   if(!mask){element.dataset.registryChroma='source-fallback';return}
   // Keep <img src="./original/Registry/savaNN.png"> for provenance.
   // Only an externally derived CSS alpha mask removes green pixels.
   const url='url("'+mask.url+'")';
   element.style.setProperty('mask-image',url,'important');
   element.style.setProperty('-webkit-mask-image',url,'important');
   element.style.setProperty('mask-size','100% 100%','important');
   element.style.setProperty('-webkit-mask-size','100% 100%','important');
   element.dataset.registryChroma='ready';
   element.dataset.registryChromaRemoved=String(mask.removed);
  });
 }
 window.__LEAF_REGISTRY_CHROMA__={
  apply,
  getState:()=>({sources:[...cache.keys()],kind:'native-PNG-preserved/exterior-green-alpha-mask'})
 };
})();
