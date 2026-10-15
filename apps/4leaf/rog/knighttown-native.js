'use strict';
/* 4LEAF original KnightTown/knightback.png is an independent 794x404
 * RECORDABLE REGION SELECT, not a ChatTown area and definitely not the
 * Genesis Dice Map/ROOM SELECT. Its six signs also have independently
 * recovered 568x74 atlas (4 states x 142px) source art.
 *
 * Room/board contents of each area are NOT part of these bitmaps. The
 * clicked area currently links into the existing functional web bulletin,
 * explicitly a reconstruction rather than an invented original server. */
(function(){
 const AREAS=Object.freeze([
  {id:'sea01',name:'모험의 바다',asset:'sea01',hit:[76,80,181,108],sprite:[90,96]},
  {id:'plain01',name:'패왕의 대지',asset:'plain01',hit:[317,112,181,108],sprite:[333,127]},
  {id:'snow01',name:'침묵의 설원',asset:'snow01',hit:[543,83,201,112],sprite:[566,99]},
  {id:'sea02',name:'도전의 바다',asset:'sea02',hit:[54,225,181,115],sprite:[72,248]},
  {id:'sea03',name:'찬란한 바다',asset:'sea03',hit:[288,263,183,108],sprite:[307,284]},
  {id:'plain02',name:'영광의 대지',asset:'plain02',hit:[475,246,215,108],sprite:[501,264]}
 ]);
 const SRC='KnightTown/knightback.png';
 function render(frame,onChoose){
  if(!frame||typeof onChoose!=='function')return;
  frame.className='social-image-frame social-knight-town';
  frame.dataset.source=SRC;
  frame.style.backgroundImage='url("./original/'+SRC+'")';
  frame.setAttribute('aria-label','원본 레코르다블 기사단 지역 선택');
  frame.replaceChildren();
  for(const area of AREAS){
   const button=document.createElement('button');
   button.type='button';button.className='knight-district-hotspot';
   button.dataset.knightArea=area.id;button.dataset.source='KnightTown/'+area.asset+'.png';
   button.dataset.nativeBounds=area.hit.join(',');
   button.dataset.nativeSprite=area.sprite.join(',');
   button.setAttribute('aria-label',area.name+' 지역에 입장');
   button.title=area.name;
   const [x,y,w,h]=area.hit;
   button.style.left=x+'px';button.style.top=y+'px';
   button.style.width=w+'px';button.style.height=h+'px';
   const sprite=document.createElement('span');
   sprite.className='knight-source-hover';
   sprite.setAttribute('aria-hidden','true');
   sprite.style.left=(area.sprite[0]-x)+'px';
   sprite.style.top=(area.sprite[1]-y)+'px';
   sprite.style.backgroundImage='url("./original/KnightTown/'+area.asset+'.png")';
   button.append(sprite);
   button.addEventListener('click',()=>onChoose({...area}));
   frame.append(button);
  }
 }
 window.__LEAF_KNIGHT_TOWN__={
  render,
  getState:()=>({source:SRC,logicalSize:[794,404],
   areas:AREAS.map(a=>({id:a.id,name:a.name,asset:a.asset,hit:[...a.hit],sprite:[...a.sprite]}))})
 };
})();
