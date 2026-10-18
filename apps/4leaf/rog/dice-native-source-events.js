/* The SHA-verified 2002 original Dice/IMG.pak WIN scenes (source sprites).
 * winAbility.spr: 330x284 + 5 independent 41x29 light tokens.
 * winJail.spr: 136x219 original JAIL cage.
 * This is live DOM, not a screenshot of a completed game. Browser placement
 * of the source parts is INFERRED from the archived signed SPR origins;
 * do not certify it as the historical 3D MVE camera/motion.
 */
(function(){
 'use strict';
 const SOURCE='./original/SourceSPRExtra/';
 const originTokens=[
  [-130,81],[-100,120],[-19,134],[61,120],[91,81]
 ];
 const definitions={
  jail:{source:'winJail.spr',name:'winJail',width:136,height:219,frames:1},
  ability:{source:'winAbility.spr',name:'winAbility',width:330,height:284,frames:6}
 };
 let last=null,deadline=0;
 function show(kind,playerName=''){
  const data=definitions[kind],game=document.getElementById('game'),
   area=document.getElementById('board-area');
  if(!data||!game||!area||game.classList.contains('hidden'))return false;
  area.querySelector('#leaf-source-effect-overlay')?.remove();
  const wrap=document.createElement('div');
  wrap.id='leaf-source-effect-overlay';
  wrap.className='leaf-source-effect '+kind;
  wrap.dataset.originalMember='Dice/IMG.pak:'+data.source;
  wrap.dataset.originalFrame='0';
  wrap.dataset.sourceKind=kind;
  wrap.dataset.nativeSourceReady='loading';
  wrap.dataset.sourceLayout='inferred-signed-SPR-origin/browser-not-3D';
  wrap.dataset.playerName=String(playerName);
  wrap.setAttribute('role','img');
  wrap.setAttribute('aria-label',(kind==='jail'?'감옥':'어빌리티')+
   ' · '+String(playerName)+' · 원본 2002년 SPR 스프라이트');
  const primary=document.createElement('img');
  primary.className='leaf-source-event-primary';
  primary.alt='';primary.draggable=false;
  primary.dataset.originalFrame='0';
  primary.addEventListener('load',()=>{
   if(!wrap.isConnected)return;
   wrap.dataset.nativeSourceReady=primary.naturalWidth===data.width&&
    primary.naturalHeight===data.height?'ready':'fallback';
  });
  primary.addEventListener('error',()=>{
   if(wrap.isConnected)wrap.dataset.nativeSourceReady='fallback';
  });
  wrap.append(primary);
  if(kind==='ability'){
   for(let index=0;index<5;index++){
    const [x,y]=originTokens[index],item=document.createElement('img');
    item.className='leaf-source-ability-token';
    item.dataset.originalFrame=String(index+1);
    item.dataset.sourceOffset=String(x)+','+String(y);
    // The IMG sprite metadata contains signed origins around a common
    // 0,0. Anchor from source-frame-0 (-165,-206) to keep the native
    // sub-pieces in the correct relative SOURCE (not guessed CSS) pixels.
    item.style.left=(x+165)+'px';
    item.style.top=(y+206)+'px';
    item.alt='';item.draggable=false;
    item.src=SOURCE+'winAbility-'+String(index+1).padStart(2,'0')+'.png';
    wrap.append(item);
   }
  }
  area.append(wrap);
  primary.src=SOURCE+data.name+'-00.png';
  last={kind,playerName,source:data.source,frameCount:data.frames};
  const current=++deadline;
  setTimeout(()=>{
   if(current===deadline&&wrap.isConnected)wrap.remove();
  },2300);
  return true;
 }
 function getState(){
  const node=document.getElementById('leaf-source-effect-overlay');
  const image=node?.querySelector('.leaf-source-event-primary');
  return {last,active:!!node,kind:node?.dataset.sourceKind||null,
   originalMember:node?.dataset.originalMember||null,
   ready:node?.dataset.nativeSourceReady||null,
   size:image?[image.naturalWidth,image.naturalHeight]:null,
   tokenCount:node?.querySelectorAll('.leaf-source-ability-token').length||0,
   layout:node?.dataset.sourceLayout||null};
 }
 window.__LEAF_NATIVE_EVENTS__={show,getState};
})();
