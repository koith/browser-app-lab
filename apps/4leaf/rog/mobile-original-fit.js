/* Original 800x600 client: keep desktop layout and scale the phone viewport.
 * Installed early in <head> so the initial layout uses the design width. */
(function(){
 'use strict';
 var DESIGN_W=800,DESIGN_H=600;
 var meta=document.querySelector('meta[name="viewport"]');
 if(!meta)return;
 var DEVICE='width=device-width, initial-scale=1, viewport-fit=cover';
 var coarse=function(){return window.matchMedia&&window.matchMedia('(pointer:coarse)').matches};
 var applied=null;
 function measureAndApply(){
  meta.setAttribute('content',DEVICE);
  var w=document.documentElement.clientWidth||window.innerWidth;
  var h=window.innerHeight;
  if(!coarse()||Math.min(w,h)>600||!w||!h){
   applied=null;
   document.documentElement.removeAttribute('data-leaf-phone-fit');
   document.documentElement.removeAttribute('data-leaf-chat-open');
   return;
  }
  var landscape=w>h;
  var width=landscape?Math.max(DESIGN_W,Math.ceil(DESIGN_H*w/h)):DESIGN_W;
  meta.setAttribute('content','width='+width+', viewport-fit=cover');
  applied={landscape:landscape,layoutWidth:width,deviceWidth:w,deviceHeight:h,scale:+(w/width).toFixed(4)};
  document.documentElement.setAttribute('data-leaf-phone-fit',landscape?'landscape':'portrait');
  if(!landscape)document.documentElement.removeAttribute('data-leaf-chat-open');
 }
 measureAndApply();
 var timer=null;
 function again(){clearTimeout(timer);timer=setTimeout(measureAndApply,180)}
 window.addEventListener('orientationchange',again);
 if(window.screen&&screen.orientation&&screen.orientation.addEventListener)screen.orientation.addEventListener('change',again);
 document.addEventListener('DOMContentLoaded',function(){
  var chat=document.createElement('button');chat.type='button';chat.id='leaf-phone-chat-toggle';
  chat.textContent='채팅';chat.setAttribute('aria-pressed','false');
  chat.onclick=function(){
   var open=document.documentElement.getAttribute('data-leaf-chat-open')!=='true';
   document.documentElement.setAttribute('data-leaf-chat-open',String(open));
   chat.setAttribute('aria-pressed',String(open));
   chat.textContent=open?'채팅 닫기':'채팅';
   window.dispatchEvent(new Event('resize'));
  };
  var rotate=document.createElement('div');rotate.id='leaf-phone-rotate';rotate.setAttribute('role','status');
  rotate.textContent='↻ 휴대폰을 가로로 돌리면 원작 화면이 크게 보입니다';
  document.body.append(chat,rotate);
 });
 window.__LEAF_PHONE_FIT__={getState:function(){return applied},refresh:measureAndApply};
})();
