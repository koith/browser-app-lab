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
 function fit(){
  const x=wrap.clientWidth,y=wrap.clientHeight;
  if(!x||!y)return;
  const scale=Math.max(.1,Math.min(x/W,y/H));
  stage.style.transform='translate3d('+((x-W*scale)/2).toFixed(2)+'px,'+
   ((y-H*scale)/2).toFixed(2)+'px,0) scale('+scale+')';
  stage.dataset.scale=scale.toFixed(6);
 }
 function state(){
  return {width:W,height:H,scale:Number(stage.dataset.scale)||0,
   source:wrap.classList.contains('config-open')?'Room/roomback.png':'Map/mapback.png',
   actualStageWidth:stage.getBoundingClientRect().width,
   actualStageHeight:stage.getBoundingClientRect().height,
   availableWidth:wrap.clientWidth,availableHeight:wrap.clientHeight};
 }
 if('ResizeObserver' in window)new ResizeObserver(fit).observe(wrap);
 window.addEventListener('resize',fit,{passive:true});
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
 window.__LEAF_DICE_NATIVE__={fit,getState:state,closePicker};
})();
