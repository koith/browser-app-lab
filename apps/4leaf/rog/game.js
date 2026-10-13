'use strict';
(function(){
const $=id=>document.getElementById(id);
const query=(s,parent=document)=>Array.from(parent.querySelectorAll(s));
const routeNames={sky:'아노마라드 상공',city:'켈티카의 거리',rooms:'하이아칸 타운',lobby:'주사위의 잔영 대기실',shop:'매직카덴',game:'창세기월드 · 주사위의 잔영','help-screen':'4LEAF 도움말'};
const BASE_CARDS=[
{id:'soldier',name:'솔져',move:1,atk:2,def:2,int:1,point:2,price:180,rank:'normal',portrait:'♟',ability:'방어C'},
{id:'joan',name:'죠안',move:1,atk:3,def:2,int:2,point:3,price:250,rank:'normal',portrait:'♙',ability:'공격C'},
{id:'rashid',name:'라시드',move:2,atk:2,def:2,int:1,point:3,price:350,rank:'normal',portrait:'♘',ability:'이동C'},
{id:'narcia',name:'나르샤',move:1,atk:2,def:2,int:3,point:3,price:390,rank:'normal',portrait:'♗',ability:'지력C'},
{id:'merza',name:'마르자나',move:1,atk:3,def:2,int:2,point:3,price:450,rank:'normal',portrait:'♙',ability:'공격B'},
{id:'iolyn',name:'이올린',move:1,atk:3,def:3,int:2,point:4,price:750,rank:'normal',portrait:'♕',ability:'방어B'},
{id:'christian',name:'크리스티앙',move:2,atk:3,def:3,int:2,point:6,price:2200,rank:'valuable',portrait:'♝',ability:'프리워프'},
{id:'saladin',name:'살라딘',move:1,atk:4,def:4,int:2,point:6,price:5800,rank:'valuable',portrait:'♜',ability:'순간이동'},
{id:'damian',name:'데미안',move:2,atk:2,def:4,int:3,point:6,price:5400,rank:'valuable',portrait:'♞',ability:'블럭'},
{id:'sherazard',name:'셰라자드',move:2,atk:1,def:2,int:5,point:6,price:6300,rank:'valuable',portrait:'♛',ability:'팀 지력+'},
{id:'ironmask',name:'철가면',move:1,atk:4,def:4,int:2,point:7,price:7000,rank:'valuable',portrait:'♚',ability:'디스트로이'},
{id:'schwarz',name:'흑태자',move:2,atk:5,def:3,int:2,point:8,price:26000,rank:'valuable',portrait:'♚',ability:'공격A'}
];
const CHR_SOURCE=window.ORIGINAL_LEAF_CHESSMEN||[];
const ABILITY_NAMES={19:'공격C',20:'공격B',21:'공격A',22:'방어C',23:'방어B',24:'이동B',25:'방어B',26:'지력B',27:'지력A',28:'능력 없음',30:'순간이동',31:'팀 지력+',32:'키퍼',33:'프리워프',34:'디스트로이',37:'이동C',38:'공격C',39:'공격B',43:'블럭',56:'흑태자의 힘'};
const LEGACY_IDS={soldier:'c_0096',joan:'c_0078',rashid:'c_0087',narcia:'c_0088',merza:'c_0040',iolyn:'c_0045',christian:'c_0090',saladin:'c_0087',damian:'c_0127',sherazard:'c_0088',ironmask:'c_0091',schwarz:'c_0170'};
const STARTERS=['c_0096','c_0078','c_0040','c_0045'];
const HIGH_PRICES={'살라딘':47000,'셰라자드':46500,'살라딘2':51500,'데미안':49500,'철가면':31000,'흑태자':60000,'크리스티앙':39000};
if(CHR_SOURCE.length>50){
 const originalCards=CHR_SOURCE
 .filter(c=>c.move>=1&&c.move<=2&&c.atk>=1&&c.def>=1&&!['마장기 test','근육이'].includes(c.name))
 .filter(c=>!['근육이','마장기 test','노동자스켈톤'].includes(c.name))
 .map(c=>({id:'c_'+c.id,sourceId:c.id,name:c.name,move:c.move,atk:c.atk,def:c.def,int:c.int,point:Math.max(1,Math.ceil((c.atk+c.def+c.int+c.move)/3)),rank:c.score>=175?'valuable':'normal',price:HIGH_PRICES[c.name]||Math.max(160,Math.round(c.score*18/10)*10),ability:ABILITY_NAMES[c.abilityId]||'능력 '+c.abilityId,abilityId:c.abilityId,element:['Wands','Swords','Cups','Disks','None'][c.element]||'None',score:c.score,portrait:'♟'}));
 BASE_CARDS.splice(0,BASE_CARDS.length,...originalCards);
}
const CARD_MAP=Object.fromEntries(BASE_CARDS.map(c=>[c.id,c]));
const DEFAULT_PROFILE={name:'Guest',gp:3000,wins:0,owned:CHR_SOURCE.length>50?STARTERS.slice():['soldier','joan','rashid','narcia'],team:CHR_SOURCE.length>50?['c_0078','c_0096','c_0040']:['joan','soldier','narcia']};
const ITEMS=[
{id:'valkyrie',name:'발키리의 창',icon:'⚔',hint:'전투 시 상대 주사위 수의 절반만큼 주사위 추가',sourceId:'0008',battle:true},
{id:'ring',name:'지혜의 반지',icon:'◉',hint:'해당 게임 종료까지 파티 능력 +1',sourceId:'0009'},
{id:'bomb',name:'자폭',icon:'☠',hint:'대전 중 패배를 무효화하고 서로 START 복귀',sourceId:'0010',battle:true},
{id:'wing',name:'날개',icon:'✧',hint:'선택한 1~12칸 전진',sourceId:'0011'},
{id:'step',name:'4칸 전후진',icon:'↔',hint:'선택한 1~4칸 전·후진',sourceId:'0012'},
{id:'flipper',name:'오리발',icon:'♧',hint:'대전 중 패배를 무효화',sourceId:'0013',battle:true},
{id:'charge',name:'어빌리티 50',icon:'✦',hint:'능력 게이지 +50%',sourceId:'0014'},
{id:'charge25',name:'어빌리티 25',icon:'✦',hint:'능력 게이지 +25%',sourceId:'0015'},
{id:'armageddon',name:'아마겟돈',icon:'✹',hint:'모든 체스맨 공격·방어·이동 능력 일시 반감',sourceId:'0016'},
{id:'dove',name:'비둘기',icon:'✧',hint:'5턴 다른 유저와 전투 면역',sourceId:'0017'},
{id:'change',name:'체인지',icon:'⟳',hint:'대전 중 공격·방어 결과 교환',sourceId:'0026',battle:true},
{id:'oddcurse',name:'홀수 저주',icon:'Ⅰ',hint:'전투 중 상대 값이 홀수면 마지막 주사위 제거',sourceId:'0028',battle:true},
{id:'evencurse',name:'짝수 저주',icon:'Ⅱ',hint:'전투 중 상대 값이 짝수면 마지막 주사위 제거',sourceId:'0029',battle:true},
{id:'curse',name:'저주',icon:'♠',hint:'원하는 앞쪽 발판을 저주로 변경',sourceId:'0030'},
{id:'kingbomb',name:'왕폭탄',icon:'✹',hint:'앞쪽 발판에 폭탄 설치',sourceId:'0031'},
{id:'odincurse',name:'오딘의 저주',icon:'☠',hint:'미발매 원작 기획 카드 · 경기 획득 불가',sourceId:'0032',disabled:true},
{id:'keeperA',name:'키퍼 A',icon:'♙',hint:'앞쪽 발판에 강력한 키퍼 소환',sourceId:'0033'},
{id:'keeperB',name:'키퍼 B',icon:'♜',hint:'앞쪽 발판에 중간 키퍼 소환',sourceId:'0034'},
{id:'keeperC',name:'키퍼 C',icon:'♛',hint:'앞쪽 발판에 약한 키퍼 소환',sourceId:'0035'},
{id:'drain25',name:'어빌리티 25 감소',icon:'−',hint:'상대 어빌리티 -25%',sourceId:'0038'},
{id:'drain50',name:'어빌리티 50 감소',icon:'−',hint:'상대 어빌리티 -50%',sourceId:'0039'},
{id:'shoe',name:'여신의 신발',icon:'♘',hint:'3턴 이동 주사위 1개 추가',sourceId:'0040'}
];
const ITEM_MAP=Object.fromEntries(ITEMS.map(i=>[i.id,i]));
const SOURCE_ROUTES=window.ORIGINAL_LEAF_MAPS||{},SOURCE_INFO=window.ORIGINAL_LEAF_MAP_INFO||{},SOURCE_TILES=window.ORIGINAL_LEAF_TILES||{};
const SOURCE_IDS=Object.fromEntries(Object.entries(SOURCE_INFO).map(([id,info])=>[info.title,id]));
const MAPS={
'4LEAF':{length:70,non:false,warp:[11,38],keepers:[13,29,47,61],jail:[24],chests:[6,32,52],boost:[17,49],attribute:[20,43],joker:[36]},
'워프게이트':{length:70,non:false,warp:[8,19,30,41,52,63],keepers:[24,45,58],jail:[34],chests:[13,37],boost:[17,56],attribute:[28],joker:[48]},
'PK':{length:70,non:false,warp:[17,53],keepers:[11,26,43,59],jail:[33],chests:[15,46],boost:[9,35],attribute:[25,50],joker:[56]},
'Stadium':{length:62,non:true,warp:[19,45],keepers:[14,27,46],jail:[33],chests:[7,23,42],boost:[15,37],attribute:[28,53],joker:[51]},
'악마의 달팽이':{length:76,non:true,warp:[20,57],keepers:[14,32,49,66],jail:[26,55],chests:[7,38,60],boost:[18,41],attribute:[28,53],joker:[47]}
};
const BOT_NAMES=['티치엘','막시민','보리스','루시안','이스핀','시벨린','루시아'];
const COLORS=['#fff3bf','#91f2d1','#ffb4c4','#abc3ff','#e9b8fb','#ffda80','#ff9bab','#d9efff'];
const PAWNS=['♞','♜','♛','♝','♟','♙','♕','♗'];
const PORTRAITS={soldier:12,joan:119,rashid:56,narcia:41,merza:45,iolyn:54,christian:25,saladin:31,damian:101,sherazard:33,ironmask:11,schwarz:22};
const SOURCE_PORTRAITS={'0096':12,'0078':48,'0040':33,'0045':8,'0087':31,'0088':33,'0090':23,'0091':11,'0127':40,'0137':31,'0170':22};
const imageFor=(id)=>'./original/CardData/chm_'+(SOURCE_PORTRAITS[(CARD_MAP[id]||{}).sourceId]||PORTRAITS[id]||((Number((CARD_MAP[id]||{}).sourceId)||40)%59+1))+'.png';
const townAvatar=(i)=>'./original/Registry/sava'+String([0,82,6,1,85][i%5]).padStart(2,'0')+'.png';
let remoteAct=false,remoteBattle=null,remoteBattleSequence=0;
let shopPage=0;
let profile,match=null,route='sky',chosenCard=CHR_SOURCE.length>50?'c_0040':'joan',group='all',currentRoom='샤이닝 브리즈',soundOn=false,audioCtx=null,busy=false,bgm=null,bgmTrack=null;
const safe=(v,f)=>{try{const a=JSON.parse(localStorage.getItem('rog_'+v));return a===null?f:a}catch{return f}};
profile=safe('profile',DEFAULT_PROFILE);
if(!profile||!Array.isArray(profile.owned))profile=structuredClone(DEFAULT_PROFILE);
if(CHR_SOURCE.length>50){
 profile.owned=[...new Set(profile.owned.map(id=>LEGACY_IDS[id]||id).filter(id=>CARD_MAP[id]))];
 if(!profile.owned.length)profile.owned=STARTERS.slice();
 profile.team=(profile.team||[]).map(id=>LEGACY_IDS[id]||id).filter(id=>CARD_MAP[id]).slice(0,4);
 if(!profile.team.length)profile.team=DEFAULT_PROFILE.team.slice();
 if(!CARD_MAP[chosenCard])chosenCard=profile.owned[0];
}
const savedMatch=safe('match',null);if(savedMatch&&Array.isArray(savedMatch.players)&&savedMatch.players.length>=2&&savedMatch.players.length<=8&&!savedMatch.finished)match=savedMatch;
function activePlayer(){return match?.players?.[match.active]||null}
function playerCanAct(){
 if(!(match&&!match.finished&&!busy&&activePlayer()&&!activePlayer().bot))return false;
 if(match.mode==='network'&&!remoteAct){
   const net=window.__LEAF_NET__;
   return !!(net?.connected&&match.active===(net.role==='host'?0:1));
 }
 return true;
}
function refreshResume(){if(!$('resume-game'))return;$('resume-game').classList.toggle('hidden',!(match&&!match.finished&&MAPS[match.map]))}
function persist(){
 try{localStorage.setItem('rog_profile',JSON.stringify(profile));localStorage.setItem('rog_match',JSON.stringify(match))}catch{}
 if(match?.mode==='network'&&window.__LEAF_NET__?.connected&&window.__LEAF_NET__.role==='host'){
   window.__LEAF_BRIDGE__?.onState?.(match);
 }
}
function log(text){$('status').textContent=text}
function d(sides=6){return 1+Math.floor(Math.random()*sides)}
function rand(a){return Math.floor(Math.random()*a)}
function diceN(n,sides){let values=[];for(let k=0;k<n;k++)values.push(d(sides));return {values,total:values.reduce((a,b)=>a+b,0)}}
function syncMusic(){if(!soundOn){if(bgm)bgm.pause();return}const track=({sky:'00',city:'01',rooms:'02',lobby:'03',shop:'04',game:'05','help-screen':'06'})[route]||'00';if(bgm&&bgmTrack===track){bgm.play().catch(()=>{});return}if(bgm)bgm.pause();bgm=new Audio('./music/'+track+'.mp3');bgm.loop=true;bgm.volume=.28;bgmTrack=track;bgm.play().catch(()=>{})}
function sfx(freq=500,duration=.07){if(!soundOn)return;try{const AC=window.AudioContext||window.webkitAudioContext;audioCtx=audioCtx||new AC();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='triangle';o.frequency.value=freq;g.gain.setValueAtTime(.038,audioCtx.currentTime);g.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+duration);o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+duration)}catch{}}
function chat(who,message,type=''){const line=document.createElement('div');line.className=type;const b=document.createElement('b');b.textContent=who+'　';line.append(b,document.createTextNode(String(message)));$('chat-log').append(line);while($('chat-log').children.length>90)$('chat-log').firstElementChild.remove();$('chat-log').scrollTop=$('chat-log').scrollHeight}
function profileUI(){$('nick').textContent=profile.name;$('profile-name').textContent=profile.name;$('my-name').textContent=profile.name;$('gp').textContent=profile.gp.toLocaleString();$('shop-gp').textContent=profile.gp.toLocaleString();$('wins').textContent=profile.wins+'승';persist()}
function navigate(id){if(!routeNames[id])return;route=id;document.getElementById('app')?.classList.toggle('app-classic-dice',id==='game');$('app').classList.toggle('app-game',id==='game');query('.scene').forEach(s=>s.classList.toggle('hidden',s.id!==id));query('[data-route]').forEach(el=>el.classList.toggle('active',el.dataset.route===id));$('where').textContent=routeNames[id];$('chat-location').textContent=routeNames[id];if(id==='game'&&match){drawGame();const p=activePlayer();if(p?.bot&&!busy)setTimeout(()=>{if(route==='game'&&match&&!match.finished&&activePlayer()?.bot&&!busy)takeTurn()},500)}if(id==='shop')drawShop();if(id==='lobby'){drawTeam();refreshResume()}log(routeNames[id]+'에 입장하였습니다.');syncMusic();sfx(610)}
function modal(title,body,buttons){$('modal-title').textContent=title;$('modal-content').replaceChildren();if(typeof body==='string'){$('modal-content').textContent=body}else if(body)$('modal-content').append(body);$('modal-buttons').replaceChildren();buttons.forEach(opt=>{const b=document.createElement('button');b.textContent=opt.label;b.className=opt.primary?'primary':'';b.onclick=()=>{$('modal').classList.add('hidden');if(opt.run)opt.run()};$('modal-buttons').append(b)});$('modal').classList.remove('hidden')}
function ask(title,body,options){return new Promise(resolve=>modal(title,body,options.map((a,i)=>({label:a,primary:i===0,run:()=>resolve(i)}))))}
function toast(message){log(message);$('move-log').textContent=message}
function rosterByIds(ids){return (ids||[]).map(id=>CARD_MAP[id]).filter(Boolean).slice(0,4)}
function teamStats(ids){
 const cards=(ids||[]).slice(0,4).map(id=>CARD_MAP[id]||null),field=cards.slice(0,3).filter(Boolean);
 const attack=cards[0]||BASE_CARDS[0],defend=cards[1]||attack,assist=cards[2]||null;
 const same=field.length>0&&field.every(c=>c.move===field[0].move);
 return {move:same?field[0].move:1,atk:attack.atk,def:defend.def,int:assist?assist.int:0,
 point:cards.reduce((sum,c)=>sum+(c?.point||0),0),ability:attack.ability,abilityId:attack.abilityId,portrait:attack.portrait,name:attack.name};
}
function ownedCards(){return profile.owned.filter(x=>CARD_MAP[x])}
function drawTeam(){
 const root=$('team-select');root.replaceChildren();
 const slots=['공격','방어','지력','보유(4번째)'];
 for(let slot=0;slot<4;slot++){
  const b=document.createElement('button');b.className='team-slot';
  const id=profile.team[slot],c=CARD_MAP[id];
  b.innerHTML='<b>'+slots[slot]+'</b><small>'+(c?c.name:'비어 있음')+'</small><small>'+(c?('M'+c.move+' A'+c.atk+' D'+c.def+' I'+c.int):'—')+'</small>';
  b.title=slot===3?'최대 네 장까지 원정대에 소지할 수 있습니다. 네 번째 체스맨은 대기입니다.':'전투와 이동을 담당하는 체스맨을 배치합니다.';
  b.onclick=()=>{
    const div=document.createElement('div'),label=document.createElement('p');
    label.textContent=slots[slot]+' 체스맨 선택 · 원본 주잔은 네 장을 준비하고 세 명까지 팀으로 업을 수 있습니다.';div.append(label);
    const select=document.createElement('select');
    if(slot>0){const blank=document.createElement('option');blank.value='';blank.textContent='비워두기';select.append(blank)}
    ownedCards().filter(x=>!profile.team.includes(x)||profile.team[slot]===x).forEach(id=>{
      const c=CARD_MAP[id],option=document.createElement('option');option.value=id;
      option.textContent=c.name+' / '+c.point+'pt / 이동'+c.move;
      if(profile.team[slot]===id)option.selected=true;select.append(option);
    });
    div.append(select);
    modal('체스맨 원정대',div,[{label:'선택',primary:true,run:()=>{
      const chosen=select.value;
      profile.team[slot]=chosen;
      if(slot===3&&!chosen)profile.team.splice(3,1);
      persist();drawTeam();
    }},{label:'취소'}]);
  };
  root.append(b);
 }
 const stats=teamStats(profile.team),limit=Number($('point-limit').value);
 const info=document.createElement('div');info.className='fine';
 info.textContent='파티 '+profile.team.filter(Boolean).length+' / 4명 · '+stats.point+' / '+limit+' POINT · 이동 '+stats.move+' / 공격 '+stats.atk+' / 방어 '+stats.def+' / 지력 '+stats.int;
 root.append(info);
 const label=document.createElement('div');label.className='fine';
 label.textContent='첫 3명: 실제 공격·방어·지력 팀 / 4번째: 출전 대기 체스맨';
 root.append(label);
}
function shopFiltered(){
 return BASE_CARDS.filter(c=>group==='all'||c.rank===group||(group==='valuable'&&c.rank==='rare'));
}
function selectShopCard(id){
 if(!CARD_MAP[id])return;
 chosenCard=id;
 const cards=shopFiltered(),index=cards.findIndex(c=>c.id===id);
 if(index>=0)shopPage=Math.floor(index/9);
 drawShop();
}
function drawShop(){
 const root=$('shop-grid'),cards=shopFiltered(),pages=Math.max(1,Math.ceil(cards.length/9));
 shopPage=Math.max(0,Math.min(pages-1,shopPage));
 if(!cards.slice(shopPage*9,shopPage*9+9).some(c=>c.id===chosenCard)&&cards.length)chosenCard=cards[shopPage*9].id;
 root.replaceChildren();
 for(let i=0;i<9;i++){
   const c=cards[shopPage*9+i],b=document.createElement('button');
   if(!c){
     b.className='shop-card shop-empty';b.disabled=true;b.setAttribute('aria-hidden','true');
     root.append(b);continue;
   }
   b.className='shop-card'+(chosenCard===c.id?' selected':'');
   b.title=c.name+' · '+c.ability+' · '+c.price.toLocaleString()+'GP · '+(profile.owned.includes(c.id)?'보유':'미보유');
   const art=document.createElement('div');art.className='card-art';
   const img=document.createElement('img');img.className='pixel-portrait';img.alt=c.name;img.src=imageFor(c.id);art.append(img);
   const name=document.createElement('b');name.textContent=c.name;
   const state=document.createElement('span');state.className='card-state';state.textContent=profile.owned.includes(c.id)?'OWN':'NEW';
   b.append(art,name,state);
   b.onclick=()=>selectShopCard(c.id);
   root.append(b);
 }
 $('shop-page').textContent=(shopPage+1)+' / '+pages;
 $('shop-prev').disabled=shopPage===0;$('shop-next').disabled=shopPage>=pages-1;
 query('.group-tab').forEach(b=>b.classList.toggle('selected',b.dataset.group===group));
 const owned=$('shop-owned-list');owned.replaceChildren();
 profile.owned.filter(id=>CARD_MAP[id]).forEach(id=>{
   const c=CARD_MAP[id],b=document.createElement('button');b.className='shop-owned-entry';
   b.textContent='♧ '+c.name+'　'+c.ability;b.title=c.name+' ('+c.point+'pt)';
   if(chosenCard===c.id)b.classList.add('selected');
   b.onclick=()=>{if(!shopFiltered().find(x=>x.id===id))group='all';selectShopCard(id)};
   owned.append(b);
 });
 const c=CARD_MAP[chosenCard]||cards[0]||BASE_CARDS[0];
 if(c){
   $('shop-selected').textContent=c.name+' · '+c.ability+' · '+c.element+' / 이동'+c.move+'　공격'+c.atk+'　방어'+c.def+'　지력'+c.int+'　POINT '+c.point+' / '+c.price.toLocaleString()+' GP';
   $('shop-buy').disabled=profile.owned.includes(c.id)||profile.gp<c.price;
   $('shop-buy').textContent=profile.owned.includes(c.id)?'보유중':(profile.gp<c.price?'GP 부족':'구입하기');
 }
 profileUI();
}
function buildRoomList(){const list=$('room-list');list.replaceChildren();['샤이닝 브리즈','실버 호라이즌','윈트리 아이스','헤이즐리 웨이브','엘핀 포레스트'].forEach((r,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+r+'　('+(['평원','설원','빙원','해양','숲'][i])+')';b.className=r===currentRoom?'selected':'';b.onclick=()=>{currentRoom=r;const roomScene=document.querySelector('#rooms .room-floor');if(roomScene)roomScene.style.backgroundImage='url("./original/ChatRoom/room'+Math.min(i,5)+'.png")';buildRoomList();$('room-title').textContent='하이아칸 · '+r;chat('SYSTEM',r+' 방에 입장했습니다. 다른 이용자와는 연결되지 않습니다.','system')};list.append(b)});$('room-title').textContent='하이아칸 · '+currentRoom}
function buildPeople(){const root=$('town-figures');root.replaceChildren();const roster=[profile.name,'티치엘','막시민','루시안','이스핀'];roster.forEach((name,i)=>{const b=document.createElement('button');b.className='avatar';b.style.setProperty('--hair',['#5f4e70','#c6b26a','#362a5e','#dcc17e','#ce8b7a'][i]);b.style.setProperty('--outfit',['#7d68b7','#649ac4','#5d638f','#ac735c','#aa798e'][i]);b.style.backgroundImage='url("'+townAvatar(i)+'")';b.innerHTML='<i class="avatar-head"></i><i class="avatar-body"></i><small></small>';b.querySelector('small').textContent=name;b.onclick=()=>chat(name,i===0?'오늘도 좋은 하루네요!':'반가워요, '+profile.name+'님.','npc');root.append(b)})}
function originalTileAt(map,index){
 const id=SOURCE_IDS[map];return SOURCE_TILES[id]?.[index]||null;
}
function generateTiles(map){
 const config=MAPS[map],source=SOURCE_TILES[SOURCE_IDS[map]];
 if(source?.length===config.length)return source.map(entry=>entry.type);
 // Historical map file absent: create a playable but visibly labeled fallback only.
 const sourceRoute=SOURCE_ROUTES[SOURCE_IDS[map]],types=[];
 for(let i=0;i<config.length;i++){
   const entry=sourceRoute?.[i];
   let type=(i===0?'start':i===config.length-1?'goal':'normal');
   if(entry?.[3]===10&&entry[5]<config.length&&entry[5]!==i)type='warp';
   types.push(type);
 }
 return types;
}
function pathCoords(){let pts=[],left=0,right=13,top=0,bottom=7;while(left<=right&&top<=bottom){for(let x=left;x<=right;x++)pts.push([x,top]);for(let y=top+1;y<=bottom;y++)pts.push([right,y]);if(top<bottom)for(let x=right-1;x>=left;x--)pts.push([x,bottom]);if(left<right)for(let y=bottom-1;y>top;y--)pts.push([left,y]);left+=1;right-=1;top+=1;bottom-=1}return pts.map(([x,y])=>({x:5.5+x*(89/13),y:8.5+y*(83/7)}))}
let PATH=pathCoords();
function chooseSourcePath(map){const records=SOURCE_ROUTES[SOURCE_IDS[map]];if(!records||records.length<8){PATH=pathCoords();return}const xs=records.map(p=>p[0]),ys=records.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);PATH=records.map(p=>({x:8+(p[0]-xmin)*84/Math.max(1,xmax-xmin),y:8+(p[1]-ymin)*84/Math.max(1,ymax-ymin)}))}
function installAuthenticMaps(){const list=$('map-select'),entries=Object.entries(SOURCE_INFO).filter(([id])=>SOURCE_ROUTES[id]&&SOURCE_ROUTES[id].length>9);if(!entries.length)return;list.replaceChildren();const rank=['4LEAF','주사위','워프 게이트','PK','악마의 달팽이','한반도','For the Lucky'];entries.sort((a,b)=>{let i=rank.indexOf(a[1].title),j=rank.indexOf(b[1].title);return (i<0?99:i)-(j<0?99:j)});for(const [id,info] of entries){const title=info.title,length=SOURCE_ROUTES[id].length;const old=MAPS[title]||{};const generate=(step,offset)=>Array.from({length:Math.floor(length/step)},(_,i)=>offset+i*step).filter(i=>i>0&&i<length-1);MAPS[title]={length,non:['악마의 달팽이','한반도'].includes(title),warp:old.warp||generate(30,8),keepers:old.keepers||generate(17,13),jail:old.jail||generate(44,25),chests:old.chests||generate(19,6),boost:old.boost||generate(23,17),attribute:old.attribute||generate(29,20),joker:old.joker||generate(41,36)};const opt=document.createElement('option');opt.value=title;opt.textContent=title+' · '+length+'칸 [원본 '+id+(SOURCE_TILES[id]?' · 발판 복원':' · 경로 복원')+']';list.append(opt)}const randomOption=document.createElement('option');randomOption.value='__RANDOM__';randomOption.textContent='랜덤맵 · 원작 2003.02 업데이트';list.append(randomOption);list.value='4LEAF'}
function freshItems(){return Array.from({length:3},()=>{const pool=ITEMS.filter(item=>!item.disabled);return pool[rand(pool.length)].id})}
function newPlayer(id,bot,name,team){return {id,bot,name,team,position:0,jail:0,ability:0,items:freshItems(),effects:{shoe:0,dove:0,clover:0,spade:0,ring:0,armageddon:0,valkyrie:0,oddcurse:0,evencurse:0,block:0,destroy:0,keeper:0},usedItem:false,color:COLORS[id],pawn:PAWNS[id]}}
function startGame(){let map=$('map-select').value;const limit=Number($('point-limit').value),stats=teamStats(profile.team);if(map==='__RANDOM__'){const candidates=Object.keys(SOURCE_IDS).filter(name=>MAPS[name]&&SOURCE_ROUTES[SOURCE_IDS[name]]?.length>9);map=candidates[rand(candidates.length)]||'4LEAF';}chooseSourcePath(map);if(!profile.team[0])return modal('파티 구성','공격 체스맨을 선택하세요.',[{label:'확인',primary:true}]);if(stats.point>limit)return modal('소환 POINT 초과','현재 파티는 '+stats.point+'POINT이며 제한은 '+limit+'POINT입니다.',[{label:'확인',primary:true}]);const selectedMode=$('game-mode').value,hotseat=selectedMode!=='ai',bots=selectedMode==='network'?1:Number($('bot-count').value);
 if(selectedMode==='network'&&(!window.__LEAF_NET__?.connected||window.__LEAF_NET__.role!=='host')){
    return modal('온라인 대전 연결','온라인 대전에서는 먼저 상대 브라우저와 연결해야 합니다. 호스트에서 연결을 시작하세요.',[{label:'확인',primary:true}]);
 }let players=[newPlayer(0,false,profile.name,profile.team.slice())];for(let i=0;i<bots;i++){const weakTeams=CHR_SOURCE.length>50?[
 ['c_0096','c_0078','c_0040'],['c_0078','c_0045','c_0096'],['c_0040','c_0078','c_0096'],['c_0045','c_0096','c_0078'],['c_0078','c_0040','c_0045'],['c_0096','c_0045','c_0078'],['c_0040','c_0096','c_0045']]:
 [['rashid','soldier','narcia'],['joan','narcia','soldier'],['soldier','joan','rashid'],['iolyn','soldier','narcia'],['merza','rashid','soldier'],['christian','soldier','joan'],['damian','soldier','narcia']];let team=weakTeams[i].filter((_,j)=>j===0||limit>=8);while(teamStats(team).point>limit)team.pop();players.push(newPlayer(i+1,!hotseat,selectedMode==='network'?(window.__LEAF_NET__?.guestName||'플레이어 2'):(hotseat?'플레이어 '+(i+2):BOT_NAMES[i]),team))}match={version:4,map,mode:selectedMode,tiles:generateTiles(map),players,active:0,round:1,finished:false,winner:-1,attribute:'NONE',message:'주사위를 굴려 주세요.',lastRoll:[],history:[],pending:null};busy=false;persist();navigate('game');chat('SYSTEM',map+' 게임을 시작했습니다. '+(selectedMode==='network'?'두 기기 온라인 연결':hotseat?'사람 '+(bots+1)+'명이 번갈아 플레이':'컴퓨터 '+bots+'명과 대전')+'.','system');drawGame();persist()}
