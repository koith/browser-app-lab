'use strict';
/* Original 4LEAF WorldMap.pak scene, independently rendered from six real four-frame
   sprites + the authentic WorldMapBack art. No full-screen screenshot is used. */
(function(){
 const WIDTH=796,HEIGHT=528;
 const REGIONS=[
  {id:'street',name:'켈티카의 거리',kind:'street',x:265,y:33,w:203,h:112,hit:[279,42,165,85]},
  {id:'knights',name:'레코르다블 · 기사단',kind:'knights',x:144,y:96,w:203,h:218,hit:[173,151,108,69]},
  {id:'north',name:'북 하이아칸 · 채팅',kind:'northchatrgn',x:305,y:113,w:268,h:140,hit:[351,149,134,75]},
  {id:'south',name:'남 하이아칸 · 채팅',kind:'southchatrgn',x:200,y:205,w:239,h:139,hit:[230,251,130,70]},
  {id:'dice',name:'주사위의 잔영',kind:'dice',x:383,y:280,w:198,h:133,hit:[426,310,134,90]},
  {id:'my4leaf',name:'마이리프 · 내 정보',kind:'m4leaf',x:500,y:162,w:138,h:147,hit:[525,177,105,117]}
 ];
 const ref={stage:null,viewport:null,scale:1,baseScale:1,x:0,y:0,region:null,layers:new Map(),ro:null};
 let dragging=null,frame=0,lastRender=0;
 const $=id=>document.getElementById(id);
 const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
 function images(kind){return './original/WorldMap/'+kind+'.png'}
 function makeCanvasSprite(region){
   const canvas=document.createElement('canvas');
   canvas.width=region.w;canvas.height=region.h;canvas.className='world-sprite';
   canvas.style.cssText='position:absolute;pointer-events:none;left:'+region.x+'px;top:'+region.y+'px;width:'+region.w+'px;height:'+region.h+'px;z-index:2;';
   const img=new Image();img.decoding='async';img.src=images(region.kind);
   const sheet=[];
   img.onload=()=>{
     try{
       const buffer=document.createElement('canvas');buffer.width=img.naturalWidth;buffer.height=img.naturalHeight;
       const ctx=buffer.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
       const data=ctx.getImageData(0,0,buffer.width,buffer.height);
       for(let i=0;i<data.data.length;i+=4){
         const r=data.data[i],g=data.data[i+1],b=data.data[i+2];
         if(g>220&&r<72&&b<85&&g>r*1.8&&g>b*1.6)data.data[i+3]=0;
       }
       ctx.putImageData(data,0,0);
       for(let i=0;i<4;i++){
         const fr=document.createElement('canvas');fr.width=region.w;fr.height=region.h;
         fr.getContext('2d').drawImage(buffer,i*region.w,0,region.w,region.h,0,0,region.w,region.h);
         sheet.push(fr);
       }
       ref.layers.set(region.id,{canvas,sheet});
       renderLayer(region.id,0);
     }catch{ /* WorldMapBack remains a usable original scene. */ }
   };
   return canvas;
 }
 function renderLayer(regionId,index){
   const layer=ref.layers.get(regionId);if(!layer)return;
   const ctx=layer.canvas.getContext('2d');ctx.clearRect(0,0,layer.canvas.width,layer.canvas.height);
   if(ref.region===regionId&&layer.sheet.length)ctx.drawImage(layer.sheet[index%layer.sheet.length],0,0);
 }
 function renderScene(){
   if(!ref.viewport||!ref.stage)return;
   const vw=ref.viewport.clientWidth,vh=ref.viewport.clientHeight;
   ref.baseScale=Math.min(vw/WIDTH,vh/HEIGHT);
   const scaled=ref.baseScale*ref.scale;
   const maxX=Math.max(0,(WIDTH*scaled-vw)/2),maxY=Math.max(0,(HEIGHT*scaled-vh)/2);
   ref.x=clamp(ref.x,-maxX,maxX);ref.y=clamp(ref.y,-maxY,maxY);
   ref.stage.style.transform='translate3d('+((vw-WIDTH*scaled)/2+ref.x)+'px,'+((vh-HEIGHT*scaled)/2+ref.y)+'px,0) scale('+scaled+')';
   const indicator=$('world-zoom-label');if(indicator)indicator.textContent=Math.round(ref.scale*100)+'%';
 }
 function zoom(by){
   ref.scale=clamp(Math.round((ref.scale+by)*100)/100,1,3.5);
   if(ref.scale<=1){ref.x=0;ref.y=0}renderScene();
 }
 function clickRegion(id){
   const data=REGIONS.find(r=>r.id===id);if(!data)return;
   if(id==='north'||id==='south'){
     if(window.__LEAF_SOCIAL__?.openRegion)window.__LEAF_SOCIAL__.openRegion(id);
     window.__ROG_TEST__?.go('rooms');
   }else if(id==='street')window.__ROG_TEST__?.go('city');
   else if(id==='dice')window.__ROG_TEST__?.go('lobby');
   else if(id==='knights'){
     window.__LEAF_SOCIAL__?.openBoard?.();
     window.__ROG_TEST__?.go('rooms');
   }else if(id==='my4leaf')showProfile();
 }
 function showProfile(){
   let panel=$('world-profile-modal');if(panel){panel.remove();return}
   panel=document.createElement('section');panel.id='world-profile-modal';panel.className='world-profile-modal';
   panel.innerHTML='<div class="world-profile-heading">MY 4LEAF <button aria-label="닫기">×</button></div><div class="world-profile-body"><img alt="" src="./original/Registry/sava00.png"><div><b id="world-profile-name"></b><small id="world-profile-gp"></small><p>마이리프 · 프로필</p><button id="world-profile-rename">닉네임 변경</button></div></div>';
   ref.viewport.append(panel);
   $('world-profile-name').textContent=$('profile-name')?.textContent||'Guest';
   $('world-profile-gp').textContent=$('gp')?.textContent+' GP';
   panel.querySelector('.world-profile-heading button').onclick=()=>panel.remove();
   $('world-profile-rename').onclick=()=>{$('rename')?.click();panel.remove()};
 }
 function build(){
   const scene=$('sky');if(!scene)return;
   scene.replaceChildren();
   const viewport=document.createElement('div');viewport.className='leaf-world-viewport';viewport.id='leaf-world-viewport';
   const stage=document.createElement('div');stage.className='leaf-world-stage';stage.id='leaf-world-stage';
   stage.style.cssText='width:'+WIDTH+'px;height:'+HEIGHT+'px;';
   const backdrop=document.createElement('img');backdrop.src='./original/WorldMap/worldmapback.png';backdrop.alt='';backdrop.width=WIDTH;backdrop.height=HEIGHT;backdrop.className='world-backdrop';backdrop.draggable=false;stage.append(backdrop);
   for(const region of REGIONS){
     stage.append(makeCanvasSprite(region));
     const hit=document.createElement('button');hit.className='world-location';hit.type='button';
     hit.dataset.region=region.id;hit.title=region.name;hit.setAttribute('aria-label',region.name);
     const [x,y,w,h]=region.hit;hit.style.cssText='left:'+x+'px;top:'+y+'px;width:'+w+'px;height:'+h+'px;';
     const tip=document.createElement('span');tip.className='world-location-tip';tip.textContent=region.name;
     hit.append(tip);
     hit.addEventListener('mouseenter',()=>{ref.region=region.id;renderLayer(region.id,frame)});
     hit.addEventListener('focus',()=>{ref.region=region.id;renderLayer(region.id,frame)});
     hit.addEventListener('mouseleave',()=>{if(ref.region===region.id)ref.region=null;renderLayer(region.id,0)});
     hit.addEventListener('blur',()=>{if(ref.region===region.id)ref.region=null;renderLayer(region.id,0)});
     hit.addEventListener('click',()=>clickRegion(region.id));
     stage.append(hit);
   }
   const controls=document.createElement('div');controls.className='world-map-controls';
   controls.innerHTML='<button id="world-zoom-out" aria-label="월드맵 축소">−</button><span id="world-zoom-label">100%</span><button id="world-zoom-in" aria-label="월드맵 확대">＋</button><button id="world-zoom-reset" aria-label="월드맵 전체보기">⌂</button>';
   const title=document.createElement('div');title.className='world-map-caption';title.textContent='4LEAF WORLD MAP　·　원본 월드맵';
   viewport.append(stage);scene.append(viewport,controls,title);
   ref.viewport=viewport;ref.stage=stage;
   $('world-zoom-out').onclick=()=>zoom(-.25);
   $('world-zoom-in').onclick=()=>zoom(.25);
   $('world-zoom-reset').onclick=()=>{ref.x=0;ref.y=0;ref.scale=1;renderScene()};
   viewport.addEventListener('pointerdown',e=>{
     if(e.target.closest('.world-location')||e.button!==0)return;
     dragging={id:e.pointerId,x:e.clientX,y:e.clientY,px:ref.x,py:ref.y};
     try{viewport.setPointerCapture(e.pointerId)}catch{}
   });
   viewport.addEventListener('pointermove',e=>{
     if(!dragging||e.pointerId!==dragging.id||ref.scale<=1)return;
     ref.x=dragging.px+e.clientX-dragging.x;ref.y=dragging.py+e.clientY-dragging.y;renderScene();
   });
   for(const name of ['pointerup','pointercancel','lostpointercapture'])viewport.addEventListener(name,()=>dragging=null);
   viewport.addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();zoom(e.deltaY<0?.25:-.25)}},{passive:false});
   if('ResizeObserver' in window){ref.ro=new ResizeObserver(renderScene);ref.ro.observe(viewport)}
   renderScene();
   if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
     setInterval(()=>{if(!$('sky')?.classList.contains('hidden')&&ref.region!==null){frame=(frame+1)%4;renderLayer(ref.region,frame)}},420);
   }
 }
 function init(){build()}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 window.__LEAF_WORLD__={clickRegion,build,zoom,getState:()=>({scale:ref.scale,x:ref.x,y:ref.y,locations:REGIONS.map(({id,hit})=>({id,hit}))})};
})();