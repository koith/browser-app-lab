/* Actual 2002 Genesis TIS/Pak 145×97 sprites arrive with opaque pink/red
 * chroma mattes (for example 0000.png pink, 0015.png red). Browsers do NOT
 * key those colors automatically as the old client did. Without decoding,
 * every overlapping source platform is an opaque painted rectangle.
 *
 * Decode each UNIQUE recovered PNG once, flood-fill only the contiguous
 * outer matte (never blindly remove all red pixels inside the source symbol),
 * preserve every interior colored pixel, and derive a polygonal POINTER
 * silhouette from the alpha boundary. The native TIS and DMP source are
 * genuine. The exact original client chroma tolerance is still unverified.
 */
(function(){
 'use strict';
 const cache=new Map(),SIZE=[145,97];
 const rgbAt=(p,i)=>[p[i],p[i+1],p[i+2]];
 const alike=(a,b,range=22)=>
  Math.abs(a[0]-b[0])<=range&&Math.abs(a[1]-b[1])<=range&&
  Math.abs(a[2]-b[2])<=range;
 function silhouette(p,w,h){
  const rows=[];
  for(let y=0;y<h;y+=4){
   let min=w,max=-1;
   for(let dy=y;dy<Math.min(h,y+4);dy++){
    for(let x=0;x<w;x++){
     if(p[(dy*w+x)*4+3]<80)continue;
     if(x<min)min=x;if(x>max)max=x;
    }
   }
   if(max>=min)rows.push({y:Math.min(h-1,y+2),left:Math.max(0,min-1),right:Math.min(w-1,max+1)});
  }
  if(rows.length<4)return null;
  const point=(x,y)=>(100*x/w).toFixed(2)+'% '+(100*y/h).toFixed(2)+'%';
  return 'polygon('+rows.map(r=>point(r.left,r.y))
   .concat([...rows].reverse().map(r=>point(r.right,r.y))).join(',')+')';
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
  context.putImageData(frame,0,0);
  const clip=silhouette(pixels,w,h);
  return {
   id,url:canvas.toDataURL('image/png'),clip,removed:tail,
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
   // Override original shorthand with the same genuine bitmap re-encoded
   // only to remove the extracted client chroma key.
   tile.style.setProperty('background-image','url("'+paint.url+'")','important');
   if(paint.clip){
    tile.style.setProperty('clip-path',paint.clip,'important');
    tile.style.setProperty('-webkit-clip-path',paint.clip,'important');
   }
   tile.dataset.tisAlpha='ready';
   tile.dataset.tisAlphaSource=paint.source;
   tile.dataset.tisChromaRemoved=String(paint.removed);
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