function tileGlyph(type){return {start:'S',goal:'G',normal:'✧',warp:'◈',keeper:'⚔',prison:'▤',chest:'▣',boost:'+3',boost4:'+4',attribute:'✥',joker:'★',random:'?',ability:'✶',ability100:'✦',clover:'♣',spade:'♠',doa:'☠',curse:'♠',blessing:'✥',arena:'⚔'}[type]||'✧'}
function appendMove(message){if(!match)return;match.message=message;match.history.push(message);if(match.history.length>90)match.history.shift();toast(message);persist()}
function drawBoard(){
 if(!match)return;
 const root=$('board-nodes'),svg=$('board-lines');
 const key=match.map+'|'+match.tiles.join(',');
 if(root.dataset.renderKey!==key){
   root.dataset.renderKey=key;root.replaceChildren();svg.replaceChildren();
   const coords=PATH.slice(0,match.tiles.length).map(p=>({x:p.x*820/100,y:p.y*355/100}));
   const path=document.createElementNS('http://www.w3.org/2000/svg','polyline');
   path.setAttribute('points',coords.map(p=>p.x+','+p.y).join(' '));
   path.setAttribute('fill','none');path.setAttribute('stroke','#b6a2d5');
   path.setAttribute('stroke-width','4');path.setAttribute('stroke-linejoin','round');path.setAttribute('opacity','.35');svg.append(path);
   const fragment=document.createDocumentFragment();
   coords.forEach((pos,i)=>{
     const type=match.tiles[i],b=document.createElement('div');b.className='tile '+type;
     b.style.left=PATH[i].x+'%';b.style.top=PATH[i].y+'%';b.dataset.tile=i;
     if(SOURCE_IDS[match.map]){
       const columns=Math.max(8,Math.sqrt(match.tiles.length)*1.6);
       b.style.width=Math.max(2.5,Math.min(5,72/columns))+'%';
       b.style.height=Math.max(4.5,Math.min(9,120/columns))+'%';
     }
     const glyph=document.createElement('span');glyph.className='tile-symbol';glyph.textContent=tileGlyph(type);
     const number=document.createElement('small');number.textContent=i+1;
     b.title=(i+1)+'칸 · '+type;b.append(glyph,number);
     b.onclick=()=>log((i+1)+'칸 · '+type+' '+match.players.filter(p=>p.position===i).map(p=>p.name).join(', '));
     fragment.append(b);
   });root.append(fragment);
 }
 const currentPositions=new Set(match.players.map(p=>p.position));
 query('.tile',root).forEach((node,i)=>node.classList.toggle('player-here',currentPositions.has(i)));
 drawPawns();
}
function drawPawns(){
 let layer=$('board-pawns');
 if(!layer){layer=document.createElement('div');layer.id='board-pawns';$('board-world').append(layer)}
 const players=match.players;
 for(const stale of query('.board-pawn',layer)){
   if(!players.some(p=>String(p.id)===stale.dataset.id))stale.remove();
 }
 for(const p of players){
   let pawn=query('.board-pawn',layer).find(node=>node.dataset.id===String(p.id));
   if(!pawn){
     pawn=document.createElement('div');pawn.className='board-pawn';pawn.dataset.id=String(p.id);
     const img=document.createElement('img');img.alt='';img.src='./original/Registry/sava'+String([0,82,6,1,85,2,84,4][p.id]||0).padStart(2,'0')+'.png';
     const name=document.createElement('span');name.className='board-pawn-name';
     pawn.append(img,name);layer.append(pawn);
   }
   const point=PATH[Math.min(p.position,PATH.length-1)]||PATH[0];
   const previous=Number(pawn.dataset.position);
   const moved=pawn.dataset.position!==undefined&&previous!==p.position;
   if(moved&&typeof pawn.animate==='function'&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
     const previousPoint=PATH[Math.min(previous,PATH.length-1)]||point;
     const dx=point.x-previousPoint.x;
     const image=pawn.querySelector('img');
     pawn._stepAnimation?.cancel?.();
     pawn._stepAnimation=image.animate([
       {transform:'translateY(0) rotate(0deg) scale(1)'},
       {transform:'translateY(-7px) rotate('+Math.max(-12,Math.min(12,dx*1.5))+'deg) scale(1.08)'},
       {transform:'translateY(-3px) rotate(0deg) scale(1.02)'},
       {transform:'translateY(0) rotate(0deg) scale(1)'}
     ],{duration:p.position<previous?420:280,easing:'ease-out'});
   }
   pawn.dataset.position=String(p.position);
   const slot=players.filter(q=>q.position===p.position).findIndex(q=>q.id===p.id);
   pawn.style.left='calc('+point.x+'% + '+((slot%4)*11-12)+'px)';
   pawn.style.top='calc('+point.y+'% - '+(Math.floor(slot/4)*14)+'px)';
   pawn.style.setProperty('--pawn-color',p.color);
   pawn.classList.toggle('pawn-current',match.active===p.id);
   pawn.querySelector('.board-pawn-name').textContent=p.name;
 }
}
function drawBattlePanels(){
 const root=$('battle-player-panels');if(!root||!match)return;
 root.replaceChildren();
 const left=document.createElement('div'),right=document.createElement('div');
 left.className='battle-team-side left';right.className='battle-team-side right';
 match.players.forEach((p,i)=>{
  const card=document.createElement('div');card.className='battle-side-card'+(match.active===i?' active':'');
  card.style.setProperty('--player-tint',p.color);
  const num=document.createElement('span');num.className='battle-side-num';num.textContent=(i+1)+'P';
  const portrait=document.createElement('img');portrait.alt='';portrait.src=imageFor(p.team[0]||'soldier');
  const info=document.createElement('div');info.className='battle-side-info';
  const nick=document.createElement('b');nick.textContent=p.name;
  const attrs=document.createElement('small');
  attrs.textContent='♣ '+(p.position+1)+'칸　'+p.ability+'%';
  const meter=document.createElement('i');meter.className='battle-side-meter';meter.style.width=Math.max(1,p.ability)+'%';
  info.append(nick,attrs,meter);card.append(num,portrait,info);
  (i%2===0?left:right).append(card);
 });
 root.append(left,right);
}
function drawMinimap(){
 const canvas=$('mini-map-canvas');if(!canvas||!match||PATH.length===0)return;
 const context=canvas.getContext('2d');if(!context)return;
 const {width:w,height:h}=canvas;context.clearRect(0,0,w,h);
 context.beginPath();
 PATH.slice(0,match.tiles.length).forEach((p,i)=>{
   const x=7+(p.x/100)*(w-14),y=10+(p.y/100)*(h-17);
   if(!i)context.moveTo(x,y);else context.lineTo(x,y);
 });
 context.strokeStyle='#b5dbf8';context.lineWidth=2;context.stroke();
 PATH.slice(0,match.tiles.length).forEach((point,i)=>{
   if(match.tiles[i]!=='warp'&&match.tiles[i]!=='goal'&&match.tiles[i]!=='start')return;
   const x=7+point.x/100*(w-14),y=10+point.y/100*(h-17);
   context.fillStyle=match.tiles[i]==='goal'?'#ffe58d':match.tiles[i]==='start'?'#86f5a2':'#68dbfa';
   context.fillRect(x-2,y-2,5,5);
 });
 match.players.forEach(p=>{
   const point=PATH[p.position]||PATH[0];if(!point)return;
   const x=7+point.x/100*(w-14),y=10+point.y/100*(h-17);
   context.beginPath();context.arc(x,y,4,0,Math.PI*2);
   context.fillStyle=p.color;context.fill();
   context.lineWidth=1;context.strokeStyle='#131c4f';context.stroke();
 });
}
function drawGame(){if(!match||!MAPS[match.map])return;chooseSourcePath(match.map);const p=(match.mode==='hotseat'||match.mode==='network'?activePlayer():match.players[0]),stats=teamStats(p.team);$('game-map-title').textContent=match.map;$('element-label').textContent=match.attribute;$('player-count').textContent=match.players.length;$('turn-indicator').textContent='ROUND '+match.round+' · '+match.players[match.active].name+' TURN';$('my-name').textContent=p.name;$('my-stats').textContent='이동 '+stats.move+' · 공격 '+stats.atk+' · 방어 '+stats.def+' · 지력 +'+stats.int;$('my-position').textContent=p.jail>0?'감옥 '+p.jail+'턴':p.position===0?'START':p.position===match.tiles.length-1?'GOAL':(p.position+1)+'번째 칸';$('my-portrait').innerHTML='<img class="player-sprite" alt="" src="'+imageFor(p.team[0]||'soldier')+'">';$('ability-fill').style.width=p.ability+'%';$('game-players').replaceChildren();match.players.forEach((user,i)=>{const li=document.createElement('div');li.className=match.active===i?'is-turn':'';li.textContent=(match.active===i?'▶ ':'　')+user.pawn+' '+user.name+' '+(user.position+1)+'칸 · '+user.ability+'%';li.style.color=user.color;$('game-players').append(li)});$('my-items').replaceChildren();p.items.forEach((itemId,i)=>{const item=ITEM_MAP[itemId],btn=document.createElement('button');btn.className='item-card';btn.innerHTML='<span class="item-icon">'+(item?.icon||'✧')+'</span>'+(item?.name||itemId);btn.title=item.hint;btn.disabled=match.finished||!playerCanAct()||p.usedItem||busy;btn.onclick=()=>useItem(i);$('my-items').append(btn)});$('roll-btn').disabled=!playerCanAct();$('ability-btn').disabled=!playerCanAct()||p.ability<100;$('move-log').textContent=match.message;drawBoard();drawBattlePanels();drawMinimap();trackActivePawn()}
const mapViewport={zoom:2.1,panX:0,panY:0,autoFollow:true};
function trackActivePawn(){
 if(!mapViewport.autoFollow||!match||!PATH.length)return;
 const area=$('board-area'),p=activePlayer(),pos=PATH[p.position];if(!pos)return;
 const w=area.clientWidth,h=area.clientHeight,z=mapViewport.zoom;
 const maxX=w*(z-1)/2,maxY=h*(z-1)/2;
 mapViewport.panX=Math.max(-maxX,Math.min(maxX,(50-pos.x)*(w*.76)*z/100));
 mapViewport.panY=Math.max(-maxY,Math.min(maxY,(50-pos.y)*h*z/100));
 applyMapViewport();
}
function applyMapViewport(){
 const world=$('board-world');if(!world)return;
 world.style.transform='translate('+mapViewport.panX+'px,'+mapViewport.panY+'px) scale('+mapViewport.zoom+')';
 const label=$('board-zoom-reset');if(label)label.title='맵 배율 '+Math.round(mapViewport.zoom*100)+'% · 중앙으로 복귀';
}
function zoomBoard(by){
 mapViewport.zoom=Math.max(1,Math.min(3.2,Math.round((mapViewport.zoom+by)*100)/100));
 if(mapViewport.zoom===1){mapViewport.panX=0;mapViewport.panY=0}
 if(mapViewport.autoFollow)trackActivePawn();else applyMapViewport();
}
function installBoardControls(){
 $('board-zoom-in').onclick=()=>zoomBoard(.25);
 $('board-zoom-out').onclick=()=>zoomBoard(-.25);
 $('board-zoom-reset').onclick=()=>{mapViewport.zoom=2.1;mapViewport.autoFollow=true;trackActivePawn()};
 const area=$('board-area');let tracking=null;
 area.addEventListener('pointerdown',e=>{
   if(e.target.closest('#board-zoom-controls')||e.button!==0)return;
   tracking={id:e.pointerId,x:e.clientX,y:e.clientY,px:mapViewport.panX,py:mapViewport.panY};
   area.setPointerCapture(e.pointerId);
 });
 area.addEventListener('pointermove',e=>{
   if(!tracking||tracking.id!==e.pointerId||mapViewport.zoom<=1)return;
   mapViewport.autoFollow=false;
   const maxX=area.clientWidth*(mapViewport.zoom-1)/2,maxY=area.clientHeight*(mapViewport.zoom-1)/2;
   mapViewport.panX=Math.max(-maxX,Math.min(maxX,tracking.px+e.clientX-tracking.x));
   mapViewport.panY=Math.max(-maxY,Math.min(maxY,tracking.py+e.clientY-tracking.y));
   applyMapViewport();
 });
 for(const kind of ['pointerup','pointercancel','lostpointercapture'])area.addEventListener(kind,()=>{tracking=null});
 area.addEventListener('wheel',e=>{
   if(!e.ctrlKey&&!e.metaKey)return;
   e.preventDefault();zoomBoard(e.deltaY<0?.2:-.2);
 },{passive:false});
 applyMapViewport();
}
function withUserTurn(){return playerCanAct()}
function useItem(index,selectedStep=null){
 if(!withUserTurn())return;
 const p=activePlayer(),itemId=p.items[index],item=ITEM_MAP[itemId];
 if(!item||p.usedItem)return;
 if(item.battle){
   modal('전투 전용 아이템',item.name+'은(는) 전투 판정 화면에서 사용할 수 있습니다.',[{label:'확인',primary:true}]);return;
 }
 const isGuest=match.mode==='network'&&window.__LEAF_NET__?.role==='guest'&&!remoteAct;
 if(remoteAct)return applyItem(index,selectedStep);
 const apply=(step)=>{
   if(isGuest){
     window.__LEAF_NET__?.send?.({type:'command',action:'item',index,steps:step});
     return;
   }
   applyItem(index,step);
 };
 if(itemId==='wing'||itemId==='step'){
   const div=document.createElement('div'),label=document.createElement('p'),field=document.createElement('input');
   label.textContent=item.name+' · '+item.hint;
   field.type='number';field.min=itemId==='wing'?'1':'-4';field.max=itemId==='wing'?'12':'4';
   field.value=itemId==='wing'?'6':'4';div.append(label,field);
   return modal('아이템 사용',div,[{
     label:'사용',primary:true,run:()=>{
       const n=Math.max(Number(field.min),Math.min(Number(field.max),Number(field.value)||0));
       if(n!==0)apply(n);
     }
   },{label:'취소'}]);
 }
 modal('아이템 · '+item.name,item.hint+' · 이번 턴에 사용하시겠습니까?',[
   {label:'사용',primary:true,run:()=>apply(null)},{label:'취소'}
 ]);
}
async function applyItem(index,steps=null){
 const p=activePlayer(),itemId=p?.items?.[index],item=ITEM_MAP[itemId];
 if(!p||!item||p.usedItem||item.battle)return;
 if(itemId==='wing'||itemId==='step'){
   const n=Math.max(itemId==='wing'?1:-4,Math.min(itemId==='wing'?12:4,Number(steps)||0));
   if(n===0)return;
   consume(index);advance(p,n);appendMove(p.name+' · '+item.name+' '+n+'칸 이동');
   if(n>0)await resolveTile(p);
   drawGame();return;
 }
 consume(index);
 if(!p.effects)p.effects={};
 switch(itemId){
 case 'shoe':p.effects.shoe=3;break;
 case 'dove':p.effects.dove=5;break;
 case 'valkyrie':p.effects.valkyrie=2;break;
 case 'ring':p.effects.ring=(p.effects.ring||0)+1;break;
 case 'armageddon':p.effects.armageddon=2;break;
 case 'charge':p.ability=Math.min(100,p.ability+50);break;
 case 'charge25':p.ability=Math.min(100,p.ability+25);break;
 case 'drain25':case 'drain50':{
   match.players.filter(q=>q!==p).forEach(other=>other.ability=Math.max(0,other.ability-(itemId==='drain25'?25:50)));break;
 }
 case 'oddcurse':case 'evencurse':match.players.filter(q=>q!==p).forEach(q=>q.effects[itemId]=1);break;
 case 'curse':match.tiles[Math.min(match.tiles.length-2,p.position+6)]='curse';break;
 case 'odincurse':match.tiles[Math.min(match.tiles.length-2,p.position+6)]='doa';break;
 case 'kingbomb':match.tiles[Math.min(match.tiles.length-2,p.position+6)]='kingbomb';break;
 case 'keeperA':case 'keeperB':case 'keeperC':
   match.tiles[Math.min(match.tiles.length-2,p.position+6)]=itemId;break;
 }
 appendMove(p.name+' · '+item.name+' 사용');drawGame();
}
function consume(index){const p=activePlayer();p.items.splice(index,1);p.usedItem=true;persist()}
function advance(user,distance){user.position=Math.min(match.tiles.length-1,Math.max(0,user.position+distance));user.ability=Math.min(100,user.ability+Math.max(0,distance)*4)}
async function useAbility(){
 if(!withUserTurn())return;
 
 const p=activePlayer(),stats=teamStats(p.team);
 if(p.ability<100)return;
 const code=stats.abilityId||0;
 const selection=remoteAct?0:await ask('어빌리티 발동',stats.name+' · '+stats.ability+' / 충전 100%',['발동','취소']);
 if(selection!==0||!withUserTurn())return;
 if(match.mode==='network'&&window.__LEAF_NET__?.role==='guest'&&!remoteAct){
   window.__LEAF_NET__?.send?.({type:'command',action:'ability'});return;
 }
 p.ability=0;
 switch(code){
 case 30:advance(p,1+rand(15));p.effects.scar=(p.effects.scar||0)+1;break;
 case 31:p.effects.teamInt=2;break;
 case 33:case 35:advance(p,1+rand(4));break;
 case 34:p.effects.destroy=2;break;
 case 43:p.effects.block=2;break;
 case 56:p.effects.ultimate=1;break;
 case 37:case 24:advance(p,3);break;
 case 23:case 25:p.effects.block=1;break;
 case 19:case 20:case 21:case 38:case 39:p.effects.valkyrie=2;break;
 case 26:case 27:p.effects.ring=2;break;
 default:p.ability=50;appendMove('이 능력은 아직 세부 효과 확인 중입니다. 절반의 게이지를 반환했습니다.');drawGame();return;
 }
 appendMove(p.name+' · '+stats.name+' 『'+stats.ability+'』 발동');
 if([30,33,35,37,24].includes(code)){p.ability=0;await resolveTile(p)}
 drawGame();persist();
}
function showBattleScene(attacker,defender,attack,defense,attackerPoints,defenderPoints){
 const area=$('board-area');if(!area)return null;
 document.querySelector('#battle-visual')?.remove();
 const stage=document.createElement('div');stage.id='battle-visual';stage.setAttribute('role','status');
 const head=document.createElement('div');head.className='battle-visual-head';head.textContent='BATTLE';
 const left=document.createElement('div'),right=document.createElement('div');
 left.className='battle-visual-side attacker';right.className='battle-visual-side defender';
 function assemble(panel,player,result,values){
   const actor=document.createElement('img');actor.className='battle-visual-actor';
   actor.src=player.id<0?'./original/Registry/sava84.png':'./original/Registry/sava'+String([0,82,6,1,85,2,84,4][player.id]||0).padStart(2,'0')+'.png';
   actor.alt=player.name;
   const title=document.createElement('strong');title.textContent=player.name;
   const score=document.createElement('div');score.className='battle-visual-total';score.textContent=String(result).padStart(2,'0');
   const dice=document.createElement('div');dice.className='battle-visual-dice';
   values.forEach(eye=>{const d=document.createElement('span');d.className='battle-visual-die';d.textContent=['⚀','⚁','⚂','⚃','⚄','⚅'][eye-1]||'⚀';dice.append(d)});
   const pedestal=document.createElement('div');pedestal.className='battle-visual-pedestal';
   panel.append(title,score,actor,pedestal,dice);
 }
 assemble(left,attacker,attackerPoints,attack.values);assemble(right,defender,defenderPoints,defense.values);
 const vs=document.createElement('div');vs.className='battle-visual-vs';vs.textContent='VS';
 stage.append(head,left,vs,right);area.append(stage);
 return stage;
}
function combat(attacker,defender,keeper=false){
 return new Promise(resolve=>{
 const aStat=teamStats(attacker.team),bStat=keeper?{def:defender.def||2,int:0}:{...teamStats(defender.team)};
 const reducedA=attacker.effects?.armageddon>0,reducedB=defender.effects?.armageddon>0;
 const isSoloA=attacker.team?.length===1,isSoloB=defender.team?.length===1;
 const isDuoA=attacker.team?.length===2,isDuoB=defender.team?.length===2;
 const aCount=Math.max(1,(reducedA?Math.max(1,Math.floor(aStat.atk/2)):aStat.atk)+(isSoloA&&attacker.effects?.ring>0?1:0));
 const bCount=Math.max(1,(reducedB?Math.max(1,Math.floor(bStat.def/2)):bStat.def)+(isDuoB&&defender.effects?.ring>0?1:0));
 let attack,defense,aValue,bValue,rerolls=0;
 for(let attempt=0;attempt<100;attempt++){
   attack=diceN(aCount,6);defense=diceN(bCount,6);
   aValue=attack.total+(aStat.int||0)+(attacker.team?.length>=3?(attacker.effects?.ring||0):0)+(attacker.effects?.teamInt>0?3:0);
   bValue=defense.total+(bStat.int||0)+(defender.team?.length>=3?(defender.effects?.ring||0):0)+(defender.effects?.teamInt>0?3:0);
   if(attacker.effects?.scar>0)aValue=Math.max(1,aValue-attacker.effects.scar);
   if(defender.effects?.scar>0)bValue=Math.max(1,bValue-defender.effects.scar);
   if(attacker.effects?.ultimate>0)aValue=30;
   if(defender.effects?.ultimate>0)bValue=18;
   if(attacker.effects?.destroy>0)aValue=24;
   if(defender.effects?.block>0)bValue=24;
   
   if(aValue!==bValue)break;rerolls++;
 }
 const div=document.createElement('div');
 div.innerHTML='<p>'+attacker.name+'의 공격! '+defender.name+'이(가) 방어합니다.'+(rerolls?' · 무승부 '+rerolls+'회 재굴림':'')+'</p><div class="battle-dice"><div>ATTACK<div class="nums">'+attack.values.join('·')+'</div><b>'+aValue+'</b><small>지력 +'+aStat.int+'</small></div><div>DEFENSE<div class="nums">'+defense.values.join('·')+'</div><b>'+bValue+'</b><small>지력 +'+bStat.int+'</small></div></div>';
 const battleStage=showBattleScene(attacker,defender,attack,defense,aValue,bValue);
 const finish=result=>{remoteBattle=null;battleStage?.remove();$('modal').classList.remove('battle-present');resolve(result)};
 const player=activePlayer();
 const selfInvolved=!keeper&&player&&!player.bot&&(attacker.id===player.id||defender.id===player.id);
 let results={attacker:aValue,defender:bValue,changed:false,negated:false};
 const options=[{label:'결과 확인',primary:true,run:()=>finish(results)}];
 if(selfInvolved&&player.items.includes('change')&&!player.usedItem){
   options.unshift({label:'체인지 카드',run:()=>{player.items.splice(player.items.indexOf('change'),1);player.usedItem=true;finish({attacker:bValue,defender:aValue,changed:true})}});
 }
 if(selfInvolved&&player.items.includes('bomb')&&!player.usedItem){options.unshift({label:'자폭',run:()=>{player.items.splice(player.items.indexOf('bomb'),1);player.usedItem=true;attacker.position=0;if(Number.isInteger(defender.position))defender.position=0;finish({...results,negated:true,mutualReset:true})}})}
 if(selfInvolved&&player.items.includes('flipper')&&!player.usedItem){
   options.unshift({label:'오리발 카드',run:()=>{player.items.splice(player.items.indexOf('flipper'),1);player.usedItem=true;finish({...results,negated:true})}});
 }

 if(selfInvolved&&!player.usedItem){
   // Original single-use battle cards are applied to the current dice roll.
   const yourAttack=attacker.id===player.id,enemyDice=yourAttack?defense:attack;
   const raw=yourAttack?aValue:bValue,opponent=yourAttack?bValue:aValue;
   function pickCard(id,modify){
     if(!player.items.includes(id))return;
     options.unshift({label:ITEM_MAP[id].name,run:()=>{
       player.items.splice(player.items.indexOf(id),1);player.usedItem=true;
       const out=modify();
       finish(out);
     }});
   }
   pickCard('valkyrie',()=>{
     const n=Math.floor(enemyDice.values.length/2);
     const extra=diceN(n,6);
     if(yourAttack)return {...results,attacker:aValue+extra.total};
     return {...results,defender:bValue+extra.total};
   });
   pickCard('oddcurse',()=>{
     const deduction=opponent%2===1?enemyDice.values[enemyDice.values.length-1]:0;
     return yourAttack?{...results,defender:bValue-deduction}:{...results,attacker:aValue-deduction};
   });
   pickCard('evencurse',()=>{
     const deduction=opponent%2===0?enemyDice.values[enemyDice.values.length-1]:0;
     return yourAttack?{...results,defender:bValue-deduction}:{...results,attacker:aValue-deduction};
   });
 }
 modal('⚔ BATTLE · 전투',div,options);$('modal').classList.add('battle-present');sfx(235,.21);
 if(match?.mode==='network'&&window.__LEAF_NET__?.connected&&player?.id===1&&!player.bot){
   const bid=++remoteBattleSequence;
   remoteBattle={bid,options:options.map(x=>x.label)};
   $('modal-title').textContent='상대 플레이어가 전투 카드를 선택하고 있습니다…';
   window.__LEAF_NET__.send({type:'battle-request',bid,attacker:attacker.name,defender:defender.name,
      attack:aValue,defense:bValue,diceAttack:attack.values,diceDefense:defense.values,
      options:remoteBattle.options});
 }
 if(!selfInvolved||(keeper&&attacker.bot)){
   setTimeout(()=>{const button=query('#modal-buttons button').find(b=>b.textContent==='결과 확인');if(!$('modal').classList.contains('hidden')&&button)button.click()},Math.max(350,keeper?600:700));
 }
 });
}

