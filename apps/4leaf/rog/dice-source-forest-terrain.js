/* 4LEAF Dice battlefield landscape reconstruction, October 2026.
 *
 * Grounded geometry: the 2003 DMP map vertex coordinates reconstructed in
 * ORIGINAL_LEAF_MAPS and converted into the SAME 1450x1120 PATH/world-camera
 * coordinate system used for actual interactive TIS platforms/Registry pawns.
 *
 * Visual reference: archived original board.jpg + battle.jpg. Those show
 * forest canopy, grassy cliff shelves, boulders and uneven dirt below the
 * native isometric TIS cards. The original heightfield/3D model data has NOT
 * been recovered. This is an explicitly inferred 2.5D Canvas landscape, not
 * a false historical original model or screenshot pasted under hitboxes.
 *
 * One opaque terrain layer is cached by map and route. Native tile DOM,
 * pointer events, move rules, WebRTC and follow-camera remain unchanged.
 */
(function(){
 'use strict';
 const WIDTH=1450,HEIGHT=1120;
 const $=id=>document.getElementById(id);
 let cacheKey='',lastState=null;
 function hashString(text){
  let h=2166136261;
  for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,16777619)}
  return h>>>0;
 }
 function generator(seed){
  let x=seed||1;
  return ()=>{
   x^=x<<13;x^=x>>>17;x^=x<<5;
   return (x>>>0)/4294967296;
  };
 }
 function pick(list,r){return list[Math.floor(r()*list.length)]}
 function blob(ctx,x,y,rx,ry,color,r,rot=0,vertices=11){
  ctx.save();ctx.translate(x,y);ctx.rotate(rot);
  ctx.beginPath();
  for(let i=0;i<vertices;i++){
   const t=i*Math.PI*2/vertices;
   const wobble=.79+r()*.38;
   const xx=Math.cos(t)*rx*wobble,yy=Math.sin(t)*ry*wobble;
   if(!i)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy);
  }
  ctx.closePath();ctx.fillStyle=color;ctx.fill();ctx.restore();
 }
 function ellipse(ctx,x,y,rx,ry,fill){
  ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);
  ctx.fillStyle=fill;ctx.fill();
 }
 function stone(ctx,x,y,scale,r){
  const w=scale*(20+r()*18),h=w*(.28+r()*.20);
  blob(ctx,x+3,y+7,w*1.2,h*.8,'#182d2077',r,-.12,8);
  blob(ctx,x,y-3,w,h,'#665f4a',r,-.2,7);
  blob(ctx,x-3,y-10,w*.84,h*.95,'#9c8b6c',r,-.2,6);
  blob(ctx,x-7,y-13,w*.48,h*.35,'#b4a180',r,-.1,5);
  blob(ctx,x+w*.28,y-8,w*.2,h*.5,'#444b3b',r,.1,5);
 }
 function tree(ctx,x,y,size,r){
  // Explicit canopy depth and ground shadows; native pawns stay in front.
  ellipse(ctx,x+size*.17,y+size*.29,size*.88,size*.30,'#162c1d99');
  ctx.fillStyle='#433a29';
  ctx.fillRect(x-size*.045,y-size*.26,size*.1,size*.44);
  const leaves=['#203e2b','#315637','#38683c','#467644','#567e43'];
  const balls=[
   [-.42,-.25,.53],[-.03,-.53,.68],[.45,-.2,.50],
   [-.52,.12,.42],[.08,.05,.64],[.38,.20,.44]
  ];
  for(let i=0;i<balls.length;i++){
   const [dx,dy,f]=balls[i];
   ellipse(ctx,x+dx*size,y+dy*size,size*f*.72,size*f*.47,pick(leaves,r));
  }
  for(let i=0;i<4;i++){
   let xx=x+(r()-.5)*size*.85,yy=y+(r()-.7)*size*.7;
   ellipse(ctx,xx,yy,size*(.08+r()*.09),size*.05,'#8e9a5788');
  }
 }
 function meadow(ctx,r,path){
  const ground=ctx.createLinearGradient(0,0,WIDTH*.55,HEIGHT);
  ground.addColorStop(0,'#344e32');
  ground.addColorStop(.22,'#526b3d');
  ground.addColorStop(.55,'#66794b');
  ground.addColorStop(.82,'#4e6840');
  ground.addColorStop(1,'#2b4935');
  ctx.fillStyle=ground;ctx.fillRect(0,0,WIDTH,HEIGHT);
  // Large soft horizontal height/vegetation bands, NOT screen artifacts.
  for(let i=0;i<92;i++){
   const x=r()*WIDTH,y=r()*HEIGHT,rx=45+r()*205,ry=24+r()*108;
   blob(ctx,x,y,rx,ry,pick(['#8e99653c','#283e2947','#9a88593b','#718e5542','#324f2f55'],r),r,r()*2,13);
  }
  // Dust/moss grains avoid an unconvincing smooth computer gradient.
  for(let i=0;i<18000;i++){
   const x=r()*WIDTH,y=r()*HEIGHT,v=1+r()*2.1;
   ctx.fillStyle=pick(['#c1bb7a22','#172e1e2a','#aebd7239','#597b3e55'],r);
   ctx.fillRect(x,y,v,v*.45);
  }
  // A physically shared soil corridor underneath original recovered DMP
  // tile platforms. The route itself is never replaced by a static picture.
  if(path.length>1){
   ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
   ctx.beginPath();for(let i=0;i<path.length;i++){const p=path[i];if(i===0)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y)}
   ctx.strokeStyle='#443c2b45';ctx.lineWidth=87;ctx.stroke();
   ctx.strokeStyle='#97795c48';ctx.lineWidth=55;ctx.stroke();
   ctx.strokeStyle='#af99694d';ctx.lineWidth=23;ctx.stroke();
   ctx.restore();
   for(let i=0;i<path.length;i++){
    const p=path[i];
    ellipse(ctx,p.x,p.y+21,42,15,'#132b2770');
    ellipse(ctx,p.x,p.y+4,47,13,'#9e91613a');
   }
  }
 }
 function distanceToRoute(x,y,route){
  let min=Infinity;
  for(let i=0;i<route.length;i++){
   let d=Math.hypot(x-route[i].x,y-route[i].y);
   if(d<min)min=d;
  }
  return min;
 }
 function scenery(ctx,r,route){
  // Forested plateaus and exposed sides recall the screenshot's green
  // tabletop landscape and cut brown cliff faces, without claiming to use
  // the absent historical source 3D models.
  for(let i=0;i<27;i++){
   const x=r()*WIDTH,y=r()*HEIGHT,rx=40+r()*106,ry=25+r()*65;
   const near=distanceToRoute(x,y,route);
   if(near<110)continue;
   blob(ctx,x+7,y+26,rx*1.14,ry*.9,'#2e33297d',r,-.1,11);
   blob(ctx,x+1,y+17,rx*1.04,ry*.9,'#5d4630',r,-.13,11);
   blob(ctx,x,y+8,rx,ry,'#91734c',r,-.13,11);
   blob(ctx,x-7,y-6,rx*.96,ry*.88,'#475d35',r,-.13,12);
   blob(ctx,x-10,y-14,rx*.77,ry*.69,'#657c40',r,-.13,12);
   for(let j=0;j<11;j++){
    const px=x+(r()-.5)*rx*1.5,py=y+ry*.38+r()*ry*.4;
    ctx.strokeStyle=pick(['#3c3128','#8b7456','#554833'],r);
    ctx.lineWidth=1+r()*2;ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(px+2+r()*6,py+4+r()*11);ctx.stroke();
   }
  }
  // Tree crowns form distinct clumps, avoiding source tile centres.
  let trees=0;
  for(let n=0;n<930&&trees<145;n++){
   const x=22+r()*(WIDTH-44),y=20+r()*(HEIGHT-40);
   if(distanceToRoute(x,y,route)<70)continue;
   if(r()<.17)continue;
   const s=14+r()*26;
   tree(ctx,x,y,s,r);trees++;
  }
  let rocks=0;
  for(let i=0;i<220&&rocks<63;i++){
   const x=r()*WIDTH,y=r()*HEIGHT;
   if(distanceToRoute(x,y,route)<58)continue;
   stone(ctx,x,y,.35+r()*.95,r);rocks++;
  }
  // Source-style top-lit ground tufts: small, noninteractive fragments.
  for(let i=0;i<490;i++){
   const x=r()*WIDTH,y=r()*HEIGHT;
   if(distanceToRoute(x,y,route)<40&&r()<.82)continue;
   ctx.beginPath();ctx.moveTo(x,y+2);ctx.lineTo(x-2,y-5);ctx.moveTo(x,y+2);ctx.lineTo(x+3,y-7);
   ctx.strokeStyle=pick(['#a3a96a6e','#183b296f','#c6b67a63'],r);
   ctx.lineWidth=.7+r()*.9;ctx.stroke();
  }
  return {trees,rocks};
 }
 function draw(map,sourcePath){
  if(!map||!Array.isArray(sourcePath)||!sourcePath.length)return;
  const board=$('board-world');
  if(!board)return;
  let canvas=$('dice-terrain-canvas');
  if(!canvas){
   canvas=document.createElement('canvas');
   canvas.id='dice-terrain-canvas';
   canvas.setAttribute('aria-hidden','true');
   canvas.width=WIDTH;canvas.height=HEIGHT;
   board.insertBefore(canvas,board.firstChild);
  }
  const route=sourcePath.map(p=>({x:p.x/100*WIDTH,y:p.y/100*HEIGHT}));
  const seed=hashString(String(map)+'|'+route.length+'|'+route.slice(0,12).map(p=>p.x.toFixed(1)+','+p.y.toFixed(1)).join(';'));
  const key=map+'|'+seed;
  if(key===cacheKey)return;
  const ctx=canvas.getContext('2d',{alpha:false});
  if(!ctx)return;
  const r=generator(seed);
  meadow(ctx,r,route);
  const features=scenery(ctx,r,route);
  canvas.dataset.terrainMap=map;
  canvas.dataset.terrainSeed=String(seed);
  cacheKey=key;
  lastState={map,seed,pathLength:route.length,size:[WIDTH,HEIGHT],...features,source:'DMP coordinates',landscape:'inferred canvas, not original 3D'};
 }
 window.__LEAF_DICE_TERRAIN__={draw,getState:()=>lastState,refresh:()=>{cacheKey=''}};
})();
