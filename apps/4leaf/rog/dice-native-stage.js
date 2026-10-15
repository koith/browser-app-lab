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
 window.__LEAF_DICE_NATIVE__={fit,getState:state};
})();
