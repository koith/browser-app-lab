'use strict';
/* Reconstructed Genesis World room selector. A list of three playable MODES is
   not three original multiplayer ROOMS: list only actual unfinished matches.
   The archived d1lobby/d1waitroom screens remain interactive backgrounds.
   The static site cannot discover a historical 4LEAF central game server. */
(function(){
 const $=id=>document.getElementById(id);
 const modes={
  ai:{label:'컴퓨터 대전',description:'내 기기에서 컴퓨터 상대와 경기합니다.'},
  hotseat:{label:'같은 기기 대전',description:'한 화면에서 참가자들이 번갈아 경기합니다.'},
  network:{label:'직접 연결 대전',description:'WebRTC로 연결한 두 브라우저 간 경기입니다.'}
 };
 let creatorOpen=false;
 const getMatch=()=>window.__ROG_TEST__?.getMatch?.()||null;
 const playable=()=>{const m=getMatch();return m&&!m.finished&&Array.isArray(m.players)&&m.players.length>1?m:null};
 function line(container,label,value){
  const row=document.createElement('div'),heading=document.createElement('b'),text=document.createElement('span');
  heading.textContent=label;text.textContent=String(value);row.append(heading,text);container.append(row);
 }
 function updateRooms(){
  const root=$('lobby-room-list'),info=$('lobby-room-info');if(!root||!info)return;
  root.replaceChildren();info.replaceChildren();
  const match=playable();
  if(match){
   const row=document.createElement('button');
   row.type='button';row.className='lobby-room-row selected';row.dataset.match='saved';
   row.setAttribute('aria-label','진행 중인 경기 '+match.map+' 계속하기');
   const number=document.createElement('span');number.className='lobby-room-id';number.textContent='01';
   const key=document.createElement('span');key.className='lobby-room-key';key.textContent='♣';
   const count=document.createElement('span');count.className='lobby-room-size';count.textContent=String(match.players.length)+'/8';
   const title=document.createElement('span');title.className='lobby-room-title';title.textContent=match.map+' · '+(modes[match.mode]?.label||'저장된 경기');
   row.append(number,key,count,title);row.onclick=resumeMatch;root.append(row);
   line(info,'방제',match.map);
   line(info,'방장',match.players[0]?.name||'Guest');
   line(info,'인원',match.players.length+'명');
   line(info,'MAP',match.map);
   line(info,'진행',Math.max(1,Number(match.round)||1)+'턴');
   line(info,'방식',modes[match.mode]?.label||match.mode);
   line(info,'상태',match.mode==='network'?'연결 확인 필요':'내 기기 저장됨');
   $('lobby-join')?.removeAttribute('aria-disabled');
  }else{
   const empty=document.createElement('div');empty.className='lobby-room-empty';
   const label=document.createElement('b');label.textContent='현재 입장 가능한 게임방이 없습니다.';
   const hint=document.createElement('small');hint.textContent='방 만들기로 새 경기를 시작하세요. 다른 이용자의 방을 찾으려면 별도의 로비 서버가 필요합니다.';
   empty.append(label,hint);root.append(empty);
   for(const [k,v] of [['방제','—'],['방장','—'],['인원','0명'],['MAP','—'],['소환수치','설정 전'],['방식','방 만들기에서 선택'],['상태','실제 서버 방 없음']])line(info,k,v);
   $('lobby-join')?.setAttribute('aria-disabled','true');
  }
 }
 function inform(title,text){
  const modal=$('modal');if(!modal)return;
  $('modal-title').textContent=title;
  $('modal-content').textContent=text;
  const buttons=$('modal-buttons');buttons.replaceChildren();
  const ok=document.createElement('button');ok.textContent='확인';ok.className='primary';
  ok.onclick=()=>modal.classList.add('hidden');buttons.append(ok);
  modal.classList.remove('hidden');
 }
 function resumeMatch(){
  const match=playable();
  if(!match){
   inform('주사위의 잔영 · 방 입장','현재 실제로 개설되어 입장할 수 있는 경기방이 없습니다. 방 만들기에서 새 경기를 시작하세요.');
   return;
  }
  if(match.mode==='network'&&!window.__LEAF_NET__?.connected){
   inform('직접 연결이 필요합니다','저장된 온라인 경기는 WebRTC 상대와 다시 연결해야 합니다. 먼저 방 만들기에서 직접 연결 모드를 설정해 주세요.');
   return;
  }
  closeCreator();
  window.__ROG_TEST__?.go('game');
 }
 function openCreator(){
  const scene=$('dice-lobby-scene');if(!scene)return;
  creatorOpen=true;
  scene.classList.add('config-open');
  $('dice-room-config').classList.remove('hidden');
  $('lobby-config-back').classList.remove('hidden');
  // The original game-mode select is a configuration, not a fake room list.
  const mode=$('game-mode');
  if(!modes[mode.value])mode.value='ai';
  mode.dispatchEvent(new Event('change'));
  if(mode.value==='network')$('bot-count').value='1';
  if(!$('map-select').value||$('map-select').selectedIndex<0)$('map-select').selectedIndex=0;
  $('lobby-create').blur();
  renderPlayerSeats();
 }
 function closeCreator(){
  creatorOpen=false;
  $('dice-lobby-scene')?.classList.remove('config-open');
  $('dice-room-config')?.classList.add('hidden');
  $('lobby-config-back')?.classList.add('hidden');
  updateRooms();
 }
 function renderPlayerSeats(){
  const panel=$('dice-room-config');if(!panel)return;
  let seats=$('lobby-players');
  if(!seats){seats=document.createElement('div');seats.id='lobby-players';seats.className='lobby-players';panel.append(seats)}
  seats.replaceChildren();
  const mode=$('game-mode').value;
  const count=mode==='network'?1:Math.max(1,Math.min(7,Number($('bot-count').value)||1));
  for(let i=0;i<8;i++){
   const seat=document.createElement('div');seat.className='lobby-seat'+(i>count?' empty':'');
   const number=document.createElement('span');number.textContent=(i+1)+'P';
   const name=document.createElement('b');name.textContent=i===0?$('profile-name').textContent:(i<=count?(mode==='ai'?'COM '+i:mode==='network'?'직접 연결 상대':'플레이어 '+(i+1)):'');
   seat.append(number,name);seats.append(seat);
  }
 }
 function init(){
  if(!$('lobby-room-list'))return;
  updateRooms();
  $('lobby-create').onclick=openCreator;
  $('lobby-join').onclick=resumeMatch;
  $('lobby-config-back').onclick=closeCreator;
  for(const tab of document.querySelectorAll('[data-route="lobby"]'))tab.addEventListener('click',closeCreator);
  $('bot-count').addEventListener('change',renderPlayerSeats);
  $('game-mode').addEventListener('change',renderPlayerSeats);
  window.addEventListener('leaf-route-change',event=>{
   if(event.detail?.route==='lobby'){closeCreator();updateRooms()}
  });
  window.addEventListener('storage',event=>{if(event.key==='rog_match'&&!creatorOpen)updateRooms()});
  window.__LEAF_LOBBY__={openCreator,closeCreator,updateRooms,resumeMatch,getState:()=>({open:creatorOpen,saved:!!playable(),rooms:playable()?1:0})};
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
 else init();
})();
