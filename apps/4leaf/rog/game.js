'use strict';
(function(){
const $=id=>document.getElementById(id);
const query=(s,parent=document)=>Array.from(parent.querySelectorAll(s));
const routeNames={sky:'포리프 월드맵',city:'켈티카의 거리',rooms:'하이아칸 채팅 타운','dice-channels':'주사위의 잔영 채널 선택',lobby:'주사위의 잔영 대기실',shop:'매직카덴',game:'창세기월드 · 주사위의 잔영','help-screen':'4LEAF 도움말'};
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
const SOURCE_ROUTES=window.ORIGINAL_LEAF_MAPS||{},
 SOURCE_TILES=window.ORIGINAL_LEAF_TILES||{};
// The 2002 source contains 26 real DMP paths, but the extracted client
// metadata names only 25. The 135-cell source map 0170 was silently
// unselectable. Preserve the unmodified archive tables and explicitly
// label an unverified display name; never invent a historical title.
const SOURCE_INFO={...(window.ORIGINAL_LEAF_MAP_INFO||{})};
for(const [id,rows] of Object.entries(SOURCE_ROUTES)){
 if(Array.isArray(rows)&&rows.length>=10&&!SOURCE_INFO[id]){
  SOURCE_INFO[id]={
   title:'이름 미확인 · 원본 DMP '+id,
   mode:null,
   metadataStatus:'ARCHIVE-MAP-PRESENT/TITLE-UNVERIFIED'
  };
 }
}
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
const savedMatch=safe('match',null);if(savedMatch&&Array.isArray(savedMatch.players)&&savedMatch.players.length>=2&&savedMatch.players.length<=8&&!savedMatch.finished){
 match=savedMatch;
 // Saved AI games never resume automatic dice turns without fresh consent.
 if(match.mode==='ai')match.botAutoplay=false;
}
function activePlayer(){return match?.players?.[match.active]||null}
function playerCanAct(){
 if(!(match&&!match.finished&&!busy&&activePlayer()))return false;
 // A paused computer turn is manually rollable. Fresh hotseat players
 // already have bot=false; real network permissions remain unchanged.
 if(activePlayer().bot&&!(match.mode==='ai'&&match.botAutoplay===false))return false;
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
function syncMusic(){if(!soundOn){if(bgm)bgm.pause();return}const track=({sky:'00',city:'01',rooms:'02','dice-channels':'03',lobby:'03',shop:'04',game:'05','help-screen':'06'})[route]||'00';if(bgm&&bgmTrack===track){bgm.play().catch(()=>{});return}if(bgm)bgm.pause();bgm=new Audio('./music/'+track+'.mp3');bgm.loop=true;bgm.volume=.28;bgmTrack=track;bgm.play().catch(()=>{})}
function sfx(freq=500,duration=.07){if(!soundOn)return;try{const AC=window.AudioContext||window.webkitAudioContext;audioCtx=audioCtx||new AC();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='triangle';o.frequency.value=freq;g.gain.setValueAtTime(.038,audioCtx.currentTime);g.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+duration);o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+duration)}catch{}}
function chat(who,message,type=''){const line=document.createElement('div');line.className=type;const b=document.createElement('b');b.textContent=who+'　';line.append(b,document.createTextNode(String(message)));$('chat-log').append(line);while($('chat-log').children.length>90)$('chat-log').firstElementChild.remove();$('chat-log').scrollTop=$('chat-log').scrollHeight}
function profileUI(){$('nick').textContent=profile.name;$('profile-name').textContent=profile.name;$('my-name').textContent=profile.name;$('gp').textContent=profile.gp.toLocaleString();$('shop-gp').textContent=profile.gp.toLocaleString();$('wins').textContent=profile.wins+'승';persist()}
function navigate(id){if(!routeNames[id])return;route=id;if(id!=='game')$('app')?.classList.remove('dice-items-open');document.getElementById('app')?.classList.toggle('app-classic-dice',id==='game');$('app').classList.toggle('app-game',id==='game');query('.scene').forEach(s=>s.classList.toggle('hidden',s.id!==id));query('[data-route]').forEach(el=>el.classList.toggle('active',el.dataset.route===id));$('where').textContent=routeNames[id];$('chat-location').textContent=routeNames[id];if(id==='game'&&match){
 drawGame();
 const resumedMatch=match,p=activePlayer();
 if(match.mode==='ai'&&match.botAutoplay===true&&p?.bot&&!busy)
  setTimeout(()=>{if(route==='game'&&match===resumedMatch&&!match.finished&&
   match.botAutoplay===true&&activePlayer()?.bot&&!busy)takeTurn()},500);
}if(id==='shop')drawShop();if(id==='lobby'){drawTeam();refreshResume()}window.dispatchEvent(new CustomEvent('leaf-route-change',{detail:{route:id}}));log(routeNames[id]+'에 입장하였습니다.');syncMusic();sfx(610)}
function modal(title,body,buttons){
 // Original Genesis IMG/dialog.png is the native 292x110 panel. Limit the
 // source-backed frame to short, real GAME confirmations and status text;
 // cards, selectors and battle result layouts retain their own full-size UI.
 // The existing live buttons and resolver callbacks are never duplicated.
 const modalNode=$('modal');
 const simple=route==='game'&&typeof body==='string'&&body.length<=180&&
  Array.isArray(buttons)&&buttons.length>=1&&buttons.length<=3;
 if(simple)modalNode.dataset.nativeDiceDialog='IMG/dialog.png';
 else delete modalNode.dataset.nativeDiceDialog;
 $('modal-title').textContent=title;$('modal-content').replaceChildren();if(typeof body==='string'){$('modal-content').textContent=body}else if(body)$('modal-content').append(body);$('modal-buttons').replaceChildren();buttons.forEach(opt=>{const b=document.createElement('button');b.textContent=opt.label;b.className=opt.primary?'primary':'';
  // Native Dice/IMG/okcancelbut.bmp has exactly two captions. Do not put
  // a misleading screenshot label on Exit/Use/Next or custom game actions.
  if(simple&&opt.label==='확인')b.dataset.originalDiceAction='confirm';
  if(simple&&opt.label==='취소')b.dataset.originalDiceAction='cancel';
  b.onclick=()=>{$('modal').classList.add('hidden');if(opt.run)opt.run()};$('modal-buttons').append(b)});$('modal').classList.remove('hidden')}
function ask(title,body,options){return new Promise(resolve=>modal(title,body,options.map((a,i)=>({label:a,primary:i===0,run:()=>resolve(i)}))))}
function syncNativeDiceEvent(message){
 // The original app's modern #move-log footer is hidden by the restored
 // 2003 game layout. Render the genuine source 244x52 IMG event frame
 // INSIDE the actual visible battlefield instead, sourced exclusively from
 // real recorded match moves, never an invented status or copied screenshot.
 const area=$('board-area');if(!area||!match)return;
 let output=$('dice-native-event');
 if(!output){
  output=document.createElement('output');
  output.id='dice-native-event';
  output.className='dice-native-event';
  output.setAttribute('role','status');
  output.setAttribute('aria-live','polite');
  output.dataset.source='IMG/eventmsgbox.png';
  area.append(output);
 }
 output.textContent=String(message||'');
 output.title=String(message||'');
 output.dataset.eventText=String(message||'');
}
function toast(message){
 log(message);
 const logElement=$('move-log');
 if(logElement){
  logElement.textContent=message;
  // IMG/eventmsgbox.png is a 244x52 original event panel. Its clipped
  // one/two-line text is readable and the full authentic event stays in the
  // DOM title and actual match.history; never manufacture gameplay entries.
  logElement.title=String(message);
  logElement.dataset.nativeSource='IMG/eventmsgbox.png';
 }
 syncNativeDiceEvent(message);
}
function rosterByIds(ids){return (ids||[]).map(id=>CARD_MAP[id]).filter(Boolean).slice(0,4)}
function teamStats(ids){
 const cards=(ids||[]).slice(0,4).map(id=>CARD_MAP[id]||null),field=cards.slice(0,3).filter(Boolean);
 const attack=cards[0]||BASE_CARDS[0],defend=cards[1]||attack,assist=cards[2]||null;
 const same=field.length>0&&field.every(c=>c.move===field[0].move);
 return {move:same?field[0].move:1,atk:attack.atk,def:defend.def,int:assist?assist.int:0,
 attackElement:attack.element||'None',defendElement:defend.element||'None',supportElement:assist?.element||'None',
 point:cards.reduce((sum,c)=>sum+(c?.point||0),0),ability:attack.ability,abilityId:attack.abilityId,portrait:attack.portrait,name:attack.name};
}
function elementalModifier(team,kind,attribute=match?.attribute||'NONE'){
 const stats=teamStats(team),attr=String(attribute).toUpperCase(),element=String(
 kind==='attack'?stats.attackElement:kind==='defense'?stats.defendElement:kind==='support'?stats.supportElement:stats.attackElement
 ).toUpperCase();
 if(kind==='attack'&&element==='SWORDS')return attr==='SWORDS'?2:attr==='CUPS'?-2:0;
 if(kind==='defense'&&element==='WANDS')return attr==='WANDS'?2:attr==='DISKS'?-2:0;
 if(kind==='support'&&element==='CUPS')return attr==='CUPS'?2:attr==='SWORDS'?-2:0;
 if(kind==='move'&&element==='DISKS')return attr==='DISKS'?2:attr==='WANDS'?-2:0;
 return 0;
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
// Archived CardShop sprite atlas includes actual 판매하기 button art, but
// surviving client has NOT verified its resale GP rule. 50% is a clearly
// labeled WEB economic fallback, never represented as source historical data.
const inferredShopResaleGP=card=>Math.max(0,Math.floor((Number(card?.price)||0)/2));
function shopCanSell(card){
 return !!card&&profile.owned.includes(card.id)&&profile.owned.length>1&&
  !profile.team.includes(card.id)&&
  !(match&&!match.finished&&match.players?.some(p=>p.team?.includes(card.id)));
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
   // The archived CardShop atlas contains distinct original Normal and
   // Valuable card frames; expose the genuine catalog rarity to the skin.
   b.dataset.rank=c.rank==='valuable'?'valuable':'normal';
   b.dataset.cardId=c.id;
   b.dataset.owned=profile.owned.includes(c.id)?'true':'false';
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
   b.dataset.cardId=c.id;b.title=c.name+' ('+c.point+'pt)';
   const icon=document.createElement('img');icon.className='shop-owned-portrait';
   icon.alt='';icon.src=imageFor(c.id);icon.loading='lazy';
   const name=document.createElement('span');name.className='shop-owned-name';name.textContent=c.name;
   const ability=document.createElement('small');ability.className='shop-owned-ability';ability.textContent=c.ability;
   b.append(icon,name,ability);
   if(chosenCard===c.id)b.classList.add('selected');
   b.onclick=()=>{if(!shopFiltered().find(x=>x.id===id))group='all';selectShopCard(id)};
   owned.append(b);
 });
 const c=CARD_MAP[chosenCard]||cards[0]||BASE_CARDS[0];
 if(c){
   $('shop-selected').textContent=c.name+' · '+c.ability+' · '+c.element+' / 이동'+c.move+'　공격'+c.atk+'　방어'+c.def+'　지력'+c.int+'　POINT '+c.point+' / '+c.price.toLocaleString()+' GP';
   $('shop-buy').disabled=profile.owned.includes(c.id)||profile.gp<c.price;
   $('shop-buy').textContent=profile.owned.includes(c.id)?'보유중':(profile.gp<c.price?'GP 부족':'구입하기');
   const sell=$('shop-sell'),canSell=shopCanSell(c);
   sell.disabled=!canSell;
   sell.textContent='판매하기';
   sell.dataset.resaleStatus='inferred-web-price-not-original';
   sell.dataset.resaleGp=String(inferredShopResaleGP(c));
   sell.title=canSell?
    c.name+' · 임시 판매가 '+inferredShopResaleGP(c).toLocaleString()+' GP (원작 판매 가격 규칙 미확인)':
    (profile.team.includes(c.id)?'출전 파티에 포함된 카드는 판매할 수 없습니다.':
    (!profile.owned.includes(c.id)?'먼저 해당 카드를 보유해야 합니다.':'마지막 카드나 진행 중 경기 참가 카드는 판매할 수 없습니다.'));
 }
 profileUI();
}
function buildRoomList(){const list=$('room-list');list.replaceChildren();['샤이닝 브리즈','실버 호라이즌','윈트리 아이스','헤이즐리 웨이브','엘핀 포레스트'].forEach((r,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+r+'　('+(['평원','설원','빙원','해양','숲'][i])+')';b.className=r===currentRoom?'selected':'';b.onclick=()=>{currentRoom=r;const roomScene=document.querySelector('#rooms .room-floor');if(roomScene)roomScene.style.backgroundImage='url("./original/ChatRoom/room'+Math.min(i,5)+'.png")';buildRoomList();$('room-title').textContent='하이아칸 · '+r;chat('SYSTEM',r+' 방에 입장했습니다. 다른 이용자와는 연결되지 않습니다.','system')};list.append(b)});$('room-title').textContent='하이아칸 · '+currentRoom}
function buildPeople(){const root=$('town-figures');if(root)root.replaceChildren()}
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
function chooseSourcePath(map){const records=SOURCE_ROUTES[SOURCE_IDS[map]];if(!records||records.length<8){PATH=pathCoords();return}/* Authentic DMP index positions are unchanged. The browser camera owns ONE explicit 150x100 WEB display pitch, and all maps share that projection. */const grid=window.__LEAF_CAMERA__?.getState?.().sourceGrid||{width:2800,height:1551,pitchX:70,pitchY:47};const xs=records.map(p=>p[0]),ys=records.map(p=>p[1]);const midX=(Math.min(...xs)+Math.max(...xs))/2,midY=(Math.min(...ys)+Math.max(...ys))/2;PATH=records.map(p=>({x:50+(p[0]-midX)*grid.pitchX/grid.width*100,y:50+(p[1]-midY)*grid.pitchY/grid.height*100}))}
function installAuthenticMaps(){const list=$('map-select'),entries=Object.entries(SOURCE_INFO).filter(([id])=>SOURCE_ROUTES[id]&&SOURCE_ROUTES[id].length>9);if(!entries.length)return;list.replaceChildren();const rank=['4LEAF','주사위','워프 게이트','PK','악마의 달팽이','한반도','For the Lucky'];entries.sort((a,b)=>{let i=rank.indexOf(a[1].title),j=rank.indexOf(b[1].title);return (i<0?99:i)-(j<0?99:j)});for(const [id,info] of entries){const title=info.title,length=SOURCE_ROUTES[id].length;const old=MAPS[title]||{};const generate=(step,offset)=>Array.from({length:Math.floor(length/step)},(_,i)=>offset+i*step).filter(i=>i>0&&i<length-1);MAPS[title]={length,non:['악마의 달팽이','한반도'].includes(title),warp:old.warp||generate(30,8),keepers:old.keepers||generate(17,13),jail:old.jail||generate(44,25),chests:old.chests||generate(19,6),boost:old.boost||generate(23,17),attribute:old.attribute||generate(29,20),joker:old.joker||generate(41,36)};const opt=document.createElement('option');opt.value=title;
 opt.textContent=title+' · '+length+'칸 [원본 '+id+
  (SOURCE_TILES[id]?' · 발판 복원':' · 경로 복원')+
  (info.metadataStatus?' · 이벤트/이름 미검증':'')+']';
 opt.dataset.originalMapId=id;
 opt.dataset.historicalTitleVerified=String(!info.metadataStatus);
 list.append(opt)}const randomOption=document.createElement('option');randomOption.value='__RANDOM__';randomOption.textContent='랜덤맵 · 원작 2003.02 업데이트';list.append(randomOption);list.value='4LEAF'}
