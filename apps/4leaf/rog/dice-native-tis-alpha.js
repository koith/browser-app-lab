/* Actual original Genesis TIS 145x97 RGBA sprites ALREADY carry native
 * alpha in their corner pixels. The apparently red/pink/green corner tint
 * visible in some image viewers is not proof of an opaque game bitmap.
 * Preserve the archived RGBA unchanged when it is already keyed.
 * For an actually opaque border only, flood-fill the exterior color
 * without erasing valid center artwork. Derive source-specific pointer
 * silhouette from genuine alpha data in either case.
 * Source pixels are verified; lost EXE hit-test logic remains inferred.
 */
(function(){
 'use strict';
 const cache=new Map(),SIZE=[145,97];
 const rgbAt=(p,i)=>[p[i],p[i+1],p[i+2]];
 const alike=(a,b,range=22)=>
  Math.abs(a[0]-b[0])<=range&&Math.abs(a[1]-b[1])<=range&&
  Math.abs(a[2]-b[2])<=range;
 function silhouette(p,w,h){
  // The previous 4-row contour sampled the MIDPOINT of a strip (y+2).
  // That cut off the top two pixels, the final bottom pixel, and some
  // anti-aliased protrusions of real 145x97 TIS platform silhouettes.
  // A clip-path is only a conservative clickable boundary: the original
  // image's native per-pixel alpha still supplies the ACTUAL artwork.
  // Cover every row boundary and every nonzero-alpha source pixel.
  const bands=[],stride=3;
  for(let y=0;y<h;y+=stride){
   let min=w,max=-1;
   const bottom=Math.min(h,y+stride);
   for(let dy=y;dy<bottom;dy++){
    for(let x=0;x<w;x++){
     if(p[(dy*w+x)*4+3]===0)continue;
     if(x<min)min=x;if(x>max)max=x;
    }
   }
   if(max>=min)bands.push({
    top:y,bottom,left:Math.max(0,min-1),right:Math.min(w,max+2)
   });
  }
  if(bands.length<4)return null;
  const point=(x,y)=>(100*x/w).toFixed(3)+'% '+(100*y/h).toFixed(3)+'%';
  const left=bands.flatMap(b=>[point(b.left,b.top),point(b.left,b.bottom)]);
  const right=[...bands].reverse().flatMap(b=>[
   point(b.right,b.bottom),point(b.right,b.top)
  ]);
  return 'polygon('+left.concat(right).join(',')+')';
 }
 function decode(img,id){
  if(img.naturalWidth!==SIZE[0]||img.naturalHeight!==SIZE[1])
   throw new Error('Unexpected original TIS atlas '+id+' '+img.naturalWidth+'x'+img.naturalHeight);
  const canvas=document.createElement('canvas');canvas.width=SIZE[0];canvas.height=SIZE[1];
  const context=canvas.getContext('2d',{willReadFrequently:true});
  context.drawImage(img,0,0);
  // Running under file:// may taint a canvas. Fallback to still-playable
  // source art+geometric clip, never break the offline unbundled app.
  const frame=context.getImageData(0,0,SIZE[0],SIZE[1]),pixels=frame.data;
  const w=SIZE[0],h=SIZE[1],count=w*h;
  const corners=[0,w-1,w*(h-1),count-1];
  const seeds=corners.filter(i=>pixels[i*4+3]>200).map(i=>rgbAt(pixels,i*4));
  const mark=new Uint8Array(count),queue=new Int32Array(count);
  let tail=0,head=0;
  const enqueue=i=>{
   if(mark[i]||pixels[i*4+3]<25)return;
   const color=rgbAt(pixels,i*4);
   if(!seeds.some(seed=>alike(color,seed)))return;
   mark[i]=1;queue[tail++]=i;
  };
  // Seed from EVERY actual edge segment, but only colors like the original
  // four corner mattes. This also handles disconnected exterior wedges.
  for(let x=0;x<w;x++){enqueue(x);enqueue((h-1)*w+x);}
  for(let y=1;y<h-1;y++){enqueue(y*w);enqueue(y*w+w-1);}
  while(head<tail){
   const i=queue[head++],x=i%w,y=(i-x)/w;
   if(x>0)enqueue(i-1);
   if(x<w-1)enqueue(i+1);
   if(y>0)enqueue(i-w);
   if(y<h-1)enqueue(i+w);
  }
  // Even the thick original source mattes can have antialiasing around a
  // red/pink border. Do NOT flood arbitrary pink artwork: only exterior
  // pixels connected to a known corner with a close-enough original color
  // were visited. Do not alter any surviving art's source RGB values.
  for(let i=0;i<count;i++)if(mark[i])pixels[i*4+3]=0;
  // Do not re-encode already-transparent source PNGs into huge data URLs.
  // This avoids needless GPU uploads and preserves byte-identical original
  // files when there was never a chroma matte to remove.
  if(tail)context.putImageData(frame,0,0);
  const clip=silhouette(pixels,w,h);
  return {
   id,url:tail?canvas.toDataURL('image/png'):'./original/Tiles/'+id+'.png',
   clip,removed:tail,alreadyTransparent:tail===0,
   pixels:count,cornerColors:seeds,native:SIZE.slice(),
   source:'Tiles/'+id+'.png'
  };
 }
 function prepare(id){
  id=String(id).padStart(4,'0');
  if(!/^\d{4}$/.test(id))return Promise.reject(new Error('Bad original TIS id'));
  if(cache.has(id))return cache.get(id);
  const work=new Promise((resolve,reject)=>{
   let retries=0;
   const image=new Image();
   image.onload=()=>{
    try{resolve(decode(image,id))}
    catch(error){reject(error)}
   };
   image.onerror=()=>{
    if(retries>=4){reject(new Error('Original TIS '+id+' unavailable'));return}
    retries++;
    setTimeout(()=>{
     image.src='./original/Tiles/'+id+'.png?retry='+retries+'&at='+Date.now();
    },Math.min(1600,120*2**retries));
   };
   image.src='./original/Tiles/'+id+'.png';
  });
  cache.set(id,work);
  return work;
 }
 function apply(tile,id){
  if(!tile)return;
  id=String(id).padStart(4,'0');
  tile.dataset.tisAlpha='loading';
  prepare(id).then(paint=>{
   if(!tile.isConnected||tile.dataset.originalArt!==id)return;
   // The same already-transparent original PNG remains the original URL.
   // Only sources with an actual opaque external matte get a keyed data PNG.
   tile.style.setProperty('background-image','url("'+paint.url+'")','important');
   if(paint.clip){
    tile.style.setProperty('clip-path',paint.clip,'important');
    tile.style.setProperty('-webkit-clip-path',paint.clip,'important');
   }
   tile.dataset.tisAlpha='ready';
   tile.dataset.tisAlphaSource=paint.source;
   tile.dataset.tisChromaRemoved=String(paint.removed);
   tile.dataset.tisSourcePreserved=String(paint.alreadyTransparent);
  }).catch(()=>{
   // Keep the old source bitmap/hexagon hitbox playable if client security
   // refuses canvas pixel reads or if a historic asset host sleeps.
   if(tile.isConnected&&tile.dataset.originalArt===id)tile.dataset.tisAlpha='fallback';
  });
 }
 window.__LEAF_TIS_ALPHA__={
  apply,prepare,
  getState:()=>({native:SIZE.slice(),cached:[...cache.keys()],kind:'exterior-matte-flood-fill'})
 };
})();