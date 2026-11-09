'use strict';
// 4LEAF native Genesis World client: Map/mapback.png and Room/roomback.png
// are independent 794x404 scene assets. Preserve source pixels and position
// actual working controls in that coordinate system instead of stretching the
// unrelated 800x540 GIF mockup.
(function(){
 const $=id=>document.getElementById(id);
 const W=794,H=404;
 const wrap=$('dice-lobby-scene');
 if(!wrap)return;
 const stage=document.createElement('div');
 stage.className='dice-native-stage';
 stage.id='dice-native-stage';
 stage.dataset.source='Map/mapback.png';
 // Existing buttons keep their identity and event listeners. This is a
 // reparenting operation, not a screenshot replacing the interactive UI.
 while(wrap.firstChild)stage.append(wrap.firstChild);
 const picker=document.createElement('button');
 picker.type='button';picker.id='dice-team-picker';
 picker.setAttribute('aria-label','체스맨 파티 선택창 열기');
 picker.setAttribute('aria-expanded','false');
 picker.setAttribute('aria-controls','dice-room-config');
 picker.textContent='체스맨 선택';
 picker.onclick=()=>{
  if(!wrap.classList.contains('config-open'))return;
  const open=stage.classList.toggle('team-picker-open');
  picker.setAttribute('aria-expanded',String(open));
  picker.setAttribute('aria-label',open?'체스맨 파티 선택창 닫기':'체스맨 파티 선택창 열기');
 };
 stage.append(picker);
 wrap.append(stage);
 // On a 390px iPhone the 794px original bitmap used to shrink to ~49%.
 // Its 10px ROOM/PLAYER text then became only 5px and looked like an empty
 // waiting room. Preserve ORIGINAL pixels and uniform aspect ratio, but
 // allow an enlarged, horizontally pannable native bitmap on narrow screens.
 // Desktop keeps the historic fit-to-viewport geometry unchanged.
 let zoomed=false,panX=null,panY=null,drag=null;
 const narrow=()=>window.innerWidth<=650&&wrap.clientWidth<=650;
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const controls=document.createElement('div');
 controls.id='dice-room-view-controls';controls.className='dice-room-view-controls';
 const zoomButton=document.createElement('button');zoomButton.type='button';
 zoomButton.id='dice-room-zoom-toggle';
 zoomButton.setAttribute('aria-label','주잔 대기방 원본 화면 확대 또는 전체 보기');
 zoomButton.setAttribute('aria-pressed','false');
 const panHint=document.createElement('span');panHint.id='dice-room-pan-hint';
 panHint.textContent='확대 시 빈 배경을 가로로 밀어 다른 영역 보기';
 controls.append(zoomButton,panHint);
 wrap.append(controls);
 const view={scale:0,x:0,y:0,fitScale:0};
 function fit(){
  const x=wrap.clientWidth,y=wrap.clientHeight;
  if(!x||!y)return;
  // Keep native source aspect ratio at every zoom/viewport size.
  const base=Math.max(.1,Math.min(x/W,y/H));
  const zoom=narrow()&&zoomed;
  const scale=base*(zoom?1.48:1);
  const width=W*scale,height=H*scale;
  const minX=Math.min(0,x-width),minY=Math.min(0,y-height);
  const posX=width<=x?(x-width)/2:clamp(panX??0,minX,0);
  const posY=height<=y?(y-height)/2:clamp(panY??(y-height)/2,minY,0);
  panX=posX;panY=posY;
  stage.style.transform='translate3d('+posX.toFixed(2)+'px,'+
   posY.toFixed(2)+'px,0) scale('+scale+')';
  stage.dataset.scale=scale.toFixed(6);
  stage.dataset.viewMode=zoom?'mobile-enlarged':'whole-native-scene';
  view.scale=scale;view.x=posX;view.y=posY;view.fitScale=base;
  zoomButton.setAttribute('aria-pressed',String(zoom));
  zoomButton.textContent=zoom?'⊟ 전체 화면':'⊞ 확대 보기';
  panHint.hidden=!zoom;
 }
 function focusPart(part){
  if(!narrow()||!zoomed){fit();return}
  const x=wrap.clientWidth;
  const scale=Math.max(.1,Math.min(x/W,wrap.clientHeight/H))*1.48;
  // On CREATE move the original 2002 READY sprite into the usable phone
  // viewport. Room list initially keeps CREATE visible on the left.
  panX=part==='ready'?clamp(x*.5-445*scale,Math.min(0,x-W*scale),0):0;
  fit();
 }
 zoomButton.onclick=()=>{
  zoomed=!zoomed;panX=null;panY=null;
  focusPart(wrap.classList.contains('config-open')?'ready':'list');
 };
 // Zoom is the sensible mobile default. A one-tap whole-scene option
 // remains present for original 794x404 pixel-layout comparisons.
 zoomed=narrow();
 stage.addEventListener('pointerdown',event=>{
  if(!narrow()||!zoomed||event.button!==0||
   event.target.closest('button,input,select,textarea,a,label,[role="button"]'))return;
  drag={id:event.pointerId,startX:event.clientX,startY:event.clientY,
   x:view.x,y:view.y};
  stage.setPointerCapture?.(event.pointerId);
 });
 stage.addEventListener('pointermove',event=>{
  if(!drag||event.pointerId!==drag.id)return;
  panX=drag.x+event.clientX-drag.startX;
  panY=drag.y+event.clientY-drag.startY;
  fit();
 });
 const endDrag=event=>{
  if(drag?.id===event.pointerId)drag=null;
 };
 stage.addEventListener('pointerup',endDrag);
 stage.addEventListener('pointercancel',endDrag);
 function state(){
  return {width:W,height:H,scale:view.scale,fitScale:view.fitScale,
   x:view.x,y:view.y,zoomed:narrow()&&zoomed,
   source:wrap.classList.contains('config-open')?'Room/roomback.png':'Map/mapback.png',
   actualStageWidth:stage.getBoundingClientRect().width,
   actualStageHeight:stage.getBoundingClientRect().height,
   availableWidth:wrap.clientWidth,availableHeight:wrap.clientHeight};
 }
 if('ResizeObserver' in window)new ResizeObserver(fit).observe(wrap);
 window.addEventListener('resize',fit,{passive:true});
 window.addEventListener('leaf-route-change',fit);
 fit();
 function closePicker(){
  stage.classList.remove('team-picker-open');
  picker.setAttribute('aria-expanded','false');
  picker.setAttribute('aria-label','체스맨 파티 선택창 열기');
 }
 wrap.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&stage.classList.contains('team-picker-open')){
   closePicker();picker.focus();event.stopPropagation();
  }
 });
 window.__LEAF_DICE_NATIVE__={fit,getState:state,closePicker,focusPart};
})();