function freshItems(){return Array.from({length:3},()=>{const pool=ITEMS.filter(item=>!item.disabled);return pool[rand(pool.length)].id})}
function newPlayer(id,bot,name,team){return {id,bot,name,team,position:0,jail:0,ability:0,items:freshItems(),effects:{shoe:0,dove:0,clover:0,spade:0,ring:0,armageddon:0,valkyrie:0,oddcurse:0,evencurse:0,block:0,destroy:0,keeper:0},usedItem:false,color:COLORS[id],pawn:PAWNS[id]}}
function startGame(){let map=$('map-select').value;const limit=Number($('point-limit').value),stats=teamStats(profile.team);if(map==='__RANDOM__'){const candidates=Object.keys(SOURCE_IDS).filter(name=>MAPS[name]&&SOURCE_ROUTES[SOURCE_IDS[name]]?.length>9);map=candidates[rand(candidates.length)]||'4LEAF';}chooseSourcePath(map);if(!profile.team[0])return modal('파티 구성','공격 체스맨을 선택하세요.',[{label:'확인',primary:true}]);if(stats.point>limit)return modal('소환 POINT 초과','현재 파티는 '+stats.point+'POINT이며 제한은 '+limit+'POINT입니다.',[{label:'확인',primary:true}]);const selectedMode=$('game-mode').value,hotseat=selectedMode!=='ai',bots=selectedMode==='network'?1:Number($('bot-count').value);
 if(selectedMode==='network'&&(!window.__LEAF_NET__?.connected||window.__LEAF_NET__.role!=='host')){
    return modal('온라인 대전 연결','온라인 대전에서는 먼저 상대 브라우저와 연결해야 합니다. 호스트에서 연결을 시작하세요.',[{label:'확인',primary:true}]);
 }let players=[newPlayer(0,false,profile.name,profile.team.slice())];for(let i=0;i<bots;i++){const weakTeams=CHR_SOURCE.length>50?[
 // Default opponents must have an actual recovered OBS body. In the old
 // sample, c_0096 (no decoded OBS source) displayed a HUGE synthetic mannequin.
 // Existing saved/user-selected teams are never silently replaced.
 ['c_0045','c_0042','c_0040'],['c_0042','c_0045','c_0043'],['c_0043','c_0044','c_0045'],['c_0044','c_0045','c_0042'],['c_0045','c_0043','c_0047'],['c_0047','c_0048','c_0045'],['c_0048','c_0049','c_0040']]:
 [['rashid','soldier','narcia'],['joan','narcia','soldier'],['soldier','joan','rashid'],['iolyn','soldier','narcia'],['merza','rashid','soldier'],['christian','soldier','joan'],['damian','soldier','narcia']];let team=weakTeams[i].filter((_,j)=>j===0||limit>=8);while(teamStats(team).point>limit)team.pop();players.push(newPlayer(i+1,!hotseat,selectedMode==='network'?(window.__LEAF_NET__?.guestName||'플레이어 2'):(hotseat?'플레이어 '+(i+2):BOT_NAMES[i]),team))}match={version:5,map,mode:selectedMode,botAutoplay:selectedMode==='ai',diceRegion:window.__LEAF_LOBBY__?.getState?.().region||null,diceChannel:window.__LEAF_LOBBY__?.getState?.().channel||null,startedAt:Date.now(),tiles:generateTiles(map),players,active:0,round:1,finished:false,winner:-1,attribute:'NONE',message:'주사위를 굴려 주세요.',lastRoll:[],history:[],pending:null};busy=false;persist();navigate('game');chat('SYSTEM',map+' 게임을 시작했습니다. '+(selectedMode==='network'?'두 기기 온라인 연결':hotseat?'사람 '+(bots+1)+'명이 번갈아 플레이':'컴퓨터 '+bots+'명과 대전')+'.','system');drawGame();persist()}
function appendMove(message){if(!match)return;match.message=message;match.history.push(message);if(match.history.length>90)match.history.shift();toast(message);persist()}
/* Source-proven historical sprite numbers from original Dice/DMP.pak palette headers:
   Korean event labels map 1-to-1 to separate authentic Dice/TIS.pak images. */
