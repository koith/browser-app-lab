'use strict';
/* 2002-04 REAL Room/roomback.png (794x404), CHESSMAN INFO area:
 * top eight 22px owned rows, bottom four 22px selected-party slots.
 * Draw live card labels/data INTO the original empty source cells.
 * Do not paste a JPEG screenshot, invent cards, or show a covering web panel.
 * The old engine team modal is still available for accessibility fallback.
 */
(function(){
 const $=id=>document.getElementById(id);
 const stage=$('dice-native-stage'),wrap=$('dice-lobby-scene');
 const api=()=>window.__LEAF_DICE_ROSTER__;
 if(!stage||!wrap)return;
 const owned=document.createElement('section');
 owned.id='dice-native-owned-chessmen';
 owned.className='dice-native-chessman-table dice-native-owned-chessmen';
 owned.setAttribute('aria-label','원본 CHESSMAN INFO · 보유 체스맨');
 const party=document.createElement('section');
 party.id='dice-native-selected-chessmen';
 party.className='dice-native-chessman-table dice-native-selected-chessmen';
 party.setAttribute('aria-label','원본 CHESSMAN INFO · 선택한 체스맨 네 칸');
 const prev=document.createElement('button'),next=document.createElement('button');
 prev.id='dice-native-chessman-prev';next.id='dice-native-chessman-next';
 prev.className=next.className='dice-native-chessman-scroll';
 prev.type=next.type='button';
 prev.setAttribute('aria-label','보유 체스맨 이전 페이지');
 next.setAttribute('aria-label','보유 체스맨 다음 페이지');
 prev.title='보유 체스맨 이전 8장';next.title='보유 체스맨 다음 8장';
 stage.append(owned,party,prev,next);
 const names=['공격','방어','지력','대기'];
 let selectedSlot=0,page=0;
 function element(tag,cls,text){
  const node=document.createElement(tag);
  node.className=cls;node.textContent=String(text??'');return node;
 }
 function row(card,slot,top,type){
  const button=document.createElement('button');
  button.type='button';
  button.className='dice-native-chessman-row '+type;
  button.style.top=top+'px';
  button.dataset.cardId=card?.id||'';
  if(type==='party'){
   button.dataset.slot=String(slot);
   button.classList.toggle('selected-slot',slot===selectedSlot);
   button.setAttribute('aria-pressed',String(slot===selectedSlot));
   button.setAttribute('aria-label',(slot+1)+'번째 원본 원정대 칸 ('+names[slot]+') · '+(card?.name||'빈 칸')+' 선택');
   button.title=(slot+1)+'P '+names[slot]+' · '+(card?.name||'비어 있음')+' — 클릭한 다음 위 보유 체스맨 선택';
   button.onclick=()=>{selectedSlot=slot;render();};
  }else{
   const assigned=api()?.getState().team.indexOf(card?.id)??-1;
   button.dataset.equipped=String(assigned>=0);
   button.setAttribute('aria-label',card?.name+' · '+card?.point+' 소환 · '+card?.ability+
     (assigned>=0?' · '+names[assigned]+' 슬롯에 배치됨':' · 선택 슬롯에 배치'));
   button.title=card?.name+' · 이동 '+card?.move+' 공격 '+card?.atk+
     ' 방어 '+card?.def+' 지력 '+card?.int+' · 클릭하여 '+names[selectedSlot]+'에 장착';
   button.onclick=()=>{
    const live=api()?.getState();
    if(!live)return;
    const already=live.team.indexOf(card.id);
    if(already>=0){selectedSlot=already;render();return;}
    const result=api()?.equip(selectedSlot,card.id);
    if(result)render();
   };
  }
  button.append(
   element('span','dice-native-chessman-name',card?.name||''),
   element('span','dice-native-chessman-points',card?.point??''),
   element('span','dice-native-chessman-ability',card?.ability||'')
  );
  const scores=[card?.move,card?.atk,card?.def,card?.int,null,null];
  for(let i=0;i<6;i++)button.append(element('span','dice-native-chessman-stat dice-stat-'+i,
   Number.isFinite(scores[i])?scores[i]:''));
  return button;
 }
 function render(){
  const source=api()?.getState();
  if(!source)return;
  const all=source.owned||[];
  page=Math.min(page,Math.max(0,Math.ceil(all.length/8)-1));
  owned.replaceChildren();party.replaceChildren();
  for(let i=0;i<8;i++){
   const card=all[page*8+i];
   if(card)owned.append(row(card,i,i*22,'owned'));
  }
  for(let slot=0;slot<4;slot++){
   const id=source.team[slot];
   party.append(row(all.find(c=>c.id===id)||null,slot,slot*22,'party'));
  }
  prev.disabled=page===0;next.disabled=page>=Math.ceil(all.length/8)-1;
  prev.hidden=next.hidden=all.length<=8;
  stage.dataset.nativeChessmenRows=String(owned.children.length);
  stage.dataset.nativeChessmenSelected=String(source.team.filter(Boolean).length);
  stage.dataset.nativeChessmenSource='Room/roomback.png';
  stage.dataset.nativeChessmenActiveSlot=String(selectedSlot);
 }
 prev.onclick=()=>{page=Math.max(0,page-1);render()};
 next.onclick=()=>{page++;render()};
 owned.addEventListener('wheel',event=>{
  const length=api()?.getState().owned.length||0;
  if(length<=8)return;
  const nextPage=Math.max(0,Math.min(Math.ceil(length/8)-1,page+Math.sign(event.deltaY)));
  if(nextPage!==page){event.preventDefault();page=nextPage;render();}
 },{passive:false});
 // Source blue SELECT at x560..628 y232 is a control for the original
 // table, not a trigger for an invented giant HTML inventory overlay.
 const picker=$('dice-team-picker');
 if(picker)picker.onclick=()=>{
  if(!wrap.classList.contains('config-open'))return;
  stage.classList.remove('team-picker-open');
  picker.setAttribute('aria-expanded','true');
  owned.querySelector('button')?.focus();
 };
 owned.addEventListener('focusout',()=>{
  if(!owned.contains(document.activeElement))
   picker?.setAttribute('aria-expanded','false');
 });
 // Escape returns keyboard focus to the source SELECT sprite without
 // hiding the original chessman table or opening a web-only modal.
 owned.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  event.preventDefault();event.stopPropagation();
  picker?.setAttribute('aria-expanded','false');
  picker?.focus();
 });
 window.addEventListener('leaf-dice-roster-change',render);
 window.addEventListener('leaf-route-change',event=>{
  if(event.detail?.route==='lobby')render();
 });
 $('point-limit')?.addEventListener('change',render);
 new MutationObserver(changes=>{
  if(changes.some(change=>change.attributeName==='class'))render();
 }).observe(wrap,{attributes:true,attributeFilter:['class']});
 window.__LEAF_NATIVE_CHESSMAN_TABLE__={
  getState:()=>({
   source:'Room/roomback.png',inventoryRows:owned.children.length,
   selectedRows:party.children.length,activeSlot:selectedSlot,
   selected:api()?.getState().team||[],page,
   cards:api()?.getState().owned.length||0
  })
 };
 render();
})();
