/* 4LEAF phone fit v2.
 * Never mutate the viewport meta tag on rotation: changing layout widths
 * makes iOS Safari re-evaluate its zoom and can enlarge/crop a live scene.
 * Instead keep the real device viewport and uniformly fit the 800x600 client.
 */
(function(){
 'use strict';
 var DESIGN_W=800,DESIGN_H=600;
 var applied=null,scheduled=false;
 var root=document.documentElement;
 var coarse=window.matchMedia?window.matchMedia('(pointer:coarse)'):null;
 var orientation=window.matchMedia?window.matchMedia('(orientation: landscape)'):null;
 function isPhone(){
  var screenShort=Math.min(
   Number(window.screen&&screen.width)||Infinity,
   Number(window.screen&&screen.height)||Infinity);
  return Boolean(coarse&&coarse.matches&&screenShort<=600);
 }
 function focusedEditor(){
  var e=document.activeElement;
  return e&&(/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName)||e.isContentEditable);
 }
 function measure(){
  // visualViewport gives the available area as Safari's toolbars expand/collapse.
  // It does NOT require changing meta width to a synthetic 1300px layout.
  var vv=window.visualViewport;
  var w=vv&&vv.width>0?vv.width:window.innerWidth;
  var h=vv&&vv.height>0?vv.height:window.innerHeight;
  if(!isPhone()||!Number.isFinite(w)||!Number.isFinite(h)||w<=0||h<=0){
   applied=null;
   root.removeAttribute('data-leaf-phone-fit');
   root.removeAttribute('data-leaf-chat-open');
   root.style.removeProperty('--leaf-fit-scale');
   return;
  }
  var landscape=orientation?orientation.matches:window.innerWidth>window.innerHeight;
  // Do not shrink an already fitted game to a postage stamp while typing.
  // The OS keyboard moves the visual viewport; keep the previous stable scale.
  var keyboard=Boolean(focusedEditor()&&applied&&applied.landscape===landscape&&
   h<applied.deviceHeight*0.78);
  if(keyboard)h=applied.deviceHeight;
  // 2px visual margin avoids fractional rounding pushing an edge off-screen.
  var scale=Math.min(1,Math.max(0.1,Math.min((w-2)/DESIGN_W,(h-2)/DESIGN_H)));
  scale=Number(scale.toFixed(5));
  var next={
   landscape:landscape,layoutWidth:DESIGN_W,layoutHeight:DESIGN_H,
   deviceWidth:Number(w.toFixed(2)),deviceHeight:Number(h.toFixed(2)),
   scale:scale,method:'uniform-transform-fit'
  };
  applied=next;
  root.style.setProperty('--leaf-fit-scale',String(scale));
  root.setAttribute('data-leaf-phone-fit',landscape?'landscape':'portrait');
  if(!landscape)root.removeAttribute('data-leaf-chat-open');
 }
 function schedule(){
  if(scheduled)return;
  scheduled=true;
  requestAnimationFrame(function(){scheduled=false;measure()});
 }
 // First pass is safe during <head>, before #app and CSS are attached.
 measure();
 window.addEventListener('resize',schedule,{passive:true});
 window.addEventListener('orientationchange',schedule,{passive:true});
 window.addEventListener('pageshow',schedule,{passive:true});
 document.addEventListener('focusin',schedule);
 document.addEventListener('focusout',schedule);
 if(window.screen&&screen.orientation&&screen.orientation.addEventListener)
  screen.orientation.addEventListener('change',schedule);
 if(window.visualViewport){
  visualViewport.addEventListener('resize',schedule,{passive:true});
  visualViewport.addEventListener('scroll',schedule,{passive:true});
 }
 document.addEventListener('DOMContentLoaded',function(){
  var chat=document.createElement('button');
  chat.type='button';chat.id='leaf-phone-chat-toggle';
  chat.textContent='채팅';chat.setAttribute('aria-pressed','false');
  chat.addEventListener('click',function(){
   var open=root.getAttribute('data-leaf-chat-open')!=='true';
   root.setAttribute('data-leaf-chat-open',String(open));
   chat.setAttribute('aria-pressed',String(open));
   chat.textContent=open?'채팅 닫기':'채팅';
  });
  var rotate=document.createElement('div');
  rotate.id='leaf-phone-rotate';rotate.setAttribute('role','status');
  rotate.textContent='↻ 휴대폰을 가로로 돌려 주세요';
  document.body.append(chat,rotate);
  schedule();
 });
 window.__LEAF_PHONE_FIT__={
  getState:function(){return applied?Object.assign({},applied):null},
  refresh:measure
 };
})();
