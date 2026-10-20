/* 4LEAF Genesis Dice: genuine DMP/TIS terrain cell exploration.
 * This does NOT invent lost MVE height, rotation or 3D mesh data.
 * All positions/types/warp indices come from recovered original/maps.js,
 * original/tiles.js and 145×97 original TIS sprite elements already
 * rendered by game.js. Clicking an actual cell changes VIEW only,
 * never a real match position, move, ability, turn or history entry.
 * Historical client tile-inspection chrome is unverified: this is clearly
 * an optional accessible web interaction, not a fake original modal. */
(function(){
 'use strict';
 const $=id=>document.getElementById(id);
 const data={selected:null,map:null,lastFocused:null};
 const names={start:'시작',goal:'도착',normal:'일반',warp:'워프',
  keeper:'키퍼',arena:'전투',chest:'보물',curse:'저주',blessing:'축복',
  prison:'감옥',ability:'어빌리티',ability100:'어빌리티 100',
  boost:'이동 보너스',boost4:'이동 보너스 4',clover:'클로버',
  spade:'스페이드',doa:'운명',joker:'조커',random:'랜덤',
  attribute:'속성'};
 function sourceMatch(){
  const match=window.__ROG_TEST__?.getMatch?.();
  if(!match||$('game')?.classList.contains('hidden'))return null;
  const record=Object.entries(window.ORIGINAL_LEAF_MAP_INFO||{})
   .find(([id,value])=>value.title===match.map&&window.ORIGINAL_LEAF_MAPS?.[id]);
  if(!record)return null;
  const id=record[0],cells=window.ORIGINAL_LEAF_MAPS[id];
  const events=window.ORIGINAL_LEAF_TILES?.[id]||[];
  return {match,id,cells,events};
 }
 function tileAt(index){return $('board-nodes')?.querySelector('.tile[data-tile="'+index+'"]')||null}
 function get(index){
  const m=sourceMatch();index=Number(index);
  if(!m||!Number.isInteger(index)||index<0||index>=m.cells.length)return null;
  const source=m.cells[index],paint=tileAt(index);
  if(!paint)return null;
  const event=m.events[index]||{type:m.match.tiles[index]||'normal'};
  const jump=source[3]===10&&Number.isInteger(source[5])&&
   source[5]>=0&&source[5]<m.cells.length&&source[5]!==index?source[5]:null;
  return {index,map:m.match.map,mapId:m.id,coord:[source[0],source[1]],
   sourceCode:source[2],event:event.type,attribute:event.attribute||null,
   warpGroup:event.warpGroup||null,warpTo:jump,
   sourceArt:paint.dataset.originalArt||null,
   real:paint.dataset.nativeTisSize==='145x97'};
 }
 function label(c){
  const attr=c.attribute?' · '+c.attribute:'';
  return (c.index+1)+'번 발판 · '+(names[c.event]||c.event)+attr;
 }
 function refreshLabels(){
  const state=sourceMatch(),root=$('board-nodes');
  if(!root||!state)return;
  if(data.map!==state.match.map){data.map=state.match.map;data.selected=null}
  for(const tile of root.querySelectorAll('.tile[data-tile]')){
   const index=Number(tile.dataset.tile);
   if(!Number.isInteger(index)||!state.cells[index])continue;
   const cell=get(index);if(!cell)continue;
   tile.tabIndex=0;tile.setAttribute('role','button');
   tile.dataset.dmpFocusable='true';
   tile.setAttribute('aria-label',label(cell)+' · 원본 DMP '+cell.coord.join(',')+
    (cell.warpTo!==null?' · 원본 워프 '+(cell.warpTo+1)+'번 연결':'')+
    ' · Enter 또는 클릭하여 카메라로 살펴보기');
   tile.setAttribute('aria-keyshortcuts','Enter Space');
   tile.setAttribute('aria-pressed',String(data.selected===index));
  }
 }
 function panel(){
  let p=$('dice-source-dmp-inspector');if(p)return p;
  const area=$('board-area');if(!area)return null;
  p=document.createElement('section');
  p.id='dice-source-dmp-inspector';
  p.className='dice-source-dmp-inspector';
  p.dataset.reconstruction='web-inspector';
  p.setAttribute('aria-label','원본 DMP 발판 정보 · 웹 복원 탐색 도구');
  p.hidden=true;
  const heading=document.createElement('div');heading.className='dmp-inspector-title';
  const body=document.createElement('div');body.className='dmp-inspector-detail';
  const actions=document.createElement('div');actions.className='dmp-inspector-actions';
  const destination=document.createElement('button');destination.type='button';
  destination.className='dmp-inspector-warp';destination.textContent='워프 연결 보기';
  destination.addEventListener('click',()=>{
   const source=get(data.selected);
   if(source?.warpTo!==null)focus(source.warpTo,{notify:true});
  });
  const close=document.createElement('button');close.type='button';
  close.className='dmp-inspector-close';close.textContent='닫기';
  close.setAttribute('aria-label','원본 발판 정보 닫기');
  close.addEventListener('click',()=>{
   p.hidden=true;const previous=tileAt(data.selected);
   data.selected=null;refreshLabels();previous?.focus({preventScroll:true});
  });
  actions.append(destination,close);p.append(heading,body,actions);area.append(p);
  return p;
 }
 function focus(index,{notify=true}={}){
  const c=get(index),tile=tileAt(index),p=panel();
  if(!c||!tile||!p)return null;
  data.selected=index;data.lastFocused=c.map;
  refreshLabels();
  if(notify){
   const ratio=[parseFloat(tile.style.left)/100,parseFloat(tile.style.top)/100];
   if(ratio.every(Number.isFinite)){
    // This invokes the same fully clamped DMP camera as the genuine source
    // minimap. Never modify player positions or inject extra game packets.
    if(window.__LEAF_MINIMAP_NAV__?.focus)
     window.__LEAF_MINIMAP_NAV__.focus(...ratio);
    else window.__LEAF_CAMERA__?.focusRatio(...ratio);
   }
  }
  p.querySelector('.dmp-inspector-title').textContent=label(c);
  p.querySelector('.dmp-inspector-detail').textContent=
   '원본 DMP ('+c.coord.join(', ')+') · TIS '+c.sourceArt+
   (c.warpTo!==null?' · '+(c.warpTo+1)+'번 연결':'');
  const warp=p.querySelector('.dmp-inspector-warp');
  warp.hidden=c.warpTo===null;
  if(c.warpTo!==null)
   warp.setAttribute('aria-label','원본 DMP '+(c.warpTo+1)+'번 워프 목적지 카메라로 살펴보기');
  p.hidden=false;p.dataset.index=String(index);p.dataset.sourceMap=c.mapId;
  p.dataset.sourceArt=c.sourceArt;p.dataset.warpTarget=c.warpTo===null?'':String(c.warpTo);
  return c;
 }
 function closeForMatchChange(){
  const p=$('dice-source-dmp-inspector');
  if(p){p.hidden=true;p.dataset.index='';}
  data.selected=null;data.map=null;
 }
 function install(){
  const root=$('board-nodes');if(!root||root.dataset.dmpExplorerAttached)return;
  root.dataset.dmpExplorerAttached='true';
  const observer=new MutationObserver(()=>{if(sourceMatch())refreshLabels();else closeForMatchChange()});
  observer.observe(root,{childList:true,subtree:false});
  root.addEventListener('click',event=>{
   const tile=event.target.closest('.tile[data-tile]');
   if(!tile||!root.contains(tile))return;
   // The underlying game tile rejects source-transparent 2002 TIS pixels,
   // but this independent inspector listens on the ancestor and previously
   // re-opened a tile panel even when the source-pixel hit was rejected.
   // Apply the SAME original 145x97 alpha test to the bubbled physical
   // click. Keyboard .click()/Enter has detail=0 and remains accessible.
   if(event.detail>0&&Number.isFinite(event.clientX)&&Number.isFinite(event.clientY)){
    const native=window.__LEAF_TIS_ALPHA__?.hitPoint(tile,event.clientX,event.clientY);
    if(native?.ready&&!native.hit)return;
   }
   focus(Number(tile.dataset.tile));
  });
  root.addEventListener('keydown',event=>{
   const tile=event.target.closest('.tile[data-tile]');
   if(!tile||!root.contains(tile)||!['Enter',' ','Spacebar'].includes(event.key))return;
   event.preventDefault();event.stopPropagation();
   focus(Number(tile.dataset.tile));
  });
  $('board-area')?.addEventListener('keydown',event=>{
   if(event.key==='Escape'&&!$('dice-source-dmp-inspector')?.hidden){
    const p=$('dice-source-dmp-inspector');if(!p)return;
    p.hidden=true;const previous=tileAt(data.selected);
    data.selected=null;refreshLabels();previous?.focus({preventScroll:true});
    event.stopPropagation();
   }
  });
  refreshLabels();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);
 else install();
 window.__LEAF_DMP_EXPLORER__={get,focus,getState:()=>({
  selected:data.selected,map:data.map,panel:!$('dice-source-dmp-inspector')?.hidden,
  verified:'DMP x/y/cell, TIS source, warp destination; no MVE elevation'
 }),refresh:refreshLabels};
})();