const ORIGINAL_TIS_EVENT={
 start:'0024',goal:'0018',normal:'0015',practice:'0043',
 boost:'0001',boost4:'0000',clover:'0006',ability:'0007',
 blessing:'0009',chest:'0010',curse:'0012',doa:'0014',
 arena:'0017',keeper:'0017',prison:'0019',joker:'0020',
 spade:'0021',ability100:'0023',random:'0035',
 kingbomb:'0021',keeperA:'0017',keeperB:'0017',keeperC:'0017'
};
const ORIGINAL_TIS_ATTRIBUTES={WANDS:'0027',SWORDS:'0025',CUPS:'0011',DISKS:'0013'};
const ORIGINAL_TIS_WARPS={'1':'0028','3':'0030','4':'0031'};
function sourceTileGraphic(type,index){
 const original=originalTileAt(match.map,index);
 if(type==='attribute'){
   const attr=(original?.type==='attribute'?original.attribute:match.attribute)||'WANDS';
   return ORIGINAL_TIS_ATTRIBUTES[attr]||'0027';
 }
 if(type==='warp'){
   const group=(original?.type==='warp'?original.warpGroup:'1')||'1';
   return ORIGINAL_TIS_WARPS[group]||'0028';
 }
 return ORIGINAL_TIS_EVENT[type]||ORIGINAL_TIS_EVENT.normal;
}
function drawBoard(){
 if(!match)return;
 const root=$('board-nodes'),svg=$('board-lines');
 const key=match.map+'|'+match.tiles.join(',');
 if(root.dataset.renderKey!==key){
   // Keep genuine Registry actors and their animation state while replacing
   // event tile content (item swaps, map changes and game resumes).
   const existingPawns=$('board-pawns');
   root.dataset.renderKey=key;root.replaceChildren();svg.replaceChildren();
   const cameraSize=window.__LEAF_CAMERA__?.getState?.().size||{width:2650,height:2050};
   const coords=PATH.slice(0,match.tiles.length).map(p=>({
    x:p.x*cameraSize.width/100,y:p.y*cameraSize.height/100}));
   const path=document.createElementNS('http://www.w3.org/2000/svg','polyline');
   path.setAttribute('points',coords.map(p=>p.x+','+p.y).join(' '));
   path.setAttribute('fill','none');path.setAttribute('stroke','#b6a2d5');
   path.setAttribute('stroke-width','4');path.setAttribute('stroke-linejoin','round');path.setAttribute('opacity','.35');svg.append(path);
   const fragment=document.createDocumentFragment();
   coords.forEach((pos,i)=>{
     const type=match.tiles[i],b=document.createElement('div');b.className='tile '+type;
     b.style.left=PATH[i].x+'%';b.style.top=PATH[i].y+'%';b.dataset.tile=i;
     // Genuine original DMP axial-grid coordinates are unchanged.
     // Render full SOURCE 145x97 pixels with screenshot-calibrated WEB
     // spacing 150x100. Original DMP indices stay 70x47; the modest
     // overlap is painted in DMP depth order, not by route index.
     // Original MVE elevation and camera matrix remain unrecovered.
     const dmp=SOURCE_ROUTES[SOURCE_IDS[match.map]]?.[i];
     if(dmp){
      b.dataset.dmpX=String(dmp[0]);
      b.dataset.dmpY=String(dmp[1]);
      b.dataset.dmpCellCode=String(dmp[2]);
     }
     b.dataset.nativeTisSize='145x97';
     b.dataset.dmpLogicalPitch='70x47';
     b.dataset.projectedPitch='150x100-web-nonoverlap';
     // Painter order follows the original DMP grid, not route parity.
     // Cells on the same row are sorted by their genuine x coordinate;
     // a row ahead ALWAYS paints over rows behind it. Reserve +1 for actors.
     const sourceY=dmp?dmp[1]:Math.round(PATH[i].y*100);
     const sourceX=dmp?dmp[0]:Math.round(PATH[i].x);
     b.style.zIndex=String((sourceY*256+sourceX)*2);
     const sourceArt=sourceTileGraphic(type,i);
     b.dataset.originalArt=sourceArt;
     b.style.setProperty('background','url("./original/Tiles/'+sourceArt+'.png") center / 100% 100% no-repeat','important');
     // Preserve the source's existing RGBA transparent pixels and derive
     // its actual click silhouette. Only genuinely opaque exterior mattes
     // require further masking; every DMP tile stays independently playable.
     window.__LEAF_TIS_ALPHA__?.apply(b,sourceArt);
     if(SOURCE_IDS[match.map]){
       const columns=Math.max(8,Math.sqrt(match.tiles.length)*1.6);
       b.style.width=Math.max(2.5,Math.min(5,72/columns))+'%';
       b.style.height=Math.max(4.5,Math.min(9,120/columns))+'%';
     }
     // Native TIS already contains its original art and event symbol.
     // Never paint invented numbers or web font glyphs over source pixels.
     // Keep cell index discoverable through live metadata and a tooltip.
     b.title=(i+1)+'칸 · '+type;
     b.setAttribute('aria-label',b.title);
     b.onclick=()=>log((i+1)+'칸 · '+type+' '+match.players.filter(p=>p.position===i).map(p=>p.name).join(', '));
     fragment.append(b);
   });root.append(fragment);
   if(existingPawns)root.append(existingPawns);
 }
 const currentPositions=new Set(match.players.map(p=>p.position));
 query('.tile',root).forEach((node,i)=>node.classList.toggle('player-here',currentPositions.has(i)));
 drawPawns();
}
function drawPawns(){
 let layer=$('board-pawns');
 const tiles=$('board-nodes');
 if(!layer){layer=document.createElement('div');layer.id='board-pawns';}
 // Old renderer always painted actors in an isolated high-z sibling layer,
 // so distant characters floated ABOVE every nearer original TIS platform.
 // Dissolve the actor wrapper via CSS display:contents and share the true DMP
 // painter order with interactive original event tiles.
 if(tiles&&layer.parentElement!==tiles)tiles.append(layer);
 const players=match.players;
 for(const stale of query('.board-pawn',layer)){
   if(!players.some(p=>String(p.id)===stale.dataset.id))stale.remove();
 }
 for(const p of players){
   let pawn=query('.board-pawn',layer).find(node=>node.dataset.id===String(p.id));
   if(!pawn){
     pawn=document.createElement('div');pawn.className='board-pawn';pawn.dataset.id=String(p.id);
     const name=document.createElement('span');name.className='board-pawn-name';
     pawn.append(name);layer.append(pawn);
   }
   // Genesis War combat chessman identity derives from the actual FIRST
   // chessman card in the player's real team. Never use ChatTown savaNN.
   // Archive full-body frames are still missing; the temporary articulated
   // eight-head web rig advertises inferred source until frames are decoded.
   window.__LEAF_GENESIS_ACTORS__?.mount(pawn,p,imageFor(p.team[0]));
   const point=PATH[Math.min(p.position,PATH.length-1)]||PATH[0];
   const previous=Number(pawn.dataset.position);
   const moved=pawn.dataset.position!==undefined&&previous!==p.position;
   if(moved)window.__LEAF_GENESIS_ACTORS__?.pose(pawn,'walk',240);
   pawn.dataset.position=String(p.position);
   // Multiple real players may share an ORIGINAL DMP cell. The old 11px
   // offset stacked native 33..80px OBS bodies completely atop one another,
   // making the original second chessman disappear behind a web proxy.
   // Keep every authoritative DMP position unchanged; spread only their
   // rendered feet within the existing 145x97 tile top. Source game engine
   // same-cell formation offsets are not recovered (INFERRED visual spacing).
   const peers=players.filter(q=>q.position===p.position);
   const slot=peers.findIndex(q=>q.id===p.id);
   const columns=Math.min(3,peers.length);
   const column=slot%columns,row=Math.floor(slot/columns);
   const sourceCellOffsetX=Math.round((column-(columns-1)/2)*32+(row%2)*8);
   const sourceCellOffsetY=-row*22;
   pawn.dataset.cellPeerCount=String(peers.length);
   pawn.dataset.cellPeerSlot=String(slot);
   pawn.dataset.formationSource='inferred-visibility-offset/source-DMP-position';
   // CSS calc(45% + -16px) is invalid and silently drops actor anchoring.
   // Always emit a single signed additive operator instead.
   pawn.style.left='calc('+point.x+'% '+(sourceCellOffsetX<0?'-':'+' )+' '+Math.abs(sourceCellOffsetX)+'px)';
   pawn.style.top='calc('+point.y+'% '+(sourceCellOffsetY<0?'-':'+' )+' '+Math.abs(sourceCellOffsetY)+'px)';
   pawn.style.setProperty('--pawn-color',p.color);
   const platform=tiles?.querySelector('.tile[data-tile="'+p.position+'"]');
   const platformDepth=Number(platform?.style.zIndex);
   // Actor stands above THEIR tile, but genuinely front-facing tiles may
   // occlude them. The original height/mesh code is not recovered; this uses
   // only verified DMP planar painter depth, not fabricated elevation.
   const depth=Number.isFinite(platformDepth)?platformDepth+1:0;
   pawn.style.setProperty('--leaf-pawn-dmp-depth',String(depth));
   pawn.dataset.depthTile=String(p.position);
   pawn.dataset.dmpPainterDepth=String(depth);
   pawn.classList.toggle('pawn-current',match.active===p.id);
   pawn.querySelector('.board-pawn-name').textContent=p.name;
 }
}
function drawBattlePanels(){
 const root=$('battle-player-panels');if(!root||!match)return;
 // Archival 4LEAF board.jpg/battle.jpg: 1/3/5 on the LEFT, 2/4/6 on
 // the RIGHT. These are genuine match players; empty slots are not NPCs.
 const present=new Map(match.players.map((p,i)=>[i,p]));
 const slots=match.players.length>6?4:3;
 root.replaceChildren();
 const left=document.createElement('div'),right=document.createElement('div');
 left.className='battle-team-side left';right.className='battle-team-side right';
 for(let i=0;i<slots*2;i++){
  const p=present.get(i);
  const card=document.createElement('div');
  card.className='battle-side-card'+(p&&match.active===i?' active':'')+(p?' occupied':' vacant');
  card.dataset.slot=String(i+1);
  card.style.setProperty('--player-tint',p?.color||'#53609a');
  // The original top-left of each 4LEAF portrait explicitly labels 1..8.
  const num=document.createElement('span');num.className='battle-side-num';
  num.textContent=(i+1)+'';
  card.append(num);
  if(p){
   const portrait=document.createElement('div');portrait.className='battle-side-portrait';
   const avatar=document.createElement('img');avatar.alt='';
   // Historical 800x600 battle.jpg player rails show player avatar heads.
   // This is NOT the full-body chessman on the board or CardData party HUD.
   // For the local human use their currently selected Registry avatar.
   const savedAvatar=window.__LEAF_SOCIAL__?.getState?.().avatar;
   const avatarSources=['sava00','sava82','sava06','sava01','sava85','sava02',
    'sava84','sava04','sava03','sava83','sava05','sava86'];
   const participantAvatar=p.id===0&&Number.isInteger(savedAvatar)?
    avatarSources[Math.max(0,Math.min(avatarSources.length-1,savedAvatar))]:
    avatarSources[(Number(p.id)||0)%avatarSources.length];
   avatar.src='./original/Registry/'+participantAvatar+'.png';
   avatar.dataset.sourceRole='player-avatar-not-chessman';
   // Preserve genuine source PNG; compute green-key alpha mask on Pages.
   window.__LEAF_REGISTRY_CHROMA__?.apply(avatar,avatar.getAttribute('src'));
   avatar.decoding='async';
   portrait.append(avatar);
   const info=document.createElement('div');info.className='battle-side-info';
   const nick=document.createElement('b');nick.textContent=p.name;
   const attrs=document.createElement('small');
   attrs.textContent=p.jail>0?'감옥 '+p.jail+'턴':(p.position+1)+'칸 · '+p.ability+'%';
   const meter=document.createElement('i');meter.className='battle-side-meter';
   meter.style.width=Math.max(0,Math.min(100,p.ability))+'%';
   info.append(nick,attrs,meter);
   card.append(portrait,info);
   card.title=(i+1)+'P '+p.name+' · '+attrs.textContent;
  }else{
   card.setAttribute('aria-label',(i+1)+'번 빈 참가자 슬롯');
  }
  (i%2===0?left:right).append(card);
 }
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
 const cameraView=window.__LEAF_CAMERA__?.getState().visible;
 if(cameraView){
  // Real source-camera DMP viewport, not a static guessed minimap box.
  const x=7+cameraView.x*(w-14),y=10+cameraView.y*(h-17);
  const viewW=cameraView.width*(w-14),viewH=cameraView.height*(h-17);
  context.save();
  context.fillStyle='rgba(74,225,246,.12)';
  context.strokeStyle='#b0f3f8';
  context.lineWidth=1.3;
  context.setLineDash([3,2]);
  context.fillRect(x,y,viewW,viewH);
  context.strokeRect(x+.5,y+.5,Math.max(1,viewW-1),Math.max(1,viewH-1));
  context.restore();
 }
 match.players.forEach(p=>{
   const point=PATH[p.position]||PATH[0];if(!point)return;
   const x=7+point.x/100*(w-14),y=10+point.y/100*(h-17);
   context.beginPath();context.arc(x,y,4,0,Math.PI*2);
   context.fillStyle=p.color;context.fill();
   context.lineWidth=1;context.strokeStyle='#131c4f';context.stroke();
 });
}
/* Original archived board.jpg/battle.jpg place four CHESSMAN headshots in a
   genuine bottom-right 2x2 pane. Drive them from the SAME current party used
   by the 2002-era battle rules, not from fabricated preview characters.
   CardData/chm_NN PNGs are the recovered source portrait images. */
