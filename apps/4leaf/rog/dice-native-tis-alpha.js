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
 const cache=new Map(),decoded=new Map(),SIZE=[145,97];
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
   // Copy the genuine decoded source alpha AFTER exterior chroma removal.
   // A CSS polygon only approximates the original contour; empty pixels
   // INSIDE it must not trigger a different source tile's click action.
   alpha:Uint8Array.from({length:count},(_,i)=>pixels[i*4+3]),
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
    try{const frame=decode(image,id);decoded.set(id,frame);resolve(frame)}
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
 // Exact original bitmap pick test in the browser's actual transformed
 // camera coordinates. Source TIS PNG is 145x97 and intentionally inverted
 // by the existing scaleY(-1) orientation repair. Rect measures the *live*
 // DOM tile (including camera zoom), so do not confuse DMP 70x47 logical
 // pitch with real source pixels or introduce a guessed CSS hexagon here.
 function hitPoint(tile,clientX,clientY){
  const id=tile?.dataset?.originalArt;
  const frame=decoded.get(id);
  if(!tile||!frame)return {ready:false,hit:true,source:id||null};
  const rect=tile.getBoundingClientRect();
  if(!(rect.width>0&&rect.height>0)||!Number.isFinite(clientX)||!Number.isFinite(clientY))
   return {ready:false,hit:true,source:id};
  const transform=getComputedStyle(tile).transform;
  // Safari/Chromium may serialize an actual 3D transform as matrix3d().
  // Inspect its vertical basis instead of assuming only matrix(1,0,0,-1).
  // Parent camera scale remains accounted for by the live screen rectangle.
  const inverted=typeof DOMMatrixReadOnly==='function'?
   new DOMMatrixReadOnly(transform).m22<0:
   (transform.startsWith('matrix(')&&Number(transform.slice(7).split(',')[3])<0);
  const x=Math.floor((clientX-rect.left)*SIZE[0]/rect.width);
  const rawY=(clientY-rect.top)*SIZE[1]/rect.height;
  // The prior floor(97-rawY) returned row 97 at the topmost screen
  // edge (outside the 0..96 source bitmap). Pixel 96 must own that edge;
  // the bottom source edge must likewise map to row 0.
  const y=inverted?Math.ceil(SIZE[1]-rawY)-1:Math.floor(rawY);
  const inside=x>=0&&x<SIZE[0]&&y>=0&&y<SIZE[1];
  const alpha=inside?frame.alpha[y*SIZE[0]+x]:0;
  return {ready:true,hit:alpha>0,alpha,x,y,inverted,source:id};
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
  apply,prepare,hitPoint,
  getState:()=>({native:SIZE.slice(),cached:[...cache.keys()],decoded:[...decoded.keys()],
   kind:'exterior-matte-flood-fill/native-alpha-hit',orientation:'source-PNG/scaleY(-1)'})
 };
})();