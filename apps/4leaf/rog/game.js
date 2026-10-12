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
{id:'valkyrie',name:'발키리의 창',icon:'⚔',hint:'두 턴 공격 주사위 1개 추가',sourceId:'0008'},
{id:'ring',name:'지혜의 반지',icon:'◉',hint:'두 턴 지원 지력 +2',sourceId:'0009'},
{id:'bomb',name:'자폭',icon:'☠',hint:'대전 중 패배를 무효화하고 서로 START 복귀',sourceId:'0010',battle:true},
{id:'wing',name:'날개',icon:'✧',hint:'선택한 1~12칸 전진',sourceId:'0011'},
{id:'step',name:'4칸 전후진',icon:'↔',hint:'선택한 1~4칸 전·후진',sourceId:'0012'},
{id:'flipper',name:'오리발',icon:'♧',hint:'대전 중 패배를 무효화',sourceId:'0013',battle:true},
{id:'charge',name:'어빌리티 50',icon:'✦',hint:'능력 게이지 +50%',sourceId:'0014'},
{id:'charge25',name:'어빌리티 25',icon:'✦',hint:'능력 게이지 +25%',sourceId:'0015'},
{id:'armageddon',name:'아마겟돈',icon:'✹',hint:'2턴 동안 방어 보정',sourceId:'0016'},
{id:'dove',name:'비둘기',icon:'✧',hint:'5턴 다른 유저와 전투 면역',sourceId:'0017'},
{id:'change',name:'체인지',icon:'⟳',hint:'대전 중 공격·방어 결과 교환',sourceId:'0026',battle:true},
{id:'oddcurse',name:'홀수 저주',icon:'Ⅰ',hint:'다음 타인의 홀수 눈 1 처리',sourceId:'0028'},
{id:'evencurse',name:'짝수 저주',icon:'Ⅱ',hint:'다음 타인의 짝수 눈 1 처리',sourceId:'0029'},
{id:'curse',name:'저주',icon:'♠',hint:'원하는 앞쪽 발판을 저주로 변경',sourceId:'0030'},
{id:'kingbomb',name:'왕폭탄',icon:'✹',hint:'앞쪽 발판에 폭탄 설치',sourceId:'0031'},
{id:'odincurse',name:'오딘의 저주',icon:'☠',hint:'앞쪽 발판에 데드 오어 얼라이브 저주',sourceId:'0032'},
{id:'keeperA',name:'키퍼 A',icon:'♙',hint:'앞쪽 발판에 약한 키퍼 소환',sourceId:'0033'},
{id:'keeperB',name:'키퍼 B',icon:'♜',hint:'앞쪽 발판에 중간 키퍼 소환',sourceId:'0034'},
{id:'keeperC',name:'키퍼 C',icon:'♛',hint:'앞쪽 발판에 강한 키퍼 소환',sourceId:'0035'},
{id:'drain25',name:'어빌리티 25 감소',icon:'−',hint:'상대 어빌리티 -25%',sourceId:'0038'},
{id:'drain50',name:'어빌리티 50 감소',icon:'−',hint:'상대 어빌리티 -50%',sourceId:'0039'},
{id:'shoe',name:'여신의 신발',icon:'♘',hint:'3턴 이동 주사위 1개 추가',sourceId:'0040'}
];
const ITEM_MAP=Object.fromEntries(ITEMS.map(i=>[i.id,i]));
const SOURCE_ROUTES=window.ORIGINAL_LEAF_MAPS||{},SOURCE_INFO=window.ORIGINAL_LEAF_MAP_INFO||{};
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
let profile,match=null,route='sky',chosenCard=CHR_SOURCE.length>50?'c_0078':'joan',group='all',currentRoom='샤이닝 브리즈',soundOn=false,audioCtx=null,busy=false,bgm=null,bgmTrack=null;
const safe=(v,f)=>{try{const a=JSON.parse(localStorage.getItem('rog_'+v));return a===null?f:a}catch{return f}};
profile=safe('profile',DEFAULT_PROFILE);
if(!profile||!Array.isArray(profile.owned))profile=structuredClone(DEFAULT_PROFILE);
if(CHR_SOURCE.length>50){
 profile.owned=[...new Set(profile.owned.map(id=>LEGACY_IDS[id]||id).filter(id=>CARD_MAP[id]))];
 if(!profile.owned.length)profile.owned=STARTERS.slice();
 profile.team=(profile.team||[]).map(id=>LEGACY_IDS[id]||id).filter(id=>CARD_MAP[id]);
 if(!profile.team.length)profile.team=DEFAULT_PROFILE.team.slice();
 if(!CARD_MAP[chosenCard])chosenCard=profile.owned[0];
}
const savedMatch=safe('match',null);if(savedMatch&&Array.isArray(savedMatch.players)&&savedMatch.players.length>=2&&savedMatch.players.length<=8&&!savedMatch.finished)match=savedMatch;
function activePlayer(){return match?.players?.[match.active]||null}
function playerCanAct(){return !!(match&&!match.finished&&!busy&&activePlayer()&&!activePlayer().bot)}
function refreshResume(){if(!$('resume-game'))return;$('resume-game').classList.toggle('hidden',!(match&&!match.finished&&MAPS[match.map]))}
function persist(){try{localStorage.setItem('rog_profile',JSON.stringify(profile));localStorage.setItem('rog_match',JSON.stringify(match))}catch{}}
function log(text){$('status').textContent=text}
function d(sides=6){return 1+Math.floor(Math.random()*sides)}
function rand(a){return Math.floor(Math.random()*a)}
function diceN(n,sides){let values=[];for(let k=0;k<n;k++)values.push(d(sides));return {values,total:values.reduce((a,b)=>a+b,0)}}
function syncMusic(){if(!soundOn){if(bgm)bgm.pause();return}const track=({sky:'00',city:'01',rooms:'02',lobby:'03',shop:'04',game:'05','help-screen':'06'})[route]||'00';if(bgm&&bgmTrack===track){bgm.play().catch(()=>{});return}if(bgm)bgm.pause();bgm=new Audio('./music/'+track+'.mp3');bgm.loop=true;bgm.volume=.28;bgmTrack=track;bgm.play().catch(()=>{})}
function sfx(freq=500,duration=.07){if(!soundOn)return;try{const AC=window.AudioContext||window.webkitAudioContext;audioCtx=audioCtx||new AC();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='triangle';o.frequency.value=freq;g.gain.setValueAtTime(.038,audioCtx.currentTime);g.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+duration);o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+duration)}catch{}}
function chat(who,message,type=''){const line=document.createElement('div');line.className=type;const b=document.createElement('b');b.textContent=who+'　';line.append(b,document.createTextNode(String(message)));$('chat-log').append(line);while($('chat-log').children.length>90)$('chat-log').firstElementChild.remove();$('chat-log').scrollTop=$('chat-log').scrollHeight}
function profileUI(){$('nick').textContent=profile.name;$('profile-name').textContent=profile.name;$('my-name').textContent=profile.name;$('gp').textContent=profile.gp.toLocaleString();$('shop-gp').textContent=profile.gp.toLocaleString();$('wins').textContent=profile.wins+'승';persist()}
function navigate(id){if(!routeNames[id])return;route=id;query('.scene').forEach(s=>s.classList.toggle('hidden',s.id!==id));query('[data-route]').forEach(el=>el.classList.toggle('active',el.dataset.route===id));$('where').textContent=routeNames[id];$('chat-location').textContent=routeNames[id];if(id==='game'&&match){drawGame();const p=activePlayer();if(p?.bot&&!busy)setTimeout(()=>{if(route==='game'&&match&&!match.finished&&activePlayer()?.bot&&!busy)takeTurn()},500)}if(id==='shop')drawShop();if(id==='lobby'){drawTeam();refreshResume()}log(routeNames[id]+'에 입장하였습니다.');syncMusic();sfx(610)}
function modal(title,body,buttons){$('modal-title').textContent=title;$('modal-content').replaceChildren();if(typeof body==='string'){$('modal-content').textContent=body}else if(body)$('modal-content').append(body);$('modal-buttons').replaceChildren();buttons.forEach(opt=>{const b=document.createElement('button');b.textContent=opt.label;b.className=opt.primary?'primary':'';b.onclick=()=>{$('modal').classList.add('hidden');if(opt.run)opt.run()};$('modal-buttons').append(b)});$('modal').classList.remove('hidden')}
function ask(title,body,options){return new Promise(resolve=>modal(title,body,options.map((a,i)=>({label:a,primary:i===0,run:()=>resolve(i)}))))}
function toast(message){log(message);$('move-log').textContent=message}
function rosterByIds(ids){return (ids||[]).map(id=>CARD_MAP[id]).filter(Boolean).slice(0,3)}
function teamStats(ids){const cards=rosterByIds(ids),attack=cards[0]||BASE_CARDS[0],defend=cards[1]||attack,assist=cards[2]||null;const same=cards.length>0&&cards.every(c=>c.move===cards[0].move);return {move:same?cards[0].move:1,atk:attack.atk,def:defend.def,int:assist?assist.int:0,point:cards.reduce((sum,c)=>sum+c.point,0),ability:attack.ability,abilityId:attack.abilityId,portrait:attack.portrait,name:attack.name};}
function ownedCards(){return profile.owned.filter(x=>CARD_MAP[x])}
function drawTeam(){const root=$('team-select');root.replaceChildren();const slots=['공격','방어','지력'];for(let slot=0;slot<3;slot++){const s=document.createElement('button');s.className='team-slot';const c=CARD_MAP[profile.team[slot]];s.innerHTML='<b>'+slots[slot]+'</b><small>'+(c?c.name:'미지정')+'</small><small>'+(c?('M'+c.move+' A'+c.atk+' D'+c.def+' I'+c.int):'')+'</small>';s.onclick=()=>{const div=document.createElement('div');const label=document.createElement('p');label.textContent=slots[slot]+' 포지션에 배치할 체스맨을 고르세요.';div.append(label);const select=document.createElement('select');ownedCards().forEach(id=>{const c=CARD_MAP[id],option=document.createElement('option');option.value=id;option.textContent=c.name+' (이동'+c.move+' · '+c.point+'pt)';if(profile.team[slot]===id)option.selected=true;select.append(option)});div.append(select);modal('파티 구성',div,[{label:'선택',primary:true,run:()=>{profile.team[slot]=select.value;persist();drawTeam()}},{label:'취소'}])};root.append(s)}const stats=teamStats(profile.team);const limit=Number($('point-limit').value);let summary=document.createElement('div');summary.className='fine';summary.textContent='합계 '+stats.point+' / '+limit+' POINT · 이동 주사위 '+stats.move+' · 공격 '+stats.atk+' · 방어 '+stats.def+' · 지원 지력 +'+stats.int;root.append(summary)}
function drawShop(){const root=$('shop-grid');root.replaceChildren();const filtered=BASE_CARDS.filter(c=>group==='all'||c.rank===group);filtered.forEach(c=>{const b=document.createElement('button');b.className='shop-card'+(chosenCard===c.id?' selected':'');b.innerHTML='<div class="card-art"><img class="pixel-portrait" src="'+imageFor(c.id)+'" alt=""></div><b>'+c.name+'</b><span>'+c.price.toLocaleString()+' GP</span><small>M '+c.move+' / A '+c.atk+' / D '+c.def+' / I '+c.int+'</small><span class="'+(profile.owned.includes(c.id)?'owned':'')+'">'+(profile.owned.includes(c.id)?'● 보유':'◇ 미보유')+'</span>';b.onclick=()=>{chosenCard=c.id;drawShop()};root.append(b)});query('.group-tab').forEach(b=>b.classList.toggle('selected',b.dataset.group===group));const c=CARD_MAP[chosenCard];$('shop-selected').textContent=c.name+' · '+c.rank.toUpperCase()+' · '+c.point+'pt / '+c.price.toLocaleString()+'GP / '+c.ability;profileUI()}
function buildRoomList(){const list=$('room-list');list.replaceChildren();['샤이닝 브리즈','실버 호라이즌','윈트리 아이스','헤이즐리 웨이브','엘핀 포레스트'].forEach((r,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+r+'　('+(['평원','설원','빙원','해양','숲'][i])+')';b.className=r===currentRoom?'selected':'';b.onclick=()=>{currentRoom=r;const roomScene=document.querySelector('#rooms .room-floor');if(roomScene)roomScene.style.backgroundImage='url("./original/ChatRoom/room'+Math.min(i,5)+'.png")';buildRoomList();$('room-title').textContent='하이아칸 · '+r;chat('SYSTEM',r+' 방에 입장했습니다. 다른 이용자와는 연결되지 않습니다.','system')};list.append(b)});$('room-title').textContent='하이아칸 · '+currentRoom}
function buildPeople(){const root=$('town-figures');root.replaceChildren();const roster=[profile.name,'티치엘','막시민','루시안','이스핀'];roster.forEach((name,i)=>{const b=document.createElement('button');b.className='avatar';b.style.setProperty('--hair',['#5f4e70','#c6b26a','#362a5e','#dcc17e','#ce8b7a'][i]);b.style.setProperty('--outfit',['#7d68b7','#649ac4','#5d638f','#ac735c','#aa798e'][i]);b.style.backgroundImage='url("'+townAvatar(i)+'")';b.innerHTML='<i class="avatar-head"></i><i class="avatar-body"></i><small></small>';b.querySelector('small').textContent=name;b.onclick=()=>chat(name,i===0?'오늘도 좋은 하루네요!':'반가워요, '+profile.name+'님.','npc');root.append(b)})}
function generateTiles(map){
 const config=MAPS[map],source=SOURCE_ROUTES[SOURCE_IDS[map]],types=[];
 // The positions of playable cells and transfer edges are read from 4LEAF's original .mve.
 // Unresolved non-transfer tile effects are distributed deterministically, never presented as decoded archive data.
 let salt=Array.from(map).reduce((n,c)=>(n*33+c.codePointAt(0))>>>0,2166136261);
 const weighted=['normal','normal','normal','normal','normal','normal','ability','normal','clover','normal','chest','normal','keeper','normal','spade','normal','boost','normal','attribute','normal','doa','normal','random','normal','joker','normal','prison','normal','blessing','normal','curse','normal','arena'];
 for(let i=0;i<config.length;i++){
   salt=(Math.imul(salt^i,1664525)+1013904223)>>>0;
   let type=weighted[salt%weighted.length];
   if(i===0)type='start';
   else if(i===config.length-1)type='goal';
   else if(source&&source[i]&&source[i][3]===10&&source[i][5]>=0&&source[i][5]<config.length&&source[i][5]!==i)type='warp';
   types.push(type);
 }
 return types;
}
function pathCoords(){let pts=[],left=0,right=13,top=0,bottom=7;while(left<=right&&top<=bottom){for(let x=left;x<=right;x++)pts.push([x,top]);for(let y=top+1;y<=bottom;y++)pts.push([right,y]);if(top<bottom)for(let x=right-1;x>=left;x--)pts.push([x,bottom]);if(left<right)for(let y=bottom-1;y>top;y--)pts.push([left,y]);left+=1;right-=1;top+=1;bottom-=1}return pts.map(([x,y])=>({x:5.5+x*(89/13),y:8.5+y*(83/7)}))}
let PATH=pathCoords();
function chooseSourcePath(map){const records=SOURCE_ROUTES[SOURCE_IDS[map]];if(!records||records.length<8){PATH=pathCoords();return}const xs=records.map(p=>p[0]),ys=records.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);PATH=records.map(p=>({x:8+(p[0]-xmin)*84/Math.max(1,xmax-xmin),y:8+(p[1]-ymin)*84/Math.max(1,ymax-ymin)}))}
function installAuthenticMaps(){const list=$('map-select'),entries=Object.entries(SOURCE_INFO).filter(([id])=>SOURCE_ROUTES[id]&&SOURCE_ROUTES[id].length>9);if(!entries.length)return;list.replaceChildren();const rank=['4LEAF','주사위','워프 게이트','PK','악마의 달팽이','한반도','For the Lucky'];entries.sort((a,b)=>{let i=rank.indexOf(a[1].title),j=rank.indexOf(b[1].title);return (i<0?99:i)-(j<0?99:j)});for(const [id,info] of entries){const title=info.title,length=SOURCE_ROUTES[id].length;const old=MAPS[title]||{};const generate=(step,offset)=>Array.from({length:Math.floor(length/step)},(_,i)=>offset+i*step).filter(i=>i>0&&i<length-1);MAPS[title]={length,non:['악마의 달팽이','한반도'].includes(title),warp:old.warp||generate(30,8),keepers:old.keepers||generate(17,13),jail:old.jail||generate(44,25),chests:old.chests||generate(19,6),boost:old.boost||generate(23,17),attribute:old.attribute||generate(29,20),joker:old.joker||generate(41,36)};const opt=document.createElement('option');opt.value=title;opt.textContent=title+' · '+length+'칸 [원본 '+id+']';list.append(opt)}list.value='4LEAF'}
function freshItems(){return Array.from({length:3},()=>ITEMS[rand(ITEMS.length)].id)}
function newPlayer(id,bot,name,team){return {id,bot,name,team,position:0,jail:0,ability:0,items:freshItems(),effects:{shoe:0,dove:0,clover:0,spade:0,ring:0,armageddon:0,valkyrie:0,oddcurse:0,evencurse:0,block:0,destroy:0,keeper:0},usedItem:false,color:COLORS[id],pawn:PAWNS[id]}}
function startGame(){const map=$('map-select').value,limit=Number($('point-limit').value),stats=teamStats(profile.team);chooseSourcePath(map);if(!profile.team[0])return modal('파티 구성','공격 체스맨을 선택하세요.',[{label:'확인',primary:true}]);if(stats.point>limit)return modal('소환 POINT 초과','현재 파티는 '+stats.point+'POINT이며 제한은 '+limit+'POINT입니다.',[{label:'확인',primary:true}]);const bots=Number($('bot-count').value),hotseat=$('game-mode').value==='hotseat';let players=[newPlayer(0,false,profile.name,profile.team.slice())];for(let i=0;i<bots;i++){const weakTeams=CHR_SOURCE.length>50?[
 ['c_0096','c_0078','c_0040'],['c_0078','c_0045','c_0096'],['c_0040','c_0078','c_0096'],['c_0045','c_0096','c_0078'],['c_0078','c_0040','c_0045'],['c_0096','c_0045','c_0078'],['c_0040','c_0096','c_0045']]:
 [['rashid','soldier','narcia'],['joan','narcia','soldier'],['soldier','joan','rashid'],['iolyn','soldier','narcia'],['merza','rashid','soldier'],['christian','soldier','joan'],['damian','soldier','narcia']];let team=weakTeams[i].filter((_,j)=>j===0||limit>=8);while(teamStats(team).point>limit)team.pop();players.push(newPlayer(i+1,!hotseat,hotseat?'플레이어 '+(i+2):BOT_NAMES[i],team))}match={version:3,map,mode:hotseat?'hotseat':'ai',tiles:generateTiles(map),players,active:0,round:1,finished:false,winner:-1,attribute:'NONE',message:'주사위를 굴려 주세요.',lastRoll:[],history:[],pending:null};busy=false;persist();navigate('game');chat('SYSTEM',map+' 게임을 시작했습니다. '+(hotseat?'사람 '+(bots+1)+'명이 번갈아 플레이합니다.':'컴퓨터 '+bots+'명이 참가합니다.'),'system');drawGame()}
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
 if(!layer){layer=document.createElement('div');layer.id='board-pawns';$('board-area').append(layer)}
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
   const slot=players.filter(q=>q.position===p.position).findIndex(q=>q.id===p.id);
   pawn.style.left='calc('+point.x+'% + '+((slot%4)*11-12)+'px)';
   pawn.style.top='calc('+point.y+'% - '+(Math.floor(slot/4)*14)+'px)';
   pawn.style.setProperty('--pawn-color',p.color);
   pawn.classList.toggle('pawn-current',match.active===p.id);
   pawn.querySelector('.board-pawn-name').textContent=p.name;
 }
}
function drawGame(){if(!match||!MAPS[match.map])return;chooseSourcePath(match.map);const p=(match.mode==='hotseat'?activePlayer():match.players[0]),stats=teamStats(p.team);$('game-map-title').textContent=match.map;$('element-label').textContent=match.attribute;$('player-count').textContent=match.players.length;$('turn-indicator').textContent='ROUND '+match.round+' · '+match.players[match.active].name+' TURN';$('my-name').textContent=p.name;$('my-stats').textContent='이동 '+stats.move+' · 공격 '+stats.atk+' · 방어 '+stats.def+' · 지력 +'+stats.int;$('my-position').textContent=p.jail>0?'감옥 '+p.jail+'턴':p.position===0?'START':p.position===match.tiles.length-1?'GOAL':(p.position+1)+'번째 칸';$('my-portrait').innerHTML='<img class="player-sprite" alt="" src="'+imageFor(p.team[0]||'soldier')+'">';$('ability-fill').style.width=p.ability+'%';$('game-players').replaceChildren();match.players.forEach((user,i)=>{const li=document.createElement('div');li.className=match.active===i?'is-turn':'';li.textContent=(match.active===i?'▶ ':'　')+user.pawn+' '+user.name+' '+(user.position+1)+'칸 · '+user.ability+'%';li.style.color=user.color;$('game-players').append(li)});$('my-items').replaceChildren();p.items.forEach((itemId,i)=>{const item=ITEM_MAP[itemId],btn=document.createElement('button');btn.className='item-card';btn.innerHTML='<span class="item-icon">'+(item?.icon||'✧')+'</span>'+(item?.name||itemId);btn.title=item.hint;btn.disabled=match.finished||!playerCanAct()||p.usedItem||busy;btn.onclick=()=>useItem(i);$('my-items').append(btn)});$('roll-btn').disabled=!playerCanAct();$('ability-btn').disabled=!playerCanAct()||p.ability<100;$('move-log').textContent=match.message;drawBoard()}
function withUserTurn(){return playerCanAct()}
function useItem(index){
 if(!withUserTurn())return;
 const user=activePlayer(),itemId=user.items[index],item=ITEM_MAP[itemId];
 if(!item||user.usedItem)return;
 if(item.battle)return modal('전투 전용 카드',item.name+'은(는) 전투 결과가 표시될 때 사용할 수 있습니다. 다른 행동을 선택해 주세요.',[{label:'확인',primary:true}]);
 if(itemId==='wing'||itemId==='step'){
   const div=document.createElement('div'),label=document.createElement('p'),input=document.createElement('input');
   label.textContent=item.name+' · '+item.hint;input.type='number';
   input.min=itemId==='wing'?'1':'-4';input.max=itemId==='wing'?'12':'4';
   input.value=itemId==='wing'?'6':'4';
   div.append(label,input);
   return modal('아이템 사용',div,[{label:'사용',primary:true,run:async()=>{
     const n=Math.max(Number(input.min),Math.min(Number(input.max),Number(input.value)||1));
     if(n===0)return;
     consume(index);advance(user,n);
     appendMove(user.name+' '+item.name+' · '+n+'칸 이동');
     if(n>0)await resolveTile(user);drawGame();
   }},{label:'취소'}]);
 }
 modal('아이템 · '+item.name,item.hint+' · 이번 턴에 사용하시겠습니까?',[{
   label:'사용',primary:true,run:()=>{
     consume(index);
     if(!user.effects)user.effects={};
     switch(itemId){
       case 'shoe': user.effects.shoe=3;break;
       case 'dove': user.effects.dove=5;break;
       case 'valkyrie':user.effects.valkyrie=2;break;
       case 'ring':user.effects.ring=2;break;
       case 'armageddon':user.effects.armageddon=2;break;
       case 'charge':user.ability=Math.min(100,user.ability+50);break;
       case 'charge25':user.ability=Math.min(100,user.ability+25);break;
       case 'drain25':{const other=match.players.filter(p=>p!==user).sort((a,b)=>b.ability-a.ability)[0];if(other)other.ability=Math.max(0,other.ability-25);break}
       case 'drain50':{const other=match.players.filter(p=>p!==user).sort((a,b)=>b.ability-a.ability)[0];if(other)other.ability=Math.max(0,other.ability-50);break}
       case 'oddcurse':match.players.filter(p=>p!==user).forEach(p=>p.effects.oddcurse=1);break;
       case 'evencurse':match.players.filter(p=>p!==user).forEach(p=>p.effects.evencurse=1);break;
       case 'curse':match.tiles[Math.min(match.tiles.length-2,user.position+6)]='curse';break;
       case 'odincurse':match.tiles[Math.min(match.tiles.length-2,user.position+6)]='doa';break;
       case 'kingbomb':match.tiles[Math.min(match.tiles.length-2,user.position+6)]='kingbomb';break;
       case 'keeperA':case 'keeperB':case 'keeperC':{
          const tile=Math.min(match.tiles.length-2,user.position+6);
          match.tiles[tile]=itemId;break
       }
     }
     appendMove(user.name+' · '+item.name+' 사용');drawGame();
   }
 },{label:'취소'}]);
}
function consume(index){const p=activePlayer();p.items.splice(index,1);p.usedItem=true;persist()}
function advance(user,distance){user.position=Math.min(match.tiles.length-1,Math.max(0,user.position+distance));user.ability=Math.min(100,user.ability+Math.max(0,distance)*4)}
async function useAbility(){
 if(!withUserTurn())return;
 const p=activePlayer(),stats=teamStats(p.team);
 if(p.ability<100)return;
 const code=stats.abilityId||0;
 const selection=await ask('어빌리티 발동',stats.name+' · '+stats.ability+' / 충전 100%',['발동','취소']);
 if(selection!==0||!withUserTurn())return;
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
 if([30,33,35,37,24].includes(code))await resolveTile(p);
 drawGame();
}
function combat(attacker,defender,keeper=false){
 return new Promise(resolve=>{
 const aStat=teamStats(attacker.team),bStat=keeper?{def:defender.def||2,int:0}:{...teamStats(defender.team)};
 const aCount=Math.max(1,aStat.atk+(attacker.effects?.valkyrie>0?1:0)),bCount=Math.max(1,bStat.def);
 let attack,defense,aValue,bValue,rerolls=0;
 for(let attempt=0;attempt<100;attempt++){
   attack=diceN(aCount,6);defense=diceN(bCount,6);
   aValue=attack.total+(aStat.int||0)+(attacker.effects?.ring>0?2:0)+(attacker.effects?.teamInt>0?3:0);
   bValue=defense.total+(bStat.int||0)+(defender.effects?.ring>0?2:0)+(defender.effects?.teamInt>0?3:0);
   if(attacker.effects?.scar>0)aValue=Math.max(1,aValue-attacker.effects.scar);
   if(defender.effects?.scar>0)bValue=Math.max(1,bValue-defender.effects.scar);
   if(attacker.effects?.ultimate>0)aValue=30;
   if(defender.effects?.ultimate>0)bValue=18;
   if(attacker.effects?.destroy>0)aValue=24;
   if(defender.effects?.block>0)bValue=24;
   if(attacker.effects?.armageddon>0)aValue+=6;
   if(defender.effects?.armageddon>0)bValue+=6;
   if(aValue!==bValue)break;rerolls++;
 }
 const div=document.createElement('div');
 div.innerHTML='<p>'+attacker.name+'의 공격! '+defender.name+'이(가) 방어합니다.'+(rerolls?' · 무승부 '+rerolls+'회 재굴림':'')+'</p><div class="battle-dice"><div>ATTACK<div class="nums">'+attack.values.join('·')+'</div><b>'+aValue+'</b><small>지력 +'+aStat.int+'</small></div><div>DEFENSE<div class="nums">'+defense.values.join('·')+'</div><b>'+bValue+'</b><small>지력 +'+bStat.int+'</small></div></div>';
 const player=activePlayer();
 const selfInvolved=!keeper&&player&&!player.bot&&(attacker.id===player.id||defender.id===player.id);
 let results={attacker:aValue,defender:bValue,changed:false,negated:false};
 const options=[{label:'결과 확인',primary:true,run:()=>resolve(results)}];
 if(selfInvolved&&player.items.includes('change')&&!player.usedItem){
   options.unshift({label:'체인지 카드',run:()=>{player.items.splice(player.items.indexOf('change'),1);player.usedItem=true;resolve({attacker:bValue,defender:aValue,changed:true})}});
 }
 if(selfInvolved&&player.items.includes('bomb')&&!player.usedItem){options.unshift({label:'자폭',run:()=>{player.items.splice(player.items.indexOf('bomb'),1);player.usedItem=true;attacker.position=0;if(Number.isInteger(defender.position))defender.position=0;resolve({...results,negated:true,mutualReset:true})}})}
 if(selfInvolved&&player.items.includes('flipper')&&!player.usedItem){
   options.unshift({label:'오리발 카드',run:()=>{player.items.splice(player.items.indexOf('flipper'),1);player.usedItem=true;resolve({...results,negated:true})}});
 }
 modal('⚔ BATTLE · 전투',div,options);sfx(235,.21);
 if(!selfInvolved||keeper&&attacker.bot){
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
 if(pos>=match.tiles.length-1){finishGame(p);return}
 let landed=false;
 if(type==='boost'||type==='boost4'){
   const n=type==='boost4'?4:3;advance(p,n);appendMove(p.name+' +'+n+' 전진!');landed=true;
 }else if(type==='warp'){
   const row=SOURCE_ROUTES[SOURCE_IDS[match.map]]?.[pos];
   let target=Number.isInteger(row?.[5])?row[5]:-1;
   if(target<0||target>=match.tiles.length||target===pos){
     const candidate=MAPS[match.map].warp.filter(x=>x!==pos);
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
 else if(type==='ability100'){const count=Math.max(1,Math.min(4,teamStats(p.team).int||teamStats(p.team).atk));const eyes=diceN(count,6).values;if(eyes.some(v=>v===6)){p.ability=100;appendMove(p.name+' 판정 '+eyes.join(',')+' · 어빌리티 100%!')}else appendMove(p.name+' 판정 '+eyes.join(',')+' · 실패')}
 else if(type==='attribute'){match.attribute=['WANDS','SWORDS','CUPS','DISKS'][rand(4)];appendMove('맵 속성이 '+match.attribute+'(으)로 변경!')}
 else if(type==='clover'){p.effects.clover=1;p.effects.spade=0;appendMove(p.name+' 클로버: 다음 주사위는 높은 눈')}
 else if(type==='spade'){p.effects.spade=1;p.effects.clover=0;appendMove(p.name+' 스페이드: 다음 주사위는 낮은 눈')}
 else if(type==='doa'){
   const first=d(6),second=d(first),diff=first-second;
   if(diff>=3)p.position=0;else p.position=Math.max(0,p.position-diff*3);
   appendMove(p.name+' DEAD OR ALIVE: '+first+' / '+second+' → '+(diff>=3?'START':diff*3+'칸 후퇴'));
 }else if(type==='keeper'||type==='arena'){
   if(!(type==='arena'&&p.effects.dove>0)){
     const monsters=[['슬라임',1],['해골',2],['좀비',2],['고렘',3],['아지다하카',3],['크루거',4],['마장기',6]];
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
 if(p.position>=match.tiles.length-1){finishGame(p);return}
 if(landed){await resolveTile(p,depth+1);return}
 if(!match.finished&&!MAPS[match.map].non){
   const opponent=match.players.find(other=>other!==p&&other.position===p.position&&other.effects.dove<=0&&p.effects.dove<=0);
   if(opponent)await resolveBattle(p,opponent,false);
 }
}
function finishGame(winner){match.finished=true;match.winner=winner.id;match.message=winner.name+'이(가) GOAL에 도착했습니다!';const distance=match.tiles.length-1;const reward=winner.id===0?1200:Math.max(100,Math.round(match.players[0].position/distance*600));profile.gp+=reward;if(winner.id===0)profile.wins++;profileUI();persist();chat('SYSTEM',winner.name+'님이 가장 먼저 GOAL에 도착했습니다! GP +'+reward,'system');modal('✦ 주사위의 잔영 · 게임 종료',winner.name+' 승리!　획득 GP +'+reward.toLocaleString()+'\n게임을 다시 시작할 수 있습니다.',[{label:'다시 시작',primary:true,run:()=>navigate('lobby')},{label:'결과 보기',run:()=>drawGame()}]);sfx(925,.4)}
function moveValues(p){
 const stats=teamStats(p.team),extra=p.effects.shoe>0?1:0,values=[];
 const sides=stats.move===2?4:6,n=Math.min(4,(stats.move===2?2:1)+extra);
 for(let i=0;i<n;i++){
   let v=d(sides);
   if(p.effects.clover)v=Math.max(v,sides===4?3:4);
   if(p.effects.spade)v=Math.min(v,sides===4?2:3);
   values.push(v);
 }
 
 if(p.effects.oddcurse){for(let i=0;i<values.length;i++)if(values[i]%2===1)values[i]=1;p.effects.oddcurse=0}
 if(p.effects.evencurse){for(let i=0;i<values.length;i++)if(values[i]%2===0)values[i]=2;p.effects.evencurse=0}
 p.effects.clover=0;p.effects.spade=0;
 return values;
}
function showDice(values){$('die1').textContent=['⚀','⚁','⚂','⚃','⚄','⚅'][Math.min(5,values[0]-1)];$('die2').textContent=values.length>1?['⚀','⚁','⚂','⚃','⚄','⚅'][Math.min(5,values[1]-1)]:'·'}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function takeTurn(){
 if(!match||match.finished||busy)return;
 busy=true;const p=match.players[match.active];drawGame();if(p.bot)await wait(250);
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
 if(p.effects.ring>0)p.effects.ring--;
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
function init(){installAuthenticMaps();if(match)chooseSourcePath(match.map);profileUI();buildRoomList();buildPeople();drawTeam();drawShop();query('[data-route]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.route)));query('.group-tab').forEach(b=>b.addEventListener('click',()=>{group=b.dataset.group;drawShop()}));$('point-limit').onchange=drawTeam;$('start-game').onclick=startGame;$('resume-game').onclick=()=>{if(match&&!match.finished){busy=false;navigate('game');chat('SYSTEM','진행 중인 게임을 이어합니다.','system')}};$('roll-btn').onclick=takeTurn;$('ability-btn').onclick=useAbility;$('exit-game').onclick=()=>modal('게임에서 나가기','진행 중인 게임은 브라우저에 보관됩니다. 나갔다가 주사위의 잔영 버튼으로 다시 들어올 수 있습니다.',[{label:'나가기',primary:true,run:()=>navigate('lobby')},{label:'취소'}]);$('shop-buy').onclick=()=>{const c=CARD_MAP[chosenCard];if(profile.owned.includes(c.id))return modal('매직카덴',c.name+' 카드는 이미 가지고 있습니다.',[{label:'확인'}]);if(profile.gp<c.price)return modal('매직카덴','GP가 부족합니다.',[{label:'확인'}]);modal('매직카덴',c.name+' 카드를 '+c.price.toLocaleString()+'GP에 구매하시겠습니까?',[{label:'구매',primary:true,run:()=>{profile.gp-=c.price;profile.owned.push(c.id);profileUI();drawShop();drawTeam();chat('매직카덴',c.name+' 카드를 구매했습니다.','system');sfx(830)}},{label:'취소'}])};$('rename').onclick=()=>{const div=document.createElement('div');div.textContent='사용할 닉네임을 입력하세요.';const input=document.createElement('input');input.maxLength=12;input.value=profile.name;div.append(document.createElement('hr'),input);modal('4LEAF 별명 변경',div,[{label:'변경',primary:true,run:()=>{if(!input.value.trim())return;profile.name=input.value.trim().slice(0,12);profileUI();buildPeople();if(match&&!match.finished)match.players[0].name=profile.name;chat('SYSTEM','닉네임이 '+profile.name+'(으)로 변경되었습니다.','system')}},{label:'취소'}])};$('audio').onclick=()=>{soundOn=!soundOn;syncMusic();log(soundOn?'원작 배경음악/효과음 켜짐':'배경음악/효과음 꺼짐');sfx(650)};$('help').onclick=()=>navigate('help-screen');$('make-room').onclick=()=>modal('새로운 채팅방','채팅방 개설은 로컬 재현 모드에서만 가능합니다.',[{label:'확인'}]);$('chat-form').onsubmit=e=>{e.preventDefault();const input=$('message'),message=input.value.trim();input.value='';if(!message)return;chat(profile.name,message);sfx(480);if(route==='rooms'&&Math.random()<.25)setTimeout(()=>chat('티치엘','오늘도 좋은 하루 보내세요!','npc'),650)};query('#online-list').forEach(()=>{});const list=$('online-list');['Guest (LOCAL)','티치엘 (NPC)','막시민 (NPC)','보리스 (NPC)','루시안 (NPC)','이스핀 (NPC)','시벨린 (NPC)','루시아 (NPC)','샤이닝 브리즈','실버 호라이즌','켈티카'].forEach(n=>{const div=document.createElement('div');div.textContent='♧ '+n;list.append(div)});setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})},12000);$('clock').textContent=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});chat('SYSTEM','4LEAF Browser에 오신 것을 환영합니다.','system');chat('SYSTEM','원작 화면 재구성 · AI 대전 · 로컬 채팅. 온라인 멀티플레이는 지원하지 않습니다.','system');navigate('sky');window.__ROG_TEST__={startGame,drawGame,takeTurn,teamStats,generateTiles,getMatch:()=>match,go:navigate,setRoll:()=>{},setMatch:v=>{match=v;drawGame()},getSourceMaps:()=>SOURCE_INFO,playerCanAct,refreshResume};if(match&&!match.finished){log('저장된 경기가 있습니다. 주사위 대기실의 이어하기로 복원하세요.')}refreshResume()}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();