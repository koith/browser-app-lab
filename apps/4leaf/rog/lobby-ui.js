'use strict';
(function(){
 const $=id=>document.getElementById(id);
 const choices=[
  {key:'ai',name:'컴퓨터 대전',people:'1 ~ 8',map:'4LEAF',style:'일반',detail:'컴퓨터 캐릭터와 1인용 주사위 게임을 시작합니다.'},
  {key:'hotseat',name:'같은 기기 대전',people:'2 ~ 8',map:'워프 게이트',style:'로컬',detail:'하나의 모바일 기기에서 번갈아 턴을 진행합니다.'},
  {key:'network',name:'직접 연결 대전',people:'2',map:'4LEAF',style:'WebRTC',detail:'서로 다른 두 기기의 브라우저를 직접 연결하는 게임입니다.'}
 ];
 let chosen=0;
 function updateRooms(){
  const root=$('lobby-room-list'),info=$('lobby-room-info');if(!root||!info)return;
  root.replaceChildren();
  choices.forEach((item,i)=>{
    const b=document.createElement('button');b.className='lobby-room-row'+(i===chosen?' selected':'');
    b.innerHTML='<span class="lobby-room-id">0'+(i+1)+'</span><span class="lobby-room-key"></span><span class="lobby-room-size"></span><span class="lobby-room-title"></span>';
    b.querySelector('.lobby-room-key').textContent='♣';
    b.querySelector('.lobby-room-size').textContent=item.people;
    b.querySelector('.lobby-room-title').textContent=item.name;
    b.title=item.detail;
    b.onclick=()=>{chosen=i;updateRooms()};
    b.ondblclick=openCreator;
    root.append(b);
  });
  const selected=choices[chosen];
  info.replaceChildren();
  for(const [label,value] of [['방제',selected.name],['방장','내 기기'],['인원',selected.people],['MAP',selected.map],['소환수치','설정 가능'],['스타일',selected.style],['공개여부',selected.key==='network'?'직접 연결':'로컬']]){
    const line=document.createElement('div');const title=document.createElement('b');title.textContent=label;const val=document.createElement('span');val.textContent=value;line.append(title,val);info.append(line);
  }
 }
 function openCreator(){
  const scene=$('dice-lobby-scene');if(!scene)return;
  scene.classList.add('config-open');
  $('dice-room-config').classList.remove('hidden');
  $('lobby-config-back').classList.remove('hidden');
  const mode=$('game-mode');mode.value=choices[chosen].key;mode.dispatchEvent(new Event('change'));
  if(choices[chosen].key==='network')$('bot-count').value='1';
  if(!$('map-select').value||$('map-select').selectedIndex<0)$('map-select').selectedIndex=0;
  $('lobby-create').blur();
  // Lobby configuration is a real room-creation form; source sprite backdrops
  // remain static but roster slots and game actions are dynamic.
  renderPlayerSeats();
 }
 function closeCreator(){
  $('dice-lobby-scene').classList.remove('config-open');
  $('dice-room-config').classList.add('hidden');
  $('lobby-config-back').classList.add('hidden');
 }
 function renderPlayerSeats(){
  const panel=$('dice-room-config');if(!panel)return;
  let seats=$('lobby-players');
  if(!seats){seats=document.createElement('div');seats.id='lobby-players';seats.className='lobby-players';panel.append(seats)}
  seats.replaceChildren();
  const count=Math.max(1,Math.min(7,Number($('bot-count').value)||1));
  for(let i=0;i<8;i++){
    const p=document.createElement('div');p.className='lobby-seat'+(i>count?' empty':'');
    const num=document.createElement('span');num.textContent=(i+1)+'P';
    const name=document.createElement('b');
    name.textContent=i===0?$('profile-name').textContent:(i<=count?($('game-mode').value==='ai'?'COM '+i:'플레이어 '+(i+1)):'');
    p.append(num,name);seats.append(p);
  }
 }
 function init(){
  if(!$('lobby-room-list'))return;
  updateRooms();
  $('lobby-create').onclick=openCreator;
  $('lobby-join').onclick=openCreator;
  $('lobby-config-back').onclick=closeCreator;
  for(const tab of document.querySelectorAll('[data-route="lobby"]'))tab.addEventListener('click',closeCreator);
  $('bot-count').addEventListener('change',renderPlayerSeats);
  $('game-mode').addEventListener('change',renderPlayerSeats);
  // The original ROOM SELECT has interactive source-built components.
  window.__LEAF_LOBBY__={openCreator,closeCreator,updateRooms};
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
 else init();
})();