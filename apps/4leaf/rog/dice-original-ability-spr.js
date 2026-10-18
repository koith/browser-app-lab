/* ORIGINAL ARCHIVE 2002 Dice/IMG.pak winAbility.spr native 6 frames.
 * Original 640-byte palette RLE, 100% unscaled source PNG pixels.
 * The base 330x284 stage + 5 genuine 41x29 button sprites retain
 * ARCHIVED originX/originY offsets, NOT made-up x/y positions.
 * Runtime display lifespan is a WEB inference; historical MVE/EXE time
 * sequence has NOT been reverse-engineered.
 * Never blocks interactive gameplay or replaces any live game state.
 */
(function(){
 'use strict';
 const members=[
  {index:0,file:'winAbility-00.png',w:330,h:284,x:-165,y:-206},
  {index:1,file:'winAbility-01.png',w:41,h:29,x:-130,y:81},
  {index:2,file:'winAbility-02.png',w:41,h:29,x:-100,y:120},
  {index:3,file:'winAbility-03.png',w:41,h:29,x:-19,y:134},
  {index:4,file:'winAbility-04.png',w:41,h:29,x:61,y:120},
  {index:5,file:'winAbility-05.png',w:41,h:29,x:91,y:81}
 ];
 const url=m=>'./original/SourceSPRExtra/'+m.file;
 let current=null,seq=0;
 function remove(){
  if(current){current.remove();current=null}
 }
 function show(playerName,abilityName){
  const area=document.getElementById('board-area');
  if(!area||document.getElementById('game')?.classList.contains('hidden'))return null;
  remove();seq++;
  const serial=seq;
  const panel=document.createElement('div');
  panel.id='leaf-original-ability-stage';
  panel.className='leaf-original-ability-stage';
  panel.dataset.sourceMember='Dice/IMG.pak:winAbility.spr';
  panel.dataset.nativeFrameCount=String(members.length);
  panel.dataset.status='loading';
  panel.dataset.placement='archive-origin-delta-web-lifetime-inferred';
  panel.setAttribute('role','img');
  panel.setAttribute('aria-label','원본 4LEAF 어빌리티 · '+
   String(playerName||'')+' · '+String(abilityName||''));
  panel.setAttribute('aria-live','off');
  const base=members[0];
  let n=0,invalid=false;
  const imgs=[];
  for(const m of members){
   const img=document.createElement('img');
   img.src=url(m);img.width=m.w;img.height=m.h;img.alt='';
   img.draggable=false;img.dataset.sourceFrame=String(m.index);
   img.dataset.originalSourceMember='Dice/IMG.pak:winAbility.spr';
   img.style.left=(m.x-base.x)+'px';
   img.style.top=(m.y-base.y)+'px';
   img.className='leaf-source-ability-frame'+(m.index?' leaf-source-ability-glyph':' leaf-source-ability-base');
   const check=()=>{
    if(!panel.isConnected||seq!==serial)return;
    if(img.naturalWidth!==m.w||img.naturalHeight!==m.h){
     invalid=true;panel.dataset.status='fallback';
     panel.dataset.error='native source image size mismatch';return;
    }
    n++;
    if(n===members.length&&!invalid)panel.dataset.status='ready';
   };
   img.addEventListener('load',check);
   img.addEventListener('error',()=>{
    if(panel.isConnected&&seq===serial){
     invalid=true;panel.dataset.status='fallback';
     panel.dataset.error='original source image missing';
    }
   });
   imgs.push(img);
   panel.append(img);
  }
  area.append(panel);current=panel;
  // Effect lifetime is a clearly labeled inferred WEB duration (1.6s).
  // Genuine source art/offsets are not substitutes for missing MVE timing.
  window.setTimeout(()=>{if(seq===serial)remove()},1600);
  return panel;
 }
 window.__LEAF_ORIGINAL_ABILITY__={
  show,remove,source:'Dice/IMG.pak:winAbility.spr',
  members:members.map(m=>({...m,url:url(m)})),
  getState:()=>({present:!!current?.isConnected,
   status:current?.dataset.status||'absent',count:current?.querySelectorAll('img').length||0,
   originalSourceRecovered:true,historicalTimingRecovered:false})
 };
})();
