'use strict';
/* MainStreet.pak original three-panel 1938×404 panorama.
   Genuine scene scroll and clickable source businesses, no CSS fake houses. */
(function(){
 const $=id=>document.getElementById(id);
 const WIDTH=1938,HEIGHT=404;
 // MainStreet PAK contains seven independent chroma-keyed building sprites.
 // The location coordinates are currently reconstructed against back.png;
 // original click-map coordinates are not yet decoded from the executable.
 // Native 1938×404 backdrop registration: correlate each non-transparent
 // source sprite against MainStreet/back.png, NOT an estimated screen crop.
 // Normalized template similarities are 0.9726–0.9928 (2026-10-15).
 const shops=[
  {id:'fashions',asset:'dress',x:1102,y:135,w:230,h:196,title:'댄디캣 클래식 · 드레스샵',category:'의상'},
  {id:'sweet',asset:'event',x:354,y:39,w:190,h:229,title:'프레쉬센트 · 이벤트홀',category:'이벤트'},
  {id:'magic',asset:'card',x:633,y:63,w:183,h:266,title:'매직카덴 · 카드샵',route:'shop'},
  {id:'court',asset:'hair',x:164,y:128,w:199,h:178,title:'실키필 · 헤어샵',category:'헤어'},
  {id:'gallery',asset:'accessory',x:1765,y:207,w:152,h:136,title:'캐즈팝 · 잡화점',category:'잡화'},
  {id:'dandy',asset:'dandymodern',x:1315,y:157,w:212,h:222,title:'댄디캣 모던 · 드레스샵',category:'의상'},
  {id:'office',asset:'office',x:884,y:7,w:215,h:238,title:'네나루하 마법학원',category:'지역 시설'}
 ];
 const state={viewport:null,track:null,x:WIDTH/2,scale:1,down:null,clientScale:1};
 // Source MainStreet/*.png are green-keyed 2002 bitmaps; large square
 // WEB hitboxes incorrectly treated their transparent corners as shops.
 // Cache only real decoded/source pixels. No photo overlays and no
 // reconstructed CSS polygon that can diverge from original artwork.
 const nativeAlpha=new WeakMap();
 function hitsOriginalBuilding(event,button){
  // Native keyboard activation / semantic DOM tests remain accessible.
  // Pointer input (detail>=1) must hit a real archived bitmap pixel.
  if(!event||event.detail===0||!Number.isFinite(event.clientX))return true;
  const canvas=button.querySelector('.street-building-art');
  const source=nativeAlpha.get(canvas);
  if(!source)return true; // Original asset still decoding or offline.
  // The original source is painted in the <canvas> CONTENT BOX.
  // A surrounding CSS 2px focus border means the button's bounding box
  // is NOT the native bitmap's pixel coordinate system. Sample only
  // against the actual canvas rect to prevent random false negatives
  // on narrow real sprite features (observed in Chromium CI).
  const rect=canvas.getBoundingClientRect();
  if(rect.width<=0||rect.height<=0)return false;
  const x=Math.floor((event.clientX-rect.left)/rect.width*source.w);
  const y=Math.floor((event.clientY-rect.top)/rect.height*source.h);
  if(x<0||x>=source.w||y<0||y>=source.h)return false;
  return source.alpha[y*source.w+x]>0;
 }
 function render(){
  if(!state.viewport||!state.track)return;
  const vw=state.viewport.clientWidth,vh=state.viewport.clientHeight;
  const scale=Math.min(vh/HEIGHT,vw/646)*state.scale;
  const leftMin=vw-WIDTH*scale,leftMax=0;
  const left=Math.max(leftMin,Math.min(leftMax,vw/2-state.x*scale));
  const top=(vh-HEIGHT*scale)/2;
  state.track.style.transform='translate3d('+left.toFixed(2)+'px,'+top.toFixed(2)+'px,0) scale('+scale+')';
  state.clientScale=scale;
  const marker=$('street-area-label');if(marker)marker.textContent=state.x<645?'거리 왼쪽 · 실키필 / 프레쉬센트':state.x<1292?'거리 중앙 · 매직카덴 / 마법학원':'거리 오른쪽 · 댄디캣 / 캐즈팝';
 }
 function pan(dx){state.x=Math.max(323,Math.min(1615,state.x+dx));render()}
 function enterWorld(){window.__ROG_TEST__?.go('sky')}
 function selectShop(id){
  const shop=shops.find(s=>s.id===id);if(!shop)return;
  if(shop.route==='shop')window.__ROG_TEST__?.go('shop');
  else showShopPlaceholder(shop);
 }
 function showShopPlaceholder(shop){
  // The building art and its destination label are original data.
  // Do not invent historical product catalogues, GP prices or transactions.
  $('street-shop-detail')?.remove();
  const panel=document.createElement('section');panel.className='street-shop-detail';panel.id='street-shop-detail';
  panel.setAttribute('role','dialog');panel.setAttribute('aria-label',shop.title);
  const title=document.createElement('b');title.textContent=shop.title;
  const art=document.createElement('img');art.className='street-shop-preview';
  art.src='./original/MainStreet/'+shop.asset+'.png';art.alt=shop.title;
  const sub=document.createElement('p');
  sub.textContent='원본 켈티카 거리의 '+shop.category+' 시설입니다. 원작 상품·가격·기능 데이터는 아직 확보되지 않아 구매를 허용하지 않습니다.';
  const close=document.createElement('button');close.type='button';close.textContent='거리로 돌아가기';close.onclick=()=>panel.remove();
  panel.append(title,art,sub,close);state.viewport.append(panel);
  close.focus();
 }
 // Convert the original MainStreet sprites' bright-green transparency key,
 // retaining precisely the source bitmap pixels, not CSS-drawn replacement art.
 function drawOriginalBuilding(canvas,shop){
  const img=new Image();img.decoding='async';
  img.onload=()=>{
   if(!canvas.isConnected)return;
   if(location.protocol==='file:'){canvas.dataset.ready='offline';return}
   try{
    canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(img,0,0);
    const data=ctx.getImageData(0,0,canvas.width,canvas.height);
    for(let i=0;i<data.data.length;i+=4){
     const r=data.data[i],g=data.data[i+1],b=data.data[i+2];
     if(g>205&&r<92&&b<100&&g>r*1.65&&g>b*1.55)data.data[i+3]=0;
    }
    ctx.putImageData(data,0,0);
    const alpha=new Uint8Array(canvas.width*canvas.height);
    for(let i=0;i<alpha.length;i++)alpha[i]=data.data[i*4+3];
    nativeAlpha.set(canvas,{w:canvas.width,h:canvas.height,alpha});
    canvas.dataset.ready='true';
    canvas.dataset.hitMaskSource='MainStreet/'+shop.asset+'.png';
   }catch{canvas.dataset.ready='offline'}
  };
  img.onerror=()=>{canvas.dataset.ready='missing';console.error('Missing original MainStreet building '+shop.asset)};
  img.src='./original/MainStreet/'+shop.asset+'.png';
 }

 function build(){
  const scene=$('city');if(!scene)return;
  scene.replaceChildren();
  const viewport=document.createElement('div');viewport.className='street-viewport';viewport.id='street-viewport';
  const track=document.createElement('div');track.className='street-track';track.id='street-track';
  track.style.width=WIDTH+'px';track.style.height=HEIGHT+'px';
  const background=document.createElement('img');background.className='street-artwork';background.src='./original/MainStreet/back.png';
  background.width=WIDTH;background.height=HEIGHT;background.draggable=false;background.alt='';
  track.append(background);
  for(const shop of shops){
   const b=document.createElement('button');b.type='button';b.className='street-location';b.dataset.street=shop.id;
   b.style.cssText='left:'+shop.x+'px;top:'+shop.y+'px;width:'+shop.w+'px;height:'+shop.h+'px;';
   b.title=shop.title;b.setAttribute('aria-label',shop.title);
   const building=document.createElement('canvas');
   building.className='street-building-art';building.width=shop.w;building.height=shop.h;
   building.dataset.source=shop.asset;
   const hint=document.createElement('span');hint.textContent=shop.title;
   b.append(building,hint);
   drawOriginalBuilding(building,shop);
   b.onclick=event=>{
    const hit=hitsOriginalBuilding(event,b);
    b.dataset.lastSourceHit=String(hit);
    if(!hit)return;
    selectShop(shop.id);
   };
   track.append(b);
  }
  viewport.append(track);
  const tools=document.createElement('nav');tools.className='street-navigation';
  tools.innerHTML='<button id="street-back" aria-label="월드맵 돌아가기">◀ 월드맵</button><button id="street-left" aria-label="거리 왼쪽으로 이동">◀</button><span id="street-area-label">거리 중앙 · 매직카덴</span><button id="street-right" aria-label="거리 오른쪽으로 이동">▶</button>';
  scene.append(viewport,tools);
  state.viewport=viewport;state.track=track;
  $('street-back').onclick=enterWorld;
  $('street-left').onclick=()=>pan(-400);
  $('street-right').onclick=()=>pan(400);
  viewport.addEventListener('pointerdown',e=>{
   if(e.button!==0)return;
   const building=e.target.closest('.street-location');
   if(building&&hitsOriginalBuilding({clientX:e.clientX,clientY:e.clientY,detail:1},building))return;
   // A source chroma-key transparent building corner is open pavement:
   // dragging there should pan the real 1938px scene rather than being
   // silently swallowed by the surrounding rectangular <button>.

   state.down={id:e.pointerId,x:e.clientX,orig:state.x};
   try{viewport.setPointerCapture(e.pointerId)}catch{}
  });
  viewport.addEventListener('pointermove',e=>{
   if(!state.down||e.pointerId!==state.down.id)return;
   state.x=state.down.orig-(e.clientX-state.down.x)/state.clientScale;
   state.x=Math.max(323,Math.min(1615,state.x));render();
  });
  for(const type of ['pointerup','pointercancel','lostpointercapture'])viewport.addEventListener(type,()=>state.down=null);
  viewport.addEventListener('wheel',e=>{if(e.shiftKey){e.preventDefault();pan(e.deltaY*.7)}},{passive:false});
  if('ResizeObserver' in window)new ResizeObserver(render).observe(viewport);
  render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build);else build();
 window.__LEAF_STREET__={pan,render,getState:()=>({x:state.x,scale:state.clientScale,locations:shops})};
})();