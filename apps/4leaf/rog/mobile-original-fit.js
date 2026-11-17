/* 4LEAF mobile landscape scene-fit v3.
 * Source images have different dimensions: Genesis Region/Map/Room 794x404,
 * World 796x528, battle 800x600. Do NOT fit all of them into the 800x600
 * game canvas or force every <section> to a horizontal flex row.
 * The outer web chrome fills the physical viewport while original source
 * image assets remain undistorted, clickable and centred at their own ratio.
 */
(function(){
 'use strict';
 var root=document.documentElement,applied=null,scheduled=false;
 var coarse=window.matchMedia?window.matchMedia('(pointer:coarse)'):null;
 var orientation=window.matchMedia?window.matchMedia('(orientation: landscape)'):null;
 var observed=false,observer=null;
 function isPhone(){
  var s=window.screen;
  var short=Math.min(Number(s&&s.width)||Infinity,Number(s&&s.height)||Infinity);
  return !!(coarse&&coarse.matches&&short<=600);
 }
 function shown(id){
  var e=document.getElementById(id);
  return !!(e&&!e.classList.contains('hidden'));
 }
 function sceneDesign(){
  if(shown('game'))return {kind:'battle',height:600,wide:false};
  if(shown('dice-channels')||shown('lobby'))
   return {kind:'genesis-404',height:440,wide:true};
  if(shown('rooms')){
   var el=document.getElementById('rooms');
   if(el.classList.contains('native-town-scene')||
      el.classList.contains('native-directory-scene')||
      el.classList.contains('native-knight-town'))
    return {kind:'chat-town-404',height:480,wide:true};
   return {kind:'chat-room-528',height:600,wide:true};
  }
  if(shown('sky'))return {kind:'world-528',height:564,wide:true};
  return {kind:'standard',height:600,wide:true};
 }
 function focusedEditor(){
  var el=document.activeElement;
  return !!(el&&(/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)||el.isContentEditable));
 }
 function measure(){
  var vv=window.visualViewport;
  var w=vv&&vv.width>0?vv.width:innerWidth;
  var h=vv&&vv.height>0?vv.height:innerHeight;
  if(!isPhone()||w<1||h<1){
   applied=null;
   root.removeAttribute('data-leaf-phone-fit');
   root.removeAttribute('data-leaf-phone-scene');
   for(var n of ['--leaf-fit-scale','--leaf-layout-width','--leaf-layout-height','--leaf-left','--leaf-top'])root.style.removeProperty(n);
   return;
  }
  // WebKit may retain a stale orientation media-query during live rotation.
  // Available viewport dimensions are authoritative, except while the
  // keyboard is shrinking a focused editor's visual viewport.
  var landscape=(focusedEditor()&&applied)?applied.landscape:(w>h);
  // Keyboard and Safari toolbar changes do not authorize zooming or cropping.
  var isKeyboard=focusedEditor()&&applied&&applied.landscape===landscape&&
   h<applied.deviceHeight*.78;
  if(isKeyboard)h=applied.deviceHeight;
  var scene=sceneDesign();
  var targetH=landscape?scene.height:600;
  var scale=Math.min((w-4)/800,(h-4)/targetH);
  scale=Math.min(1.5,Math.max(.1,scale));
  scale=Number(scale.toFixed(6));
  // Fill wide phones with original MainFrame chrome, but keep the unmodified
  // source scene (794px art) centred. Never stretch/crop its native image.
  var virtualW=(landscape&&scene.wide)?
   Math.max(800,Math.floor((w-4)/scale)):800;
  root.style.setProperty('--leaf-fit-scale',String(scale));
  root.style.setProperty('--leaf-layout-width',virtualW+'px');
  root.style.setProperty('--leaf-layout-height',targetH+'px');
  root.style.setProperty('--leaf-left','calc(50% - '+(virtualW/2)+'px)');
  root.style.setProperty('--leaf-top','calc(50% - '+(targetH/2)+'px)');
  root.setAttribute('data-leaf-phone-fit',landscape?'landscape':'portrait');
  root.setAttribute('data-leaf-phone-scene',scene.kind);
  applied={landscape:landscape,kind:scene.kind,layoutWidth:virtualW,
   layoutHeight:targetH,sourceWidth:800,sourceHeight:scene.height,
   deviceWidth:+w.toFixed(2),deviceHeight:+h.toFixed(2),scale:scale,
   method:'per-scene-native-contain'};
 }
 function schedule(){
  if(scheduled)return;
  scheduled=true;
  requestAnimationFrame(function(){scheduled=false;measure()});
 }
 function start(){
  if(observed)return;
  observed=true;
  var app=document.getElementById('app');
  var targets=['sky','dice-channels','lobby','rooms','game','shop'];
  if('MutationObserver' in window){
   observer=new MutationObserver(schedule);
   if(app)observer.observe(app,{attributes:true,attributeFilter:['class']});
   targets.forEach(function(id){
    var el=document.getElementById(id);
    if(el)observer.observe(el,{attributes:true,attributeFilter:['class']});
   });
  }
  // Do not invent a global floating chat button. Original room chat is
  // integrated inside the 794x528 ChatRoom scene and is already usable on
  // mobile. The detached blue button previously covered the original
  // MainFrame icons and Genesis 'back' control on every landscape screen.
  if(!document.getElementById('leaf-phone-rotate')){
   var rotate=document.createElement('div');
   rotate.id='leaf-phone-rotate';rotate.setAttribute('role','status');
   rotate.textContent='↻ 휴대폰을 가로로 돌려 주세요';
   document.body.append(rotate);
  }
  schedule();
 }
 measure();
 window.addEventListener('resize',schedule,{passive:true});
 window.addEventListener('orientationchange',schedule,{passive:true});
 window.addEventListener('pageshow',schedule,{passive:true});
 window.addEventListener('leaf-route-change',schedule);
 document.addEventListener('focusin',schedule);
 document.addEventListener('focusout',schedule);
 if(window.screen&&screen.orientation&&screen.orientation.addEventListener)
  screen.orientation.addEventListener('change',schedule);
 if(window.visualViewport){
  visualViewport.addEventListener('resize',schedule,{passive:true});
  visualViewport.addEventListener('scroll',schedule,{passive:true});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
 else start();
 window.__LEAF_PHONE_FIT__={
  getState:function(){return applied?Object.assign({},applied):null},
  refresh:measure
 };
})();