function drawNativeChessmen(){
 const root=$('dice-native-party'),toggle=$('dice-items-toggle');
 if(!root||!match)return;
 const p=(match.mode==='hotseat'||match.mode==='network'?activePlayer():match.players[0]);
 if(!p)return;
 const sameUser=root.dataset.playerId===String(p.id);
 const selectedIndex=sameUser?Number(root.dataset.selectedIndex)||0:0;
 root.replaceChildren();
 root.dataset.playerId=String(p.id);
 root.dataset.selectedIndex=String(selectedIndex);
 root.dataset.playerName=p.name;
 for(let i=0;i<4;i++){
  const cardId=p.team?.[i],source=cardId&&CARD_MAP[cardId],role=['공격','방어','지력','대기'][i];
  const slot=document.createElement(source?'button':'div');
  slot.className='dice-chessman-slot'+(source?' occupied':' vacant')+(i===3?' reserve':'');
  slot.dataset.teamIndex=String(i);
  slot.dataset.cardId=source?source.id:'';
  slot.setAttribute('aria-label',source?(role+' '+source.name+' 체스맨 정보'):(role+' 비어 있음'));
  if(source){
   slot.type='button';
   slot.title=role+' · '+source.name+' / 이동 '+source.move+' 공격 '+source.atk+' 방어 '+source.def+' 지력 '+source.int;
   const img=document.createElement('img');
   img.className='dice-chessman-face';
   img.src=imageFor(source.id);
   img.alt=source.name;
   img.loading='eager';
   const stamp=document.createElement('span');stamp.className='dice-chessman-moon';
   stamp.setAttribute('aria-hidden','true');
   const name=document.createElement('b');name.textContent=source.name;
   slot.append(img,stamp,name);
   slot.classList.toggle('selected',selectedIndex===i);
   slot.onfocus=()=>{
    root.dataset.selectedIndex=String(i);
    root.querySelectorAll('.dice-chessman-slot').forEach(s=>s.classList.toggle('selected',s===slot));
   };
   slot.onclick=()=>{
    const content=document.createElement('div');
    const portrait=document.createElement('img');portrait.src=imageFor(source.id);
    portrait.alt=source.name;portrait.width=58;portrait.height=62;
    const detail=document.createElement('p');
    detail.textContent=role+' · '+source.name+' / 이동 '+source.move+' / 공격 '+source.atk+
      ' / 방어 '+source.def+' / 지력 '+source.int+' / '+(source.ability||'능력 없음')+
      ' / '+source.point+' POINT';
    content.append(portrait,detail);
    modal('체스맨 · '+source.name,content,[{label:'닫기',primary:true}]);
   };
  }else{
   const blank=document.createElement('span');
   blank.className='dice-chessman-empty';
   blank.textContent='—';
   const name=document.createElement('b');name.textContent=role+' 빈 슬롯';
   slot.append(blank,name);
  }
  root.append(slot);
 }
 // Source IMG/selector.png is a genuine four-action icon atlas. Historical
 // icon-to-action mapping is unverified: use safe existing game actions only,
 // and do NOT invent swapping combat roles or new attack mechanics.
 const occupied=[...root.querySelectorAll('button.dice-chessman-slot.occupied')];
 const inspect=$('dice-inspect-tool');
 if(inspect){
  inspect.disabled=occupied.length===0;
  inspect.onclick=()=>{
   const current=occupied.find(s=>s.dataset.teamIndex===root.dataset.selectedIndex)||occupied[0];
   current?.click();
  };
 }
 const next=$('dice-next-tool');
 if(next){
  next.disabled=occupied.length<2;
  next.onclick=()=>{
   const idx=occupied.findIndex(s=>s.dataset.teamIndex===root.dataset.selectedIndex);
   const item=occupied[(idx+1)%occupied.length];
   item?.focus();
  };
 }
 const abilityTool=$('dice-ability-tool');
 if(abilityTool){
  abilityTool.disabled=$('ability-btn')?.disabled!==false;
  abilityTool.onclick=()=>{
   const ability=$('ability-btn');
   if(ability&&!ability.disabled)ability.click();
  };
 }
 const counter=$('dice-item-count');
 if(counter)counter.textContent=String(p.items?.length||0);
 if(toggle){
  toggle.setAttribute('aria-expanded',String($('app')?.classList.contains('dice-items-open')));
  toggle.onclick=()=>{
   const app=$('app');app.classList.toggle('dice-items-open');
   toggle.setAttribute('aria-expanded',String(app.classList.contains('dice-items-open')));
  };
 }
}
function drawGame(){if(!match||!MAPS[match.map])return;chooseSourcePath(match.map);
 const controllingOpponent=match.mode==='ai'&&match.botAutoplay===false;
 const p=(match.mode==='hotseat'||match.mode==='network'||controllingOpponent?activePlayer():match.players[0]),stats=teamStats(p.team);
 const toggle=$('dice-ai-autoplay-toggle');
 if(toggle){
  const ai=match.mode==='ai'&&!match.finished;
  toggle.hidden=!ai;
  toggle.textContent=match.botAutoplay?'AI 자동진행: 켜짐':'AI 자동진행: 일시정지';
  toggle.setAttribute('aria-pressed',String(ai&&match.botAutoplay===true));
  toggle.title=match.botAutoplay?'컴퓨터 상대의 자동 주사위 턴을 일시정지합니다.':
   '상대방 턴을 직접 주사위 굴리기로 진행합니다. 눌러 자동 진행을 다시 켤 수 있습니다.';
 }
 const roll=$('roll-btn');
 if(roll){
  const manualBot=controllingOpponent&&activePlayer()?.bot;
  roll.setAttribute('aria-label',manualBot?activePlayer().name+'의 주사위 직접 굴리기':'주사위 굴리기');
  roll.title=manualBot?'컴퓨터 상대의 이번 턴도 사용자가 직접 굴립니다.':
   match.finished?'경기가 끝났습니다. 대기실에서 새 게임을 시작하세요.':
   busy?'현재 주사위와 칸 이벤트 처리 중입니다.':
   match.mode==='network'&&!playerCanAct()?'상대 연결 또는 자신의 차례를 기다리세요.':
   '이번 참가자의 주사위를 굴립니다.';
 }
$('game-map-title').textContent=match.map;const elapsed=Math.floor((Date.now()-(match.startedAt||Date.now()))/1000);$('mini-time').textContent='TIME '+formatGameDuration(Math.max(0,elapsed))+' / GP '+formatGameDuration(match.players.length*90);$('element-label').textContent=match.attribute;$('player-count').textContent=match.players.length;$('turn-indicator').textContent='ROUND '+match.round+' · '+match.players[match.active].name+' TURN';$('my-name').textContent=p.name;$('my-stats').textContent='이동 '+stats.move+' · 공격 '+stats.atk+' · 방어 '+stats.def+' · 지력 +'+stats.int;$('my-position').textContent=p.jail>0?'감옥 '+p.jail+'턴':p.position===0?'START':p.position===match.tiles.length-1?'GOAL':(p.position+1)+'번째 칸';$('my-portrait').innerHTML='<img class="player-sprite" alt="" src="'+imageFor(p.team[0]||'soldier')+'">';$('ability-fill').style.width=p.ability+'%';$('game-players').replaceChildren();match.players.forEach((user,i)=>{const li=document.createElement('div');li.className=match.active===i?'is-turn':'';li.textContent=(match.active===i?'▶ ':'　')+user.pawn+' '+user.name+' '+(user.position+1)+'칸 · '+user.ability+'%';li.style.color=user.color;$('game-players').append(li)});$('my-items').replaceChildren();p.items.forEach((itemId,i)=>{const item=ITEM_MAP[itemId],btn=document.createElement('button');btn.className='item-card';btn.innerHTML='<span class="item-icon">'+(item?.icon||'✧')+'</span>'+(item?.name||itemId);btn.title=item.hint;btn.disabled=match.finished||!playerCanAct()||p.usedItem||busy;btn.onclick=()=>useItem(i);$('my-items').append(btn)});$('roll-btn').disabled=!playerCanAct();$('ability-btn').disabled=!playerCanAct()||p.ability<100;$('move-log').textContent=match.message;syncNativeDiceEvent(match.message);drawBoard();drawBattlePanels();drawNativeChessmen();drawMinimap();trackActivePawn()}
// An 800px native client camera at 125% fills only a few gigantic tiles
// on a 390px phone. Preserve each 145x97 native TIS sprite and 70x47 DMP
// pitch, but show a wider source-world slice at game start on small screens.
// This is a responsive WEB camera convention, not a recovered EXE setting.
function defaultDiceCameraZoom(){
 const area=$('board-area');
 return area&&area.clientWidth>0&&area.clientWidth<520?.65:1;
}
const mapViewport={zoom:1,panX:0,panY:0,autoFollow:true,lastTurn:null,matchKey:null};
function trackActivePawn(){
 if(!match||!PATH.length)return;
 // Follow a genuine new participant or new match, not on every UI repaint.
 if(mapViewport.matchKey!==match.startedAt||mapViewport.lastTurn!==match.active){
  if(mapViewport.matchKey!==match.startedAt)mapViewport.zoom=defaultDiceCameraZoom();
  mapViewport.autoFollow=true;mapViewport.panX=0;mapViewport.panY=0;
  mapViewport.matchKey=match.startedAt;mapViewport.lastTurn=match.active;
 }
 if(window.__LEAF_CAMERA__){
  // Follow means keep the actual active pawn at the camera's source anchor.
  // A clamped offset from the previous pawn position is NOT a manual pan;
  // otherwise same-turn movement slowly slides the real pawn off-centre.
  if(mapViewport.autoFollow)window.__LEAF_CAMERA__.viewport(mapViewport.zoom,0,0);
  window.__LEAF_CAMERA__.sync(match,PATH);
  const actual=window.__LEAF_CAMERA__.getState();
  mapViewport.panX=actual.panX;mapViewport.panY=actual.panY;
  return;
 }
 if(!mapViewport.autoFollow||!match||!PATH.length)return;
 const area=$('board-area'),p=activePlayer(),pos=PATH[p.position];if(!pos)return;
 const w=area.clientWidth,h=area.clientHeight,z=mapViewport.zoom;
 const maxX=w*(z-1)/2,maxY=h*(z-1)/2;
 mapViewport.panX=Math.max(-maxX,Math.min(maxX,(50-pos.x)*(w*.76)*z/100));
 mapViewport.panY=Math.max(-maxY,Math.min(maxY,(50-pos.y)*h*z/100));
 applyMapViewport();
}
function applyMapViewport(){
 if(window.__LEAF_CAMERA__){
  const view=window.__LEAF_CAMERA__.viewport(mapViewport.zoom,mapViewport.panX,mapViewport.panY);
  mapViewport.panX=view.panX;mapViewport.panY=view.panY;
  return;
 }
 const world=$('board-world');if(!world)return;
 world.style.transform='translate('+mapViewport.panX+'px,'+mapViewport.panY+'px) scale('+mapViewport.zoom+')';
 const label=$('board-zoom-reset');if(label)label.title='맵 배율 '+Math.round(mapViewport.zoom*100)+'% · 중앙으로 복귀';
}
function zoomBoard(by){
 mapViewport.zoom=Math.max(.65,Math.min(2.4,Math.round((mapViewport.zoom+by)*100)/100));
 if(mapViewport.zoom===1){mapViewport.panX=0;mapViewport.panY=0}
 // Source game zoom buttons must change the real shared world scale even
 // while follow-camera is enabled. Calling sync() alone kept the previous
 // scale forever until a manual drag disabled follow.
 applyMapViewport();
 if(mapViewport.autoFollow)trackActivePawn();
}
function installBoardControls(){
 $('board-zoom-in').onclick=()=>zoomBoard(.25);
 $('board-zoom-out').onclick=()=>zoomBoard(-.25);
 $('board-zoom-reset').onclick=()=>{mapViewport.zoom=defaultDiceCameraZoom();mapViewport.panX=0;mapViewport.panY=0;mapViewport.autoFollow=true;applyMapViewport();trackActivePawn()};
 const area=$('board-area');
 const minimap=$('mini-map-canvas');
 // Native IMG/minimap.png is backed by a genuine 152x112 game canvas,
 // but the original revival disabled interaction. Keep the source art and
 // bind map clicks to the actual full-size recovered DMP camera.
 let draggingMinimap=null;
 function focusMiniPoint(rx,ry){
  if(!match||route!=='game'||!window.__LEAF_CAMERA__?.focusRatio)return null;
  mapViewport.autoFollow=false;
  const view=window.__LEAF_CAMERA__.focusRatio(
   Math.max(0,Math.min(1,rx)),Math.max(0,Math.min(1,ry)));
  mapViewport.panX=view.panX;mapViewport.panY=view.panY;
  return view;
 }
 const readMiniPointer=e=>{
  const b=minimap.getBoundingClientRect();
  if(!b.width||!b.height)return null;
  const x=(e.clientX-b.left)/b.width*minimap.width;
  const y=(e.clientY-b.top)/b.height*minimap.height;
  return [(x-7)/(minimap.width-14),(y-10)/(minimap.height-17)];
 };
 minimap.tabIndex=0;
 minimap.setAttribute('role','button');
 minimap.setAttribute('aria-label',
  '원본 주잔 미니맵 · 클릭 또는 드래그로 DMP 카메라 탐색, 방향키 이동, Home 현재 체스맨 추적');
 minimap.setAttribute('aria-keyshortcuts','ArrowUp ArrowDown ArrowLeft ArrowRight Home');
 minimap.addEventListener('pointerdown',e=>{
  if(e.pointerType==='mouse'&&e.button!==0)return;
  const point=readMiniPointer(e);if(!point)return;
  e.preventDefault();e.stopPropagation();
  draggingMinimap=e.pointerId;
  try{minimap.setPointerCapture(e.pointerId)}catch{}
  focusMiniPoint(...point);
 });
 minimap.addEventListener('pointermove',e=>{
  if(draggingMinimap!==e.pointerId)return;
  const point=readMiniPointer(e);if(point)focusMiniPoint(...point);
 });
 const releaseMini=e=>{
  if(draggingMinimap===e.pointerId)draggingMinimap=null;
 };
 for(const type of ['pointerup','pointercancel','lostpointercapture'])
  minimap.addEventListener(type,releaseMini);
 minimap.addEventListener('keydown',e=>{
  if(e.target!==minimap||route!=='game')return;
  if(e.key==='Home'||e.key==='0'){
   e.preventDefault();
   mapViewport.autoFollow=true;
   mapViewport.panX=mapViewport.panY=0;
   trackActivePawn();return;
  }
  const delta={ArrowLeft:[-.08,0],ArrowRight:[.08,0],
   ArrowUp:[0,-.08],ArrowDown:[0,.08]}[e.key];
  if(!delta)return;
  e.preventDefault();
  const view=window.__LEAF_CAMERA__?.getState().visible;
  if(view)focusMiniPoint(view.x+view.width/2+delta[0],
   view.y+view.height/2+delta[1]);
 });
 window.__LEAF_MINIMAP_NAV__={
  focus:focusMiniPoint,
  onCameraRender:()=>{if(route==='game'&&match)drawMinimap()},
  getState:()=>({
   source:'IMG/minimap.png',canvas:[minimap.width,minimap.height],
   isVisible:getComputedStyle(minimap).pointerEvents!=='none'&&
    minimap.getBoundingClientRect().width>0,
   follow:mapViewport.autoFollow,
   camera:window.__LEAF_CAMERA__?.getState()||null
  })
 };
 // 1450x1120 actual DMP route may be explored at ANY source zoom. The old
 // zoom-only clamp prevented travel beyond a small rectangle of the board.
 const pointers=new Map();let dragging=null,pinch=null;
 const distance=()=>{
  const [a,b]=[...pointers.values()];
  return a&&b?Math.hypot(a.x-b.x,a.y-b.y):0;
 };
 // Original TIS cells are accessible [role=button] but also the actual
 // pan/zoom surface. Only overlay controls block world camera interactions.
 const blocked=e=>Boolean(e.target.closest(
  '#board-zoom-controls,#board-mini,.board-mini,button,input,textarea,select,#battle-visual,#battle-player-panels,[role="button"]:not(.tile):not(.board-pawn)'));
 const pan=(dx,dy)=>{
  mapViewport.autoFollow=false;
  if(window.__LEAF_CAMERA__?.panBy){
   const view=window.__LEAF_CAMERA__.panBy(dx,dy);
   mapViewport.panX=view.panX;mapViewport.panY=view.panY;
  }else{
   mapViewport.panX+=dx;mapViewport.panY+=dy;applyMapViewport();
  }
 };
 area.tabIndex=0;
 area.setAttribute('aria-label','원본 주잔 지형: 드래그로 탐색, 휠 확대, 방향키 이동, 0키 캐릭터 추적');
 area.addEventListener('pointerdown',e=>{
  if((e.pointerType==='mouse'&&e.button!==0)||blocked(e))return;
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size===1){
   dragging={id:e.pointerId,x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,moved:false};
  }else if(pointers.size===2){
   pinch={distance:distance(),zoom:mapViewport.zoom};dragging=null;
   for(const id of pointers.keys())try{area.setPointerCapture(id)}catch{}
  }
 });
 area.addEventListener('pointermove',e=>{
  if(!pointers.has(e.pointerId))return;
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size>=2){
   if(!pinch)pinch={distance:distance(),zoom:mapViewport.zoom};
   if(pinch.distance>8){
    mapViewport.zoom=Math.max(.65,Math.min(2.4,
     Math.round(pinch.zoom*distance()/pinch.distance*100)/100));
    mapViewport.autoFollow=false;applyMapViewport();
   }
   return;
  }
  if(!dragging||dragging.id!==e.pointerId)return;
  if(!dragging.moved&&Math.hypot(e.clientX-dragging.startX,e.clientY-dragging.startY)<5)return;
  if(!dragging.moved){
   dragging.moved=true;try{area.setPointerCapture(e.pointerId)}catch{}
  }
  const dx=e.clientX-dragging.x,dy=e.clientY-dragging.y;
  dragging.x=e.clientX;dragging.y=e.clientY;
  pan(dx,dy);
 });
 function release(e){
  pointers.delete(e.pointerId);
  if(pointers.size<2)pinch=null;
  if(pointers.size===1){
   const [id,p]=[...pointers.entries()][0];
   dragging={id,x:p.x,y:p.y,startX:p.x,startY:p.y,moved:false};
  }else dragging=null;
 }
 for(const kind of ['pointerup','pointercancel','lostpointercapture'])
  area.addEventListener(kind,release);
 area.addEventListener('wheel',e=>{
  if(blocked(e))return;
  e.preventDefault();zoomBoard(e.deltaY<0?.2:-.2);
 },{passive:false});
 area.addEventListener('keydown',e=>{
  if(e.target!==area)return;
  const move={ArrowLeft:[48,0],ArrowRight:[-48,0],
   ArrowUp:[0,48],ArrowDown:[0,-48]}[e.key];
  if(move){e.preventDefault();pan(...move);return}
  if(e.key==='+'||e.key==='='){e.preventDefault();zoomBoard(.25)}
  else if(e.key==='-'){e.preventDefault();zoomBoard(-.25)}
  else if(e.key==='0'){
   e.preventDefault();mapViewport.zoom=defaultDiceCameraZoom();
   mapViewport.panX=mapViewport.panY=0;
   mapViewport.autoFollow=true;applyMapViewport();trackActivePawn();
  }
 });
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
 // Verified six native 2002 winAbility.spr frames, shown only on a real
 // authorized cast. Layout duration is inferred; game logic is not.
 window.__LEAF_ORIGINAL_ABILITY__?.show(p.name,stats.ability);
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
   const actor=document.createElement('div');
   actor.className='battle-visual-actor board-pawn leaf-battle-chessman';
   actor.setAttribute('role','img');
   actor.setAttribute('aria-label',player.name+' · 전투 체스맨');
   if(player.team?.length){
     // The actual player's Genesis chessman is also the duel actor.
     // The original full-body model is not in the recovered archive;
     // share the existing inferred rig/poses, not unrelated 4LEAF avatars.
     window.__LEAF_GENESIS_ACTORS__?.mount(actor,player,imageFor(player.team[0]));
     window.__LEAF_GENESIS_ACTORS__?.pose(actor,
       panel.classList.contains('attacker')?'attack':'hurt',850);
   }else{
     // Keeper mesh is not recovered. Do not impersonate it with savaNN.
     const placeholder=document.createElement('span');
     placeholder.className='leaf-unrecovered-keeper';
     placeholder.textContent='KEEPER';
     actor.append(placeholder);
     actor.dataset.actorOriginalModelRecovered='false';
   }
   const title=document.createElement('strong');title.textContent=player.name;
   const score=document.createElement('div');score.className='battle-visual-total';score.textContent=String(result).padStart(2,'0');
   const dice=document.createElement('div');dice.className='battle-visual-dice';
   // Archived board.jpg and battle.jpg display real six-sided dice with
   // visible pip topology, not operating-system Unicode dice characters.
   // These are independent live faces whose pips come ONLY from the actual
   // rolled combat arrays; there are no pasted screenshots or fake results.
   const pipCells={1:[5],2:[1,9],3:[1,5,9],
    4:[1,3,7,9],5:[1,3,5,7,9],6:[1,3,4,6,7,9]};
   values.forEach(eye=>{
    const value=Math.min(6,Math.max(1,Number(eye)||1));
    const die=document.createElement('span');die.className='battle-visual-die';
    die.dataset.eye=String(value);
    die.dataset.source='archived-battle-photo-inferred-3d-pips';
    die.setAttribute('role','img');
    die.setAttribute('aria-label','주사위 '+value+'눈');
    die.title='실제 굴림 '+value;
    for(const cell of pipCells[value]){
     const dot=document.createElement('i');
     dot.className='battle-die-pip';
     dot.dataset.cell=String(cell);
     dot.setAttribute('aria-hidden','true');
     dot.style.gridColumn=String((cell-1)%3+1);
     dot.style.gridRow=String(Math.floor((cell-1)/3)+1);
     die.append(dot);
    }
    dice.append(die);
   });
   const pedestal=document.createElement('div');pedestal.className='battle-visual-pedestal';
   // Keep fallback geometry available only if the verified archived
   // winBattle.spr PNG fails to load; the native image supersedes it
   // automatically when 355x113 source pixels are ready.
   pedestal.dataset.geometrySource='fallback-only-source-if-missing';
   for(let legIndex=0;legIndex<4;legIndex++){
     const support=document.createElement('span');
     support.className='leaf-battle-platform-leg leaf-battle-platform-leg-'+legIndex;
     support.setAttribute('aria-hidden','true');
     pedestal.append(support);
   }
   const crossbar=document.createElement('span');
   crossbar.className='leaf-battle-platform-crossbar';
   crossbar.setAttribute('aria-hidden','true');
   pedestal.append(crossbar);
   panel.append(title,score,actor,pedestal,dice);
 }
 assemble(left,attacker,attackerPoints,attack.values);assemble(right,defender,defenderPoints,defense.values);
 const vs=document.createElement('div');vs.className='battle-visual-vs';vs.textContent='VS';
 // VERIFIED ARCHIVE SOURCE: Dice/IMG.pak winBattle.spr frame 1 is
 // the *actual* original 355x113 metal dual podium + red VS graphic,
 // not an invented CSS 4-legged platform or a pasted game screenshot.
 // The independently rendered participant sprites, names, live pip
 // results, combat state and game engine remain interactive entities.
 const nativePodiums=document.createElement('img');
 nativePodiums.className='leaf-native-winbattle-podiums';
 nativePodiums.src='./original/SourceSPRExtra/winBattle-01.png';
 nativePodiums.alt='';
 nativePodiums.draggable=false;
 nativePodiums.dataset.originalSourceMember='Dice/IMG.pak:winBattle.spr';
 nativePodiums.dataset.originalFrame='1';
 const nativeHeading=document.createElement('img');
 nativeHeading.className='leaf-native-winbattle-heading';
 nativeHeading.src='./original/SourceSPRExtra/winBattle-00.png';
 nativeHeading.alt='';nativeHeading.draggable=false;
 nativeHeading.dataset.originalSourceMember='Dice/IMG.pak:winBattle.spr';
 nativeHeading.dataset.originalFrame='0';
 stage.dataset.nativeBattlePodium='loading';
 nativePodiums.addEventListener('load',()=>{
  if(!stage.isConnected)return;
  stage.dataset.nativeBattlePodium=nativePodiums.naturalWidth===355&&
   nativePodiums.naturalHeight===113?'ready':'fallback';
 });
 nativePodiums.addEventListener('error',()=>{
  if(stage.isConnected)stage.dataset.nativeBattlePodium='fallback';
 });
 nativeHeading.addEventListener('load',()=>{
  if(stage.isConnected&&nativeHeading.naturalWidth===222&&
    nativeHeading.naturalHeight===42)
    stage.dataset.nativeBattleHeading='ready';
 });
 nativeHeading.addEventListener('error',()=>{
  if(stage.isConnected)stage.dataset.nativeBattleHeading='fallback';
 });
 stage.append(nativePodiums,nativeHeading,head,left,vs,right);
 area.append(stage);
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
 // Source: actual final-service 2004 screenshot and commentary archived by
 // 4LEAF Memorial (https://4leafmemorial.tistory.com/1577 ,
 // "주사위의 잔영 - 철가면 vs 데미안 이벤트", 2013-03-15).
 // Ironmask Destroy and Damian Block each force EXACTLY 24. The native
 // game cancels both abilities when they clash; the old reconstruction
 // blindly rolled the same unavoidable 24:24 draw one hundred times.
 let neutralizedFixed=false;
 for(let attempt=0;attempt<100;attempt++){
   attack=diceN(aCount,6);defense=diceN(bCount,6);
   aValue=attack.total+(aStat.int||0)+(attacker.team?.length>=3?(attacker.effects?.ring||0):0)+(attacker.effects?.teamInt>0?3:0)+elementalModifier(attacker.team,'attack')+elementalModifier(attacker.team,'support');
   bValue=defense.total+(bStat.int||0)+(defender.team?.length>=3?(defender.effects?.ring||0):0)+(defender.effects?.teamInt>0?3:0)+(keeper?0:elementalModifier(defender.team,'defense')+elementalModifier(defender.team,'support'));
   if(attacker.effects?.scar>0)aValue=Math.max(1,aValue-attacker.effects.scar);
   if(defender.effects?.scar>0)bValue=Math.max(1,bValue-defender.effects.scar);
   if(attacker.effects?.ultimate>0)aValue=30;
   if(defender.effects?.ultimate>0)bValue=18;
   if(attacker.effects?.destroy>0)aValue=24;
   if(defender.effects?.block>0)bValue=24;
   // Do NOT keep re-rolling two deterministically fixed faces. Only the
   // demonstrated Destroy-vs-Block pair triggers historic cancellation.
   if(!keeper&&aValue===24&&bValue===24&&
      attacker.effects?.destroy>0&&defender.effects?.block>0){
     attacker.effects.destroy=0;defender.effects.block=0;
     neutralizedFixed=true;
     rerolls++;
     continue;
   }
   if(aValue!==bValue)break;rerolls++;
 }
 const div=document.createElement('div');
 div.innerHTML='<p>'+attacker.name+'의 공격! '+defender.name+'이(가) 방어합니다.'+
 (neutralizedFixed?' · DESTROY/BLOCK 24:24 상쇄! 양측 강제 능력 무효화':'')+
 (rerolls?' · 무승부 '+rerolls+'회 재굴림':'')+'</p><div class="battle-dice"><div>ATTACK<div class="nums">'+attack.values.join('·')+'</div><b>'+aValue+'</b><small>지력 +'+aStat.int+'</small></div><div>DEFENSE<div class="nums">'+defense.values.join('·')+'</div><b>'+bValue+'</b><small>지력 +'+bStat.int+'</small></div></div>';
 const battleStage=showBattleScene(attacker,defender,attack,defense,aValue,bValue);
 // The native 2004 battle stage must remain unobstructed. Keep the
 // SINGLE authoritative modal-buttons element and the original callbacks,
 // but display it in an independent tray at the bottom of the real game
 // canvas rather than overlaying the genuine winBattle.spr podium and VS.
 const battleActions=document.createElement('div');
 battleActions.className='leaf-native-battle-actions';
 battleActions.setAttribute('role','group');
 battleActions.setAttribute('aria-label','실제 전투 결과 및 전투 카드');
 const modalButtons=$('modal-buttons');
 const modalButtonsParent=modalButtons.parentElement;
 const finish=result=>{
   remoteBattle=null;
   if(modalButtons.parentElement===battleActions)modalButtonsParent.append(modalButtons);
   battleActions.remove();
   battleStage?.remove();
   $('modal').classList.remove('battle-present');
   resolve({...result,neutralizedFixed});
 };
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
 modal('⚔ BATTLE · 전투',div,options);
 $('modal').classList.add('battle-present');
 battleActions.append(modalButtons);
 $('board-area').append(battleActions);
 sfx(235,.21);
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
 window.__LEAF_GENESIS_ACTORS__?.poseByPlayer(attacker.id,'attack',800);
 if(!keeper)window.__LEAF_GENESIS_ACTORS__?.poseByPlayer(defender.id,'hurt',650);
 const result=await combat(attacker,defender,keeper);
 if(result.neutralizedFixed)appendMove('철가면 DESTROY 24 ↔ 데미안 BLOCK 24 · 능력 충돌 무효화 후 정상 주사위 재굴림');
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
 else if(type==='prison'){p.jail=3;appendMove(p.name+' 감옥 3턴! 더블 주사위로 탈출할 수 있습니다.');window.__LEAF_NATIVE_EVENTS__?.show('jail',p.name)}
 else if(type==='kingbomb'){p.position=0;appendMove(p.name+' 왕폭탄 폭발! START 복귀');match.tiles[pos]='normal'}
 else if(type==='keeperA'||type==='keeperB'||type==='keeperC'){const power={keeperA:1,keeperB:3,keeperC:5};await resolveBattle(p,{id:-1,name:ITEM_MAP[type].name,def:power[type]},true);match.tiles[pos]='normal'}
 else if(type==='ability'){p.ability=Math.min(100,p.ability+25);appendMove(p.name+' 어빌리티 게이지 +25%');if(p.ability===100)window.__LEAF_NATIVE_EVENTS__?.show('ability',p.name)}
 else if(type==='ability100'){
   const ts=teamStats(p.team),count=Math.max(1,Math.min(4,p.team?.length>=3?ts.int:(p.team?.length===2?ts.def:ts.atk)));
   const targets=Array.from({length:6},(_,i)=>i+1).sort(()=>Math.random()-.5).slice(0,count);
   const eye=d(6);
   if(targets.includes(eye)){p.ability=100;appendMove(p.name+' 소울풀 판정 '+eye+' / 목표 '+targets.join(',')+' · 어빌리티 100%!');window.__LEAF_NATIVE_EVENTS__?.show('ability',p.name)}
   else appendMove(p.name+' 소울풀 판정 '+eye+' / 목표 '+targets.join(',')+' · 실패');
 }
 else if(type==='attribute'){match.attribute=originalTileAt(match.map,pos)?.attribute||['WANDS','SWORDS','CUPS','DISKS'][rand(4)];appendMove('맵 속성이 '+match.attribute+'(으)로 변경!')}
 else if(type==='clover'){p.effects.clover=1;p.effects.spade=0;appendMove(p.name+' 클로버: 다음 주사위는 높은 눈')}
 else if(type==='spade'){p.effects.spade=1;p.effects.clover=0;appendMove(p.name+' 스페이드: 다음 주사위는 낮은 눈')}
 else if(type==='doa'){
   const first=d(6),second=d(first),diff=first-second;
   if(diff>=3)p.position=0;else p.position=Math.max(0,p.position-diff*3);
   appendMove(p.name+' DEAD OR ALIVE: '+first+' / '+second+' → '+(diff>=3?'START':diff*3+'칸 후퇴'));
   // Source-authentic winDoa.spr graphic, independent of rolled eyes.
   window.__LEAF_NATIVE_EVENTS__?.show('doa',p.name);
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
function calculateMatchReward(winner,m=match,now=Date.now()){
 const participants=Math.max(2,Math.min(8,m?.players?.length||2));
 const duration=Math.max(0,now-(Number.isFinite(m?.startedAt)?m.startedAt:now));
 const required=participants*90000;
 const historicalBase=m?.map==='4LEAF'?49:m?.map==='워프 게이트'?29:null;
 const estimated=historicalBase===null;
 const fullReward=(historicalBase??29)+Math.max(0,participants-2)*10;
 const percent=winner?.id===0?1:Math.min(1,Math.max(0,(m?.players?.[0]?.position||0)/Math.max(1,(m?.tiles?.length||1)-1)));
 const eligible=duration>=required;
 return {gp:eligible?Math.floor(fullReward*percent):0,eligible,seconds:Math.floor(duration/1000),minimumSeconds:participants*90,fullReward,estimated};
}
function formatGameDuration(seconds){return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')}
/* Actual source IMG.pak winResult.spr gives the native 452x88
 * RESULT / PLAYER / CL / COMPLETE / GP / WIN RATE headings.
 * Rows remain live match entities, NOT a pasted screenshot. Historical
 * CL and lifetime win-rate protocols are NOT decoded: show a dash rather
 * than fabricating historical values. Player progress and awarded GP
 * come exclusively from the real current match state.
 */
function nativeMatchResult(winner,rewardInfo,reward){
 const panel=document.createElement('section');
 panel.id='leaf-original-match-result';
 panel.className='leaf-original-match-result';
 panel.dataset.originalMember='Dice/IMG.pak:winResult.spr';
 panel.dataset.originalFrame='0';
 panel.dataset.sourceLayout='source-header/WEB-inferred-data-rows';
 panel.dataset.nativeResult='loading';
 const header=document.createElement('img');
 header.className='leaf-original-result-heading';
 header.src='./original/SourceSPRExtra/winResult-00.png';
 header.alt='';header.draggable=false;
 header.addEventListener('load',()=>{
  if(!panel.isConnected)return;
  panel.dataset.nativeResult=header.naturalWidth===452&&
   header.naturalHeight===88?'ready':'fallback';
 });
 header.addEventListener('error',()=>{
  if(panel.isConnected)panel.dataset.nativeResult='fallback';
 });
 panel.append(header);
 const table=document.createElement('table');
 table.className='leaf-original-result-table';
 const heading=document.createElement('thead'),headRow=document.createElement('tr');
 for(const label of ['PLAYER','CL','COMPLETE','GP','WIN RATE']){
  const th=document.createElement('th');th.scope='col';th.textContent=label;headRow.append(th);
 }
 heading.append(headRow);table.append(heading);
 const body=document.createElement('tbody');
 const finish=Math.max(1,(match?.tiles?.length||1)-1);
 for(const player of match?.players||[]){
  const row=document.createElement('tr');row.dataset.playerId=String(player.id);
  if(player.id===winner.id)row.className='leaf-original-result-winner';
  const percentage=Math.round(Math.max(0,Math.min(100,player.position/finish*100)));
  const cells=[player.name,'—',percentage+'%',
   player.id===winner.id?String(reward):'0','—'];
  cells.forEach((value,index)=>{
   const td=document.createElement('td');td.textContent=value;
   td.dataset.col=['player','cl','complete','gp','win-rate'][index];
   row.append(td);
  });
  body.append(row);
 }
 table.append(body);panel.append(table);
 const details=document.createElement('p');
 details.className='leaf-original-result-description';
 details.textContent=winner.name+' 승리!　획득 GP +'+reward.toLocaleString()+
  ' · 플레이 '+formatGameDuration(rewardInfo.seconds)+
  ' / GP 지급 '+formatGameDuration(rewardInfo.minimumSeconds)+
  (rewardInfo.eligible?'':' · 최소 시간이 충족되지 않아 GP 0')+
  (rewardInfo.estimated?' · ※ 이 맵의 기본 GP는 추정치':'')+
  ' · 게임을 다시 시작할 수 있습니다.';
 panel.append(details);
 return panel;
}
function finishGame(winner){match.finished=true;match.winner=winner.id;match.message=winner.name+'이(가) GOAL에 도착했습니다!';const rewardInfo=calculateMatchReward(winner);const reward=rewardInfo.gp;profile.gp+=reward;if(winner.id===0)profile.wins++;profileUI();persist();chat('SYSTEM',winner.name+'님이 가장 먼저 GOAL에 도착했습니다! GP +'+reward,'system');modal('✦ 주사위의 잔영 · 게임 종료',nativeMatchResult(winner,rewardInfo,reward),[{label:'다시 시작',primary:true,run:()=>navigate('lobby')},{label:'결과 보기',run:()=>drawGame()}]);sfx(925,.4)}
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
function showDice(values){
 const faces=['⚀','⚁','⚂','⚃','⚄','⚅'];
 $('die1').textContent=faces[Math.min(5,values[0]-1)];
 $('die2').textContent=values.length>1?faces[Math.min(5,values[1]-1)]:'·';
 // These are the ACTUALLY rolled gameplay eyes, not a simulated animation.
 if(match)match.lastRoll=values.slice();
 const box=$('dice-box');
 if(box){
  box.dataset.rollCount=String((Number(box.dataset.rollCount)||0)+1);
  box.setAttribute('role','status');
  box.setAttribute('aria-label','주사위 결과 '+values.join(' + '));
  box.classList.remove('dice-rolled');
  void box.offsetWidth;
  box.classList.add('dice-rolled');
 }
}
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
 busy=true;const p=match.players[match.active];
 try{
 drawGame();if(p.bot&&match.mode==='ai'&&match.botAutoplay===true){
  await wait(250);await computerPrepareTurn(p);if(match.finished){busy=false;return}
 }
 if(p.jail>0){
   const a=d(6),b=d(6);await window.__LEAF_DICE_FALL__?.roll([a,b],{sides:6});showDice([a,b]);
   if(a===b){p.jail=0;appendMove(p.name+' 감옥 탈출! 더블 '+a+'/'+b+' · 이동 턴 진행')}
   else{p.jail--;appendMove(p.name+' 감옥 '+p.jail+'턴 남음 (주사위 '+a+'/'+b+')');await wait(p.bot?300:150);busy=false;nextTurn();return}
 }
 const values=moveValues(p),attributeMoveBonus=elementalModifier(p.team,'move'),move=Math.max(1,values.reduce((a,b)=>a+b,0)+attributeMoveBonus);await window.__LEAF_DICE_FALL__?.roll(values,{sides:teamStats(p.team).move===2?4:6});showDice(values);
 p.ability=Math.min(100,p.ability+move*3);
 if(move){
   appendMove(p.name+' 이동 주사위 '+values.join('+')+(attributeMoveBonus>0?' +2':attributeMoveBonus<0?' −2':'')+' = '+move+'칸 ('+match.attribute+')');
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
 }catch(error){
  // A failed event/battle renderer must never lock the real roll control
  // permanently in the disabled busy state.
  busy=false;
  console.error('4LEAF game dice turn failed',error);
  const reason=String(error?.message||error||'알 수 없는 오류').slice(0,110);
  try{appendMove('주사위 처리 오류 · '+reason+' · 다시 시도하세요.');drawGame()}
  catch(drawError){console.error('4LEAF game error recovery failed',drawError);
   const button=$('roll-btn');if(button)button.disabled=false;}
 }
}
function nextTurn(){
 if(!match||match.finished)return;
 match.active=(match.active+1)%match.players.length;
 if(match.active===0)match.round++;
 const p=activePlayer();p.usedItem=false;
 drawGame();persist();
 if(p.bot&&match.mode==='ai'&&match.botAutoplay===true){
  const scheduledMatch=match;
  setTimeout(()=>{if(route==='game'&&match===scheduledMatch&&!busy&&!match.finished&&
   match.botAutoplay===true&&match.players[match.active].bot)takeTurn()},430);
 }
 else appendMove(p.name+' 차례입니다. 주사위를 굴리세요.');
}
/* Recovered Dice/IMG/menu.png contains two independent 29px game menu
   illustrations. Use those source sprites as real clickable controls while
   keeping old match and chessman logic unchanged. The original per-icon
   command mapping is unverified, so these are safe web-side actions only. */
function installNativeDiceMenu(){
 const menu=$('dice-menu-round'),party=$('dice-menu-party');
 if(menu)menu.onclick=()=>{
  if(!match)return;
  const current=activePlayer();
  const body=document.createElement('div');
  const info=document.createElement('p');
  info.textContent='맵 '+match.map+' · '+match.round+'라운드 · '+match.players.length+
    '명 · 현재 차례 '+(current?.name||'없음');
  body.append(info);
  const list=document.createElement('div');
  for(const p of match.players){
   const row=document.createElement('div');
   row.textContent=p.name+' · '+(p.position+1)+'번째 칸 · 어빌리티 '+p.ability+'%';
   list.append(row);
  }
  body.append(list);
  modal('현재 경기 정보',body,[{label:'닫기',primary:true}]);
 };
 if(party)party.onclick=()=>{
  if(!match)return;
  $('dice-inspect-tool')?.click();
 };
}
function toggleBotAutoplay(){
 if(!match||match.mode!=='ai'||match.finished)return;
 match.botAutoplay=!match.botAutoplay;
 const enabled=match.botAutoplay;
 drawGame();persist();
 appendMove(enabled?'컴퓨터 상대 자동 주사위: 켜짐':'컴퓨터 상대 자동 주사위: 일시정지 · 상대 턴도 직접 굴리세요.');
 if(enabled&&activePlayer()?.bot&&!busy){
  const scheduledMatch=match;
  setTimeout(()=>{if(route==='game'&&match===scheduledMatch&&!busy&&!match.finished&&
   match.botAutoplay===true&&activePlayer()?.bot)takeTurn()},430);
 }
}
function init(){installBoardControls();installNativeDiceMenu();
 const botToggle=$('dice-ai-autoplay-toggle');if(botToggle)botToggle.onclick=toggleBotAutoplay;
 installAuthenticMaps();if(match)chooseSourcePath(match.map);profileUI();buildRoomList();buildPeople();drawTeam();drawShop();query('[data-route]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.route)));query('.group-tab').forEach(b=>b.addEventListener('click',()=>{group=b.dataset.group;shopPage=0;drawShop()}));$('shop-prev').onclick=()=>{shopPage--;drawShop()};$('shop-next').onclick=()=>{shopPage++;drawShop()};$('point-limit').onchange=drawTeam;$('start-game').onclick=startGame;$('resume-game').onclick=()=>{if(match&&!match.finished){busy=false;navigate('game');chat('SYSTEM','진행 중인 게임을 이어합니다.','system')}};$('roll-btn').onclick=takeTurn;$('ability-btn').onclick=useAbility;$('exit-game').onclick=()=>modal('게임에서 나가기','진행 중인 게임은 브라우저에 보관됩니다. 나갔다가 주사위의 잔영 버튼으로 다시 들어올 수 있습니다.',[{label:'나가기',primary:true,run:()=>navigate('lobby')},{label:'취소'}]);$('shop-buy').onclick=()=>{const c=CARD_MAP[chosenCard];if(profile.owned.includes(c.id))return modal('매직카덴',c.name+' 카드는 이미 가지고 있습니다.',[{label:'확인'}]);if(profile.gp<c.price)return modal('매직카덴','GP가 부족합니다.',[{label:'확인'}]);modal('매직카덴',c.name+' 카드를 '+c.price.toLocaleString()+'GP에 구매하시겠습니까?',[{label:'구매',primary:true,run:()=>{profile.gp-=c.price;profile.owned.push(c.id);profileUI();drawShop();drawTeam();chat('매직카덴',c.name+' 카드를 구매했습니다.','system');sfx(830)}},{label:'취소'}])};$('shop-sell').onclick=()=>{
 const c=CARD_MAP[chosenCard];
 if(!shopCanSell(c)){
  modal('매직카덴','선택한 카드가 없거나, 출전·진행 중 경기·마지막 보유 카드이므로 판매할 수 없습니다.',[{label:'확인'}]);
  return;
 }
 const gp=inferredShopResaleGP(c);
 modal('매직카덴',c.name+' 카드를 판매하시겠습니까? 임시 판매가 '+
  gp.toLocaleString()+' GP (원작 재판매 가격 규칙 미확인).',[{label:'판매',primary:true,run:()=>{
   // Protect against double confirmation, intervening game state and
   // resale of a currently equipped/still active match chessman.
   if(!shopCanSell(c))return;
   profile.owned=profile.owned.filter(id=>id!==c.id);
   profile.gp+=gp;
   if(chosenCard===c.id)chosenCard=profile.owned[0]||BASE_CARDS[0]?.id;
   profileUI();drawShop();drawTeam();
   chat('매직카덴',c.name+' 카드 판매 · '+gp.toLocaleString()+' GP (임시 웹 판매 규칙).','system');
   sfx(600);
  }},{label:'취소'}]);
};$('rename').onclick=()=>{const div=document.createElement('div');div.textContent='사용할 닉네임을 입력하세요.';const input=document.createElement('input');input.maxLength=12;input.value=profile.name;div.append(document.createElement('hr'),input);modal('4LEAF 별명 변경',div,[{label:'변경',primary:true,run:()=>{if(!input.value.trim())return;profile.name=input.value.trim().slice(0,12);profileUI();buildPeople();if($('rog-real-user'))$('rog-real-user').textContent='♧ '+profile.name+' (내 기기)';if(match&&!match.finished)match.players[0].name=profile.name;chat('SYSTEM','닉네임이 '+profile.name+'(으)로 변경되었습니다.','system')}},{label:'취소'}])};$('audio').onclick=()=>{soundOn=!soundOn;syncMusic();log(soundOn?'원작 배경음악/효과음 켜짐':'배경음악/효과음 꺼짐');sfx(650)};$('help').onclick=()=>navigate('help-screen');$('make-room').onclick=()=>modal('새로운 채팅방','채팅방 개설은 로컬 재현 모드에서만 가능합니다.',[{label:'확인'}]);$('chat-form').onsubmit=e=>{e.preventDefault();const input=$('message'),message=input.value.trim();input.value='';if(!message)return;chat(profile.name,message);if(window.__LEAF_NET__?.connected&&match?.mode==='network')window.__LEAF_NET__.send({type:'chat',who:profile.name,text:message});sfx(480);};const list=$('online-list');list.replaceChildren();const selfUser=document.createElement('div');selfUser.id='rog-real-user';selfUser.textContent='♧ '+profile.name+' (내 기기)';list.append(selfUser);setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})},12000);$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});chat('SYSTEM','4LEAF Browser에 오신 것을 환영합니다.','system');chat('SYSTEM','원작 화면 재구성 · AI/로컬 대전 · 브라우저 간 직접 연결. 원작 중앙 서버는 지원하지 않습니다.','system');navigate('sky');window.__LEAF_BRIDGE__={getMatch:()=>match,getName:()=>profile.name,onState:null,
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
 }};window.__ROG_TEST__={startGame,drawGame,takeTurn,teamStats,generateTiles,getMatch:()=>match,go:navigate,setRoll:()=>{},setMatch:v=>{match=v;drawGame()},getSourceMaps:()=>SOURCE_INFO,getSourceTiles:()=>SOURCE_TILES,resolveTile,finishGame,calculateMatchReward,elementalModifier,resolveBattle,moveValues,activePlayer,playerCanAct,refreshResume};if(match&&!match.finished){log('저장된 경기가 있습니다. 주사위 대기실의 이어하기로 복원하세요.')}refreshResume()}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();