async function resolveBattle(attacker,defender,keeper){
 const result=await combat(attacker,defender,keeper);
 if(result.negated){appendMove(result.mutualReset?'자폭: 양측 START 복귀':'오리발 효과: 전투 무효화');return}
 const av=result.attacker,bv=result.defender;
 if(av===bv){appendMove('전투 판정이 무효입니다.');return}
 const loser=av>bv?defender:attacker,diff=Math.abs(av-bv);
 if(loser&&Number.isInteger(loser.position)){loser.position=diff>=7?0:Math.max(0,loser.position-diff)}
 appendMove(attacker.name+' '+av+' : '+bv+' '+defender.name+' · '+(av>bv?attacker.name:defender.name)+' 승리! '+(keeper?'키퍼 전투':loser.name+' '+(diff>=7?'START 복귀':diff+'칸 후퇴')));
 chat('BATTLE',attacker.name+' '+av+' : '+bv+' '+defender.name,'system');
 drawGame();
}
function grantItem(user){if(user.items.length<5){const itemId=ITEMS[rand(ITEMS.length)].id;user.items.push(itemId);appendMove(user.name+'이(가) 보물상자에서 '+ITEM_MAP[itemId].name+' 획득!')}else appendMove(user.name+'은 아이템이 가득 찼습니다.')}
async function resolveTile(p,depth=0){
 if(!match||match.finished||depth>5)return;
 const pos=p.position,type=match.tiles[pos];
 if(type==='goal'||pos>=match.tiles.length-1){finishGame(p);return}
 let landed=false;
 if(type==='boost'||type==='boost4'){
   const n=type==='boost4'?4:3;advance(p,n);appendMove(p.name+' +'+n+' 전진!');landed=true;
 }else if(type==='warp'){
   const row=SOURCE_ROUTES[SOURCE_IDS[match.map]]?.[pos];
   const group=originalTileAt(match.map,pos)?.warpGroup;
   let target=(row?.[3]===10&&Number.isInteger(row[5]))?row[5]:-1;
   if(target<0||target>=match.tiles.length||target===pos){
     const candidate=match.tiles.map((type,i)=>({type,i})).filter(o=>o.type==='warp'&&o.i!==pos&&(!group||originalTileAt(match.map,o.i)?.warpGroup===group)).map(o=>o.i);
     target=candidate.length?candidate[rand(candidate.length)]:pos;
   }
   if(target!==pos){p.position=target;appendMove(p.name+' 워프: '+(pos+1)+' → '+(target+1)+' 칸');landed=true}
 }else if(type==='chest'){grantItem(p)}
 else if(type==='blessing'){while(p.items.length<5)p.items.push(ITEMS[rand(ITEMS.length)].id);appendMove(p.name+' 신의 축복: 아이템 가득 충전')}
 else if(type==='curse'){p.items=[];appendMove(p.name+' 신의 저주: 모든 아이템 소실')}
 else if(type==='prison'){p.jail=3;appendMove(p.name+' 감옥 3턴! 더블 주사위로 탈출할 수 있습니다.')}
 else if(type==='kingbomb'){p.position=0;appendMove(p.name+' 왕폭탄 폭발! START 복귀');match.tiles[pos]='normal'}
 else if(type==='keeperA'||type==='keeperB'||type==='keeperC'){const power={keeperA:1,keeperB:3,keeperC:5};await resolveBattle(p,{id:-1,name:ITEM_MAP[type].name,def:power[type]},true);match.tiles[pos]='normal'}
 else if(type==='ability'){p.ability=Math.min(100,p.ability+25);appendMove(p.name+' 어빌리티 게이지 +25%')}
 else if(type==='ability100'){
   const ts=teamStats(p.team),count=Math.max(1,Math.min(4,p.team?.length>=3?ts.int:(p.team?.length===2?ts.def:ts.atk)));
   const targets=Array.from({length:6},(_,i)=>i+1).sort(()=>Math.random()-.5).slice(0,count);
   const eye=d(6);
   if(targets.includes(eye)){p.ability=100;appendMove(p.name+' 소울풀 판정 '+eye+' / 목표 '+targets.join(',')+' · 어빌리티 100%!')}
   else appendMove(p.name+' 소울풀 판정 '+eye+' / 목표 '+targets.join(',')+' · 실패');
 }
 else if(type==='attribute'){match.attribute=originalTileAt(match.map,pos)?.attribute||['WANDS','SWORDS','CUPS','DISKS'][rand(4)];appendMove('맵 속성이 '+match.attribute+'(으)로 변경!')}
 else if(type==='clover'){p.effects.clover=1;p.effects.spade=0;appendMove(p.name+' 클로버: 다음 주사위는 높은 눈')}
 else if(type==='spade'){p.effects.spade=1;p.effects.clover=0;appendMove(p.name+' 스페이드: 다음 주사위는 낮은 눈')}
 else if(type==='doa'){
   const first=d(6),second=d(first),diff=first-second;
   if(diff>=3)p.position=0;else p.position=Math.max(0,p.position-diff*3);
   appendMove(p.name+' DEAD OR ALIVE: '+first+' / '+second+' → '+(diff>=3?'START':diff*3+'칸 후퇴'));
 }else if(type==='keeper'||type==='arena'){
   if(type==='arena'){
     const incumbent=match.players.find(x=>x!==p&&x.position===pos);
     if(incumbent&&p.effects.dove<=0&&incumbent.effects.dove<=0)await resolveBattle(p,incumbent,false);
   }else{
     const monsters=[['말벌',1],['박쥐',1],['슬라임',1],['가이아버그',2],['해골',2],['좀비',2],['고렘',3],['아지다하카',3],['카르마타',4],['크루거',4],['마장기',6]];
     const mob=monsters[rand(monsters.length)];
     await resolveBattle(p,{id:-1,name:mob[0],def:mob[1]},true);
   }
 }else if(type==='random'||type==='joker'){
   const choices=['chest','ability','boost','clover','prison','blessing','curse'];
   const next=choices[rand(choices.length)];
   if(type==='random')match.tiles[pos]=next;
   appendMove(p.name+' '+(type==='random'?'물음표(고정)':'조커')+' → '+next);
   match.tiles[pos]=next;await resolveTile(p,depth+1);
   if(type==='joker')match.tiles[pos]='joker';
   return;
 }
 if(match.tiles[p.position]==='goal'||p.position>=match.tiles.length-1){finishGame(p);return}
 if(landed){await resolveTile(p,depth+1);return}
 if(!match.finished&&!MAPS[match.map].non&&type!=='arena'){
   const opponent=match.players.find(other=>other!==p&&other.position===p.position&&other.effects.dove<=0&&p.effects.dove<=0);
   if(opponent)await resolveBattle(p,opponent,false);
 }
}
function finishGame(winner){match.finished=true;match.winner=winner.id;match.message=winner.name+'이(가) GOAL에 도착했습니다!';const distance=match.tiles.length-1;const reward=winner.id===0?89:Math.max(1,Math.round(89*match.players[0].position/distance));profile.gp+=reward;if(winner.id===0)profile.wins++;profileUI();persist();chat('SYSTEM',winner.name+'님이 가장 먼저 GOAL에 도착했습니다! GP +'+reward,'system');modal('✦ 주사위의 잔영 · 게임 종료',winner.name+' 승리!　획득 GP +'+reward.toLocaleString()+'\n게임을 다시 시작할 수 있습니다.',[{label:'다시 시작',primary:true,run:()=>navigate('lobby')},{label:'결과 보기',run:()=>drawGame()}]);sfx(925,.4)}
function moveValues(p){
 const stats=teamStats(p.team),extra=p.effects.shoe>0?1:0,values=[];
 const sides=stats.move===2?4:6,n=Math.min(4,(stats.move===2?2:1)+extra);
 for(let i=0;i<n;i++){
   let v=d(sides);
   if(p.effects.clover)v=(sides===4?3:4)+rand(sides===4?2:3);
   if(p.effects.spade)v=1+rand(sides===4?2:3);
   values.push(v);
 }
 
  p.effects.clover=0;p.effects.spade=0;
 return values;
}
function showDice(values){$('die1').textContent=['⚀','⚁','⚂','⚃','⚄','⚅'][Math.min(5,values[0]-1)];$('die2').textContent=values.length>1?['⚀','⚁','⚂','⚃','⚄','⚅'][Math.min(5,values[1]-1)]:'·'}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function computerPrepareTurn(p){
 if(!p.bot||p.jail>0||match.finished)return;
 const itemChoices=['charge','charge25','wing','step','shoe','dove','ring','blessing'];
 if(!p.usedItem){
  const idx=p.items.findIndex(id=>itemChoices.includes(id));
  if(idx>=0){
    const name=p.items[idx];
    if(['wing','step'].includes(name)&&p.position+12<match.tiles.length){
      await applyItem(idx,name==='wing'?8:4);
    }else if(['charge','charge25'].includes(name)&&p.ability<65){
      await applyItem(idx,null);
    }else if(['shoe','dove','ring','blessing'].includes(name)){
      await applyItem(idx,null);
    }
  }
 }
 if(match.finished)return;
 if(p.ability>=100){
   const code=teamStats(p.team).abilityId;
   p.ability=0;
   if(code===30||code===33||code===35||code===37||code===24){
     advance(p,code===30?1+rand(15):1+rand(4));
     if(code===30)p.effects.scar=(p.effects.scar||0)+1;
     appendMove(p.name+' 컴퓨터 어빌리티 발동');
     await resolveTile(p);
   }else if([31,26,27].includes(code))p.effects.teamInt=2;
   else if(code===34)p.effects.destroy=2;
   else if(code===43||code===23||code===25)p.effects.block=2;
   else if(code===56)p.effects.ultimate=1;
   else if([19,20,21,38,39].includes(code))p.effects.valkyrie=2;
   else p.ability=100;
 }
 drawGame();persist();
}
async function takeTurn(){
 if(!match||match.finished||busy)return;
 if(match.mode==='network'&&window.__LEAF_NET__?.role==='guest'&&!remoteAct){
   if(playerCanAct())window.__LEAF_NET__?.send?.({type:'command',action:'roll'});
   return;
 }
 busy=true;const p=match.players[match.active];drawGame();if(p.bot){await wait(250);await computerPrepareTurn(p);if(match.finished){busy=false;return}}
 if(p.jail>0){
   const a=d(6),b=d(6);showDice([a,b]);
   if(a===b){p.jail=0;appendMove(p.name+' 감옥 탈출! 더블 '+a+'/'+b+' · 이동 턴 진행')}
   else{p.jail--;appendMove(p.name+' 감옥 '+p.jail+'턴 남음 (주사위 '+a+'/'+b+')');await wait(p.bot?300:150);busy=false;nextTurn();return}
 }
 const values=moveValues(p),move=values.reduce((a,b)=>a+b,0);showDice(values);
 p.ability=Math.min(100,p.ability+move*3);
 if(move){
   appendMove(p.name+' 이동 주사위 '+values.join('+')+' = '+move+'칸');
   const target=Math.min(match.tiles.length-1,p.position+move),steps=target-p.position;
   for(let i=0;i<steps;i++){
     p.position++;
     if(i===steps-1||i%2===0)drawGame();
     await wait(p.bot?38:60);
   }
   await resolveTile(p);
 }
 drawGame();if(match.finished){busy=false;return}
 if(p.effects.shoe>0)p.effects.shoe--;
 if(p.effects.dove>0)p.effects.dove--;
 if(p.effects.armageddon>0)p.effects.armageddon--;
 if(p.effects.valkyrie>0)p.effects.valkyrie--;
 
 if(p.effects.block>0)p.effects.block--;
 if(p.effects.destroy>0)p.effects.destroy--;
 if(p.effects.keeper>0)p.effects.keeper--;
 if(p.effects.teamInt>0)p.effects.teamInt--;
 if(p.effects.ultimate>0)p.effects.ultimate--;
 await wait(p.bot?180:100);busy=false;nextTurn();
}
function nextTurn(){
 if(!match||match.finished)return;
 match.active=(match.active+1)%match.players.length;
 if(match.active===0)match.round++;
 const p=activePlayer();p.usedItem=false;
 drawGame();persist();
 if(p.bot)setTimeout(()=>{if(route==='game'&&!busy&&match&&!match.finished&&match.players[match.active].bot)takeTurn()},430);
 else appendMove(p.name+' 차례입니다. 주사위를 굴리세요.');
}
function init(){installBoardControls();installAuthenticMaps();if(match)chooseSourcePath(match.map);profileUI();buildRoomList();buildPeople();drawTeam();drawShop();query('[data-route]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.route)));query('.group-tab').forEach(b=>b.addEventListener('click',()=>{group=b.dataset.group;shopPage=0;drawShop()}));$('shop-prev').onclick=()=>{shopPage--;drawShop()};$('shop-next').onclick=()=>{shopPage++;drawShop()};$('point-limit').onchange=drawTeam;$('start-game').onclick=startGame;$('resume-game').onclick=()=>{if(match&&!match.finished){busy=false;navigate('game');chat('SYSTEM','진행 중인 게임을 이어합니다.','system')}};$('roll-btn').onclick=takeTurn;$('ability-btn').onclick=useAbility;$('exit-game').onclick=()=>modal('게임에서 나가기','진행 중인 게임은 브라우저에 보관됩니다. 나갔다가 주사위의 잔영 버튼으로 다시 들어올 수 있습니다.',[{label:'나가기',primary:true,run:()=>navigate('lobby')},{label:'취소'}]);$('shop-buy').onclick=()=>{const c=CARD_MAP[chosenCard];if(profile.owned.includes(c.id))return modal('매직카덴',c.name+' 카드는 이미 가지고 있습니다.',[{label:'확인'}]);if(profile.gp<c.price)return modal('매직카덴','GP가 부족합니다.',[{label:'확인'}]);modal('매직카덴',c.name+' 카드를 '+c.price.toLocaleString()+'GP에 구매하시겠습니까?',[{label:'구매',primary:true,run:()=>{profile.gp-=c.price;profile.owned.push(c.id);profileUI();drawShop();drawTeam();chat('매직카덴',c.name+' 카드를 구매했습니다.','system');sfx(830)}},{label:'취소'}])};$('rename').onclick=()=>{const div=document.createElement('div');div.textContent='사용할 닉네임을 입력하세요.';const input=document.createElement('input');input.maxLength=12;input.value=profile.name;div.append(document.createElement('hr'),input);modal('4LEAF 별명 변경',div,[{label:'변경',primary:true,run:()=>{if(!input.value.trim())return;profile.name=input.value.trim().slice(0,12);profileUI();buildPeople();if(match&&!match.finished)match.players[0].name=profile.name;chat('SYSTEM','닉네임이 '+profile.name+'(으)로 변경되었습니다.','system')}},{label:'취소'}])};$('audio').onclick=()=>{soundOn=!soundOn;syncMusic();log(soundOn?'원작 배경음악/효과음 켜짐':'배경음악/효과음 꺼짐');sfx(650)};$('help').onclick=()=>navigate('help-screen');$('make-room').onclick=()=>modal('새로운 채팅방','채팅방 개설은 로컬 재현 모드에서만 가능합니다.',[{label:'확인'}]);$('chat-form').onsubmit=e=>{e.preventDefault();const input=$('message'),message=input.value.trim();input.value='';if(!message)return;chat(profile.name,message);if(window.__LEAF_NET__?.connected&&match?.mode==='network')window.__LEAF_NET__.send({type:'chat',who:profile.name,text:message});sfx(480);if(route==='rooms'&&Math.random()<.25)setTimeout(()=>chat('티치엘','오늘도 좋은 하루 보내세요!','npc'),650)};query('#online-list').forEach(()=>{});const list=$('online-list');['Guest (LOCAL)','티치엘 (NPC)','막시민 (NPC)','보리스 (NPC)','루시안 (NPC)','이스핀 (NPC)','시벨린 (NPC)','루시아 (NPC)','샤이닝 브리즈','실버 호라이즌','켈티카'].forEach(n=>{const div=document.createElement('div');div.textContent='♧ '+n;list.append(div)});setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})},12000);$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});chat('SYSTEM','4LEAF Browser에 오신 것을 환영합니다.','system');chat('SYSTEM','원작 화면 재구성 · AI 대전 · 로컬 채팅. 온라인 멀티플레이는 지원하지 않습니다.','system');navigate('sky');window.__LEAF_BRIDGE__={getMatch:()=>match,getName:()=>profile.name,onState:null,
 receiveMatch:remote=>{if(window.__LEAF_NET__?.role!=='guest'||!remote||!MAPS[remote.map])return;
   match=remote;busy=false;
   try{localStorage.setItem('rog_match',JSON.stringify(match))}catch{}
   if(route!=='game')navigate('game');else drawGame();
 },
 setGuestName:name=>{if(window.__LEAF_NET__?.role==='host'&&match?.mode==='network'){
    match.players[1].name=String(name).trim().slice(0,12)||'플레이어 2';drawGame();persist();
 }},
 remoteBattleChoice:(bid,label)=>{
    if(window.__LEAF_NET__?.role!=='host'||!remoteBattle||remoteBattle.bid!==bid||!remoteBattle.options.includes(label))return;
    const opts=query('#modal-buttons button');
    const selection=opts.find(btn=>btn.textContent===label);
    if(selection)selection.click();
 },
 remoteCommand:async(action,index,steps)=>{
   if(window.__LEAF_NET__?.role!=='host'||match?.mode!=='network'||match.active!==1||busy||match.finished||remoteAct)return;
   if(!['roll','ability','item'].includes(action))return;
   if(action==='item'&&(!Number.isInteger(index)||index<0||index>=activePlayer().items.length||!Number.isFinite(Number(steps))))return;
   remoteAct=true;try{
     if(action==='roll')await takeTurn();
     else if(action==='ability')await useAbility();
     else await useItem(index,steps);
   }finally{remoteAct=false}
 }};window.__ROG_TEST__={startGame,drawGame,takeTurn,teamStats,generateTiles,getMatch:()=>match,go:navigate,setRoll:()=>{},setMatch:v=>{match=v;drawGame()},getSourceMaps:()=>SOURCE_INFO,getSourceTiles:()=>SOURCE_TILES,resolveBattle,moveValues,activePlayer,playerCanAct,refreshResume};if(match&&!match.finished){log('저장된 경기가 있습니다. 주사위 대기실의 이어하기로 복원하세요.')}refreshResume()}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();