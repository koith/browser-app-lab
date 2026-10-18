'use strict';
// Recompose original Dice IMG sprites as separate functioning panels.
// Unlike a screenshot overlay, the minimap is the SAME game-updated canvas:
// reparenting keeps its backing pixels, while the chat retains real DOM text,
// editable input and the existing send handler.
(function(){
 const $=id=>document.getElementById(id);
 const WIDTH=800,HEIGHT=600,CONTENT=608,CHAT={width:406,height:152},MINI={width:172,height:152};
 let dock=null,observer=null;
 function sync(){
  const app=$('app'),main=$('main'),map=$('board-mini'),area=$('board-area');
  if(!app||!main||!map||!area)return;
  if(!dock){
   dock=document.createElement('div');
   dock.id='dice-native-minidock';
   dock.className='dice-native-minidock';
   dock.setAttribute('aria-hidden','true');
   main.append(dock);
  }
  // A tiny mobile viewport cannot fit two original pixel-size panels side by
  // side; preserve the actual minimap over the board rather than crop it.
  const canDock=app.classList.contains('app-classic-dice')&&
   main.clientWidth>=594&&window.matchMedia('(min-width:651px)').matches;
  if(canDock){
   if(map.parentElement!==dock)dock.append(map);
  }else if(map.parentElement!==area){
   area.append(map);
  }
  dock.hidden=!canDock;
  // The 2002 mini-panel now contains two genuine keyboard-operable source
  // tabs. A visible dock must NOT retain aria-hidden=true from its previous
  // decorative-only incarnation.
  dock.setAttribute('aria-hidden',String(!canDock));
  dock.dataset.active=String(canDock);
 }
 function init(){
  const main=$('main');if(!main)return;
  if('ResizeObserver' in window){
   observer=new ResizeObserver(sync);
   observer.observe(main);
  }
  window.addEventListener('leaf-route-change',sync);
  window.addEventListener('resize',sync,{passive:true});
  sync();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
 else init();
 window.__LEAF_DICE_FRAME__={
  sync,
  getState:()=>({
   logicalWidth:WIDTH,logicalHeight:HEIGHT,
   mainSourceWidth:CONTENT,
   chatSourceWidth:CHAT.width,chatSourceHeight:CHAT.height,
   minimapSourceWidth:MINI.width,minimapSourceHeight:MINI.height,
   docked:dock?.dataset.active==='true',
   chatWidth:document.querySelector('#app.app-classic-dice .messenger')?.getBoundingClientRect().width||0,
   minimapParent:$('board-mini')?.parentElement?.id||null
  })
 };
})();