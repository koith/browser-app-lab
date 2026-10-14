'use strict';
/* ChatTown/ChatRoom.pak social reconstruction.
   Actual messages and real occupant counts: BroadcastChannel across tabs and
   optional encrypted WebRTC DataChannel between two devices. No fake online NPCs. */
(function(){
 const $=id=>document.getElementById(id);
 const W=794,H=528;
 const REGIONS={
  north:{title:'북 하이아칸',art:'northback',districts:[
   ['실버 호라이즌',72,55,164,91],['화이트 크리스탈',253,95,165,91],['프레이 시티',433,81,167,93],['샤이닝 브리즈',608,58,165,101],
   ['윈트리 아이스',35,193,169,99],['스노우 폴',226,237,168,95],['스위트 자스민',568,194,178,95],['그린 에메랄드',401,284,168,94]
  ]},
  south:{title:'남 하이아칸',art:'southback',districts:[
   ['블루 사파이어',65,57,175,91],['헤이즐리 웨이브',253,93,163,96],['미쉘 에메랄드',438,67,170,97],['엘핀 포레스트',608,57,178,95],
   ['아루아 코랄',34,192,170,99],['블랙씨 아린',226,235,166,99],['브라브 지피트',581,193,174,101],['미스틱 머메이드',405,290,171,96]
  ]}
 };
 const originalTemplates=[2,3,5,4,0,1];
 const avatars=['sava00','sava82','sava06','sava01','sava85','sava02','sava84','sava04','sava03','sava83','sava05','sava86'];
 const now=()=>Date.now(),uuid=()=>crypto.randomUUID?.()||Math.random().toString(36).slice(2)+String(Date.now());
 const safe=(s,max=100)=>String(s??'').replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,max);
 const tabId=uuid();
 const nick=()=>safe($('profile-name')?.textContent||'Guest',12)||'Guest';
 const state={region:'north',district:REGIONS.north.districts[3][0],view:'town',roomId:null,rooms:loadRooms(),peers:new Map(),seen:new Set(),bubble:null,scope:'world',avatar:0,position:{x:52,y:76}};
 let channel=null,rtc=null,dataChannel=null,rtcRole=null,resize=null,pulse=null,stageInfo=null,sceneInit=false;
 const $root=()=>$('rooms'),$stage=()=>$('social-stage');
 async function deriveRoomProof(password,salt){
  const raw=new TextEncoder().encode(String(password));
  const key=await crypto.subtle.importKey('raw',raw,{name:'PBKDF2'},false,['deriveBits']);
  const bits=await crypto.subtle.deriveBits({
   name:'PBKDF2',salt:new TextEncoder().encode(salt),iterations:120000,hash:'SHA-256'
  },key,256);
  return Array.from(new Uint8Array(bits),n=>n.toString(16).padStart(2,'0')).join('');
 }
 function loadRooms(){
  try{
   const raw=JSON.parse(localStorage.getItem('leaf_social_rooms_v3')||'[]');
   return Array.isArray(raw)?raw.filter(r=>r&&typeof r.id==='string'&&typeof r.name==='string'&&['north','south'].includes(r.region)).slice(-180).map(r=>({
    id:safe(r.id,70),name:safe(r.name,26),region:r.region,district:safe(r.district,36),owner:safe(r.owner,24),
    passwordProof:safe(r.passwordProof||'',65),passwordSalt:safe(r.passwordSalt||'',75),background:Number.isInteger(r.background)&&r.background>=0&&r.background<=5?r.background:2,created:Number(r.created)||0
   })):[];
  }catch{return []}
 }
 function saveRooms(){try{localStorage.setItem('leaf_social_rooms_v3',JSON.stringify(state.rooms))}catch{}}
 function currentRoom(){
  return roomById(state.roomId);
 }
 function roomById(id){
  return state.rooms.find(r=>r.id===id)||presetRooms().find(r=>r.id===id)||null;
 }
 function presetRooms(){
  const current=REGIONS[state.region]||REGIONS.north;
  return originalTemplates.map((background,i)=>({
   id:'public:'+state.region+':'+state.district+':'+i,name:'공개 채팅방 '+String(i+1).padStart(2,'0'),
   region:state.region,district:state.district,owner:'',passwordProof:'',passwordSalt:'',background,preset:true,created:0
  }));
 }
 function catalogue(){
  return [...presetRooms(),...state.rooms.filter(r=>r.region===state.region&&r.district===state.district)];
 }
 function scope(){
  if(state.view==='room'&&state.roomId)return 'room:'+state.roomId;
  if(state.view==='directory')return 'district:'+state.region+':'+state.district;
  if(state.view==='town')return 'town:'+state.region;
  if(state.view==='board')return 'board:recordable';
  return 'world';
 }
 // Room foreground and seat maps are based on the recovered ChatRoom PNG compositions.
 // Exact historical anchors are not stored in the extracted bitmap assets, so these
 // values remain image-grounded approximations, not decoded native engine coordinates.
 const ROOM_LAYOUTS={
  0:{seats:[[21,66],[38,66],[55,66],[73,66],[20,80],[38,80],[55,80],[74,80],[22,92],[39,92],[57,92],[74,92]]},
  1:{seats:[[24,64],[42,64],[60,64],[76,64],[22,78],[40,78],[59,78],[76,78],[22,91],[40,91],[59,91],[76,91]]},
  2:{seats:[[20,63],[37,63],[55,63],[73,63],[21,78],[38,78],[56,78],[73,78],[22,92],[39,92],[57,92],[74,92]]},
  3:{seats:[[19,83],[38,72],[59,72],[81,83],[24,94],[39,94],[56,94],[72,94],[22,69],[77,69],[39,83],[61,83]],
     foreground:{file:'room3t',x:204,y:354,w:568,h:213,depth:80}},
  4:{seats:[[21,65],[38,65],[56,65],[74,65],[21,80],[39,80],[58,80],[75,80],[21,93],[39,93],[57,93],[75,93]],
     foreground:{file:'room4t',x:318,y:345,w:157,h:143,depth:77}},
  5:{seats:[[20,66],[38,66],[56,66],[74,66],[20,81],[39,81],[57,81],[75,81],[22,93],[39,93],[57,93],[74,93]],
     foreground:{file:'room5t',x:281,y:357,w:260,h:170,depth:78}}
 };
 const roomLayout=(bg=currentRoom()?.background)=>ROOM_LAYOUTS[bg]||ROOM_LAYOUTS[2];
 const roomSeats=(bg=currentRoom()?.background)=>roomLayout(bg).seats.map(([x,y])=>({x,y}));
 function closestSeat(x,y,occupied=new Set(),seats=roomSeats()){
  const list=seats.map((seat,i)=>({i,d:(seat.x-x)**2*2.26+(seat.y-y)**2}))
   .sort((a,b)=>a.d-b.d||a.i-b.i);
  return (list.find(p=>!occupied.has(p.i))||list[0]).i;
 }
 function place(user,index,occupied=new Set()){
  const pos=user.position;
  const x=pos&&Number.isFinite(pos.x)?pos.x:52;
  const y=pos&&Number.isFinite(pos.y)?pos.y:76;
  const seats=roomSeats(),seat=closestSeat(x,y,occupied,seats);
  return {...seats[seat],seat};
 }
 function compactPresence(){
  return {id:tabId,nick:nick(),scope:state.scope,roomId:state.roomId,
   region:state.region,district:state.district,view:state.view,
   avatar:state.avatar,position:{x:state.position.x,y:state.position.y},last:now()};
 }
 function sendLocal(packet){
  const msg={v:1,from:tabId,...packet};
  try{channel?.postMessage(msg)}catch{}
  try{localStorage.setItem('leaf_social_broadcast',JSON.stringify({...msg,_ts:now(),_salt:uuid()}))}catch{}
 }
 function sendRTC(packet){
  if(dataChannel?.readyState!=='open')return;
  const data={v:1,...packet};
  try{dataChannel.send(JSON.stringify(data))}catch{}
 }
 function presence(announce=true){
  const self=compactPresence();
  if(announce){sendLocal({kind:'presence',peer:self});sendRTC({kind:'presence',peer:self})}
  updateCounts();
 }
 function seen(id){
  if(!id||state.seen.has(id))return true;
  state.seen.add(id);
  if(state.seen.size>1000)state.seen.clear();
  return false;
 }
 function acceptPacket(p,source){
  if(!p||p.v!==1||typeof p!=='object')return;
  if(p.kind==='presence'||p.kind==='hello'){
   const user=p.peer;
   if(!user||typeof user.id!=='string'||user.id===tabId)return;
   const peer={id:safe(user.id,100),nick:safe(user.nick,12),scope:safe(user.scope,120),roomId:safe(user.roomId,70),
    region:['north','south'].includes(user.region)?user.region:'north',
    district:safe(user.district,40),view:safe(user.view,15),avatar:Math.max(0,Math.min(avatars.length-1,Number(user.avatar)||0)),
    position:user.position&&Number.isFinite(user.position.x)&&Number.isFinite(user.position.y)?user.position:null,last:now(),source};
   state.peers.set(peer.id,peer);
   if(p.kind==='hello'){sendLocal({kind:'presence',peer:compactPresence()});sendRTC({kind:'presence',peer:compactPresence()})}
   updateCounts();return;
  }
  if(p.kind==='bye'){
   if(typeof p.id==='string')state.peers.delete(p.id);
   updateCounts();return;
  }
  if(p.kind==='chat'){
   if(typeof p.id!=='string'||seen(p.id))return;
   const entry={id:safe(p.id,90),scope:safe(p.scope,120),user:safe(p.user,12),text:safe(p.text,250),sender:safe(p.sender,100),time:Number(p.time)||now()};
   if(!entry.scope||!entry.text)return;
   storeMessage(entry);
   if(source!=='rtc')sendRTC({kind:'chat',...entry});
   if(source==='rtc')sendLocal({kind:'chat',...entry});
   if(entry.scope===state.scope){renderMessage(entry);showBubble(entry.sender,entry.text)}
   return;
  }
  if(p.kind==='bulletinPost'){
    if(p.post&&typeof p.post.id==='string'){
      const post={id:safe(p.post.id,80),author:safe(p.post.author,12),title:safe(p.post.title,65),
       body:safe(p.post.body,800),created:Number(p.post.created)||now()};
      if(post.title&&post.body&&!boardPosts().some(x=>x.id===post.id)){
        const all=boardPosts();all.push(post);saveBoardPosts(all);
        if(state.view==='board')renderBoardList();
        if(source==='rtc')sendLocal({kind:'bulletinPost',post});
        else if(source==='local')sendRTC({kind:'bulletinPost',post});
      }
    }
    return;
  }
  if(p.kind==='roomCreated'||p.kind==='roomClosed'){
   if(p.roomCreated||p.kind==='roomCreated'){
     const r=p.room;
     if(r&&typeof r.id==='string'&&!roomById(r.id)&&state.rooms.length<200){
       const incoming={id:safe(r.id,70),name:safe(r.name,26),region:r.region==='south'?'south':'north',
        district:safe(r.district,36),owner:safe(r.owner,24),passwordProof:safe(r.passwordProof,65),passwordSalt:safe(r.passwordSalt,75),
        background:Math.max(0,Math.min(5,Number(r.background)||2)),created:Number(r.created)||now()};
       state.rooms.push(incoming);saveRooms();if(state.view==='directory')renderDirectory();
     }
   }else{
     state.rooms=state.rooms.filter(r=>r.id!==p.roomId);saveRooms();
     if(state.roomId===p.roomId)openDirectory();
     else if(state.view==='directory')renderDirectory();
   }
   updateCounts();return;
  }
  if(p.kind==='move'&&p.position&&Number.isFinite(p.position.x)&&Number.isFinite(p.position.y)){
   const who=state.peers.get(p.from);if(who){who.position=p.position;who.last=now();renderOccupants()}return;
  }
 }
 function historyKey(s){return 'leaf_social_log_'+encodeURIComponent(s).slice(0,140)}
 function roomHistory(s){
  try{
   const all=JSON.parse(localStorage.getItem(historyKey(s))||'[]');
   return Array.isArray(all)?all.slice(-90):[];
  }catch{return []}
 }
 function storeMessage(entry){
  const list=roomHistory(entry.scope);
  if(list.some(x=>x.id===entry.id))return;
  list.push(entry);
  try{localStorage.setItem(historyKey(entry.scope),JSON.stringify(list.slice(-90)))}catch{}
 }
 function renderMessage(m){
  const el=document.createElement('div');el.className='social-chat-message';
  const time=document.createElement('time');time.textContent=new Date(m.time).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  const name=document.createElement('b');name.textContent=m.user+'　';
  const msg=document.createElement('span');msg.textContent=m.text;
  el.append(time,name,msg);$('chat-log')?.append(el);
  const log=$('chat-log');if(log){while(log.childElementCount>110)log.firstElementChild.remove();log.scrollTop=log.scrollHeight}
 }
 function systemLine(message){
  const log=$('chat-log');if(!log)return;
  const line=document.createElement('div');line.className='social-system-line';line.textContent='[안내] '+message;
  log.append(line);log.scrollTop=log.scrollHeight;
 }
 function renderHistory(){
  const log=$('chat-log');if(!log)return;
  log.replaceChildren();
  systemLine('원본 4LEAF 채팅 화면 복원 · 이 브라우저 탭 및 직접 연결된 사용자만 표시됩니다.');
  for(const item of roomHistory(state.scope))renderMessage(item);
 }
 function publishText(text){
  const v=safe(text,250);if(!v)return;
  if(v==='/help'){systemLine('/nick 별명 · /me 행동 · 각 대화방에서 접속자끼리 대화할 수 있습니다.');return}
  if(v.startsWith('/nick ')){$('rename')?.click();return}
  const content=v.startsWith('/me ')?'＊ '+nick()+' '+v.slice(4):v;
  const item={kind:'chat',id:uuid(),scope:state.scope,user:nick(),text:content,sender:tabId,time:now()};
  storeMessage(item);renderMessage(item);showBubble(tabId,content);sendLocal(item);sendRTC(item);
 }
 function onlinePeers(sc=state.scope){
  const fresh=[compactPresence()];
  for(const peer of state.peers.values())if(now()-peer.last<17000&&peer.id!==tabId)fresh.push(peer);
  return fresh.filter(x=>x.scope===sc);
 }
 function everyoneCount(){
  return 1+[...state.peers.values()].filter(p=>now()-p.last<17000).length;
 }
 function updateCounts(){
  if(!sceneInit)return;
  const c=$('social-online-count');if(c)c.textContent=onlinePeers().length+'명';
  const group=$('social-peer-list');
  if(group){group.replaceChildren();onlinePeers().forEach(user=>{
    const row=document.createElement('div');row.className='social-user-row';
    const status=document.createElement('i');status.className='social-status-led';
    const name=document.createElement('b');name.textContent=user.nick+(user.id===tabId?' (나)':'');
    const last=document.createElement('small');last.textContent='접속 중';
    row.append(status,name,last);group.append(row);
  })}
  const global=$('online-list');
  if(global&&$('rooms')&&!$('rooms').classList.contains('hidden')&&['town','directory','room'].includes(state.view)){
    global.replaceChildren();
    const h=document.createElement('div');h.textContent=state.scope+'　실접속 '+onlinePeers().length;global.append(h);
    onlinePeers().forEach(p=>{const d=document.createElement('div');d.textContent='♧ '+p.nick+(p.id===tabId?' (나)':'');global.append(d)});
  }
  const rooms=$('social-directory-list');
  if(rooms&&state.view==='directory')for(const row of rooms.querySelectorAll('[data-room]')){
    const count=onlinePeers('room:'+row.dataset.room).length;
    const badge=row.querySelector('.social-room-users');
    if(badge)badge.textContent=count+'명 접속';
  }
  if(state.view==='room')renderOccupants();
 }
 function changeScope(next){
  state.scope=next;
  renderHistory();
  presence();
  updateCounts();
 }
 function updateHeader(){
  const name=$('social-location-title');
  if(name)name.textContent=state.view==='board'?'레코르다블 · 기사단 게시판':state.view==='room'?('Chatting Room · '+(currentRoom()?.name||'채팅방')):
    state.view==='directory'?(state.district+' · 채팅방 목록'):
    (REGIONS[state.region]?.title||'하이아칸')+' · 채팅 지역';
  const bread=$('social-breadcrumb');
  if(bread)bread.textContent=state.view==='board'?'RECORDABLE › 기사단 게시판':(REGIONS[state.region]?.title||'하이아칸')+(state.view==='town'?'':' › '+state.district)+(state.view==='room'?' › '+(currentRoom()?.name||''): '');
  const back=$('social-back');if(back)back.textContent=state.view==='board'?'← 월드맵':state.view==='room'?'← 채팅방 목록':state.view==='directory'?'← 채팅 지역':'← 월드맵';
  const note=$('chatroom-name');if(note)note.textContent=state.view==='board'?'BULLETIN CHANNEL':state.view==='room'?(currentRoom()?.name||'CHATTING ROOM'):state.view==='town'?'TOWN CHANNEL':'ROOM LIST';
 }
 function roomTemplate(background){return './original/ChatRoom/room'+background+'.png'}
 function fit(){
  const region=$stage(),frame=$('social-image-frame');if(!region||!frame)return;
  const scale=Math.min(region.clientWidth/W,region.clientHeight/H);
  frame.style.transform='translate3d('+((region.clientWidth-W*scale)/2)+'px,'+((region.clientHeight-H*scale)/2)+'px,0) scale('+scale+')';
 }
 function addClassicRoomToolbar(){
  const header=$root()?.querySelector('.social-header');if(!header)return;
  // Native MainFrame/toolbarbtn.pak: 120×270, four 30px button states
  // in columns and nine distinct 30px tool icons in rows.
  const bar=document.createElement('nav');
  bar.className='social-classic-toolbar';
  bar.setAttribute('aria-label','원본 포리프 채팅방 도구모음');
  const actions=[
   {row:0,title:'채팅방 목록',act:()=>openDirectory()},
   {row:2,title:'기사단 게시판',act:()=>{openBoard();window.__ROG_TEST__?.go('rooms')}},
   {row:3,title:'아바타 선택',act:()=>openAvatarMenu()},
   {row:4,title:'매직카덴',act:()=>window.__ROG_TEST__?.go('shop')},
   {row:7,title:'게임 안내',act:()=>window.__ROG_TEST__?.go('help-screen')},
   {row:8,title:'월드맵으로 돌아가기',act:()=>window.__ROG_TEST__?.go('sky')}
  ];
  for(const item of actions){
   const button=document.createElement('button');
   button.type='button';button.className='social-original-tool';
   button.style.setProperty('--icon-row',String(item.row));
   button.style.setProperty('--icon-y',(-30*item.row)+'px');
   button.title=item.title;button.setAttribute('aria-label',item.title);
   button.addEventListener('click',item.act);
   bar.append(button);
  }
  header.append(bar);
 }
 function build(){
  const root=$root();if(!root)return;
  root.replaceChildren();root.classList.add('leaf-social-scene');
  root.innerHTML='<div class="social-header"><div><strong id="social-location-title">하이아칸</strong><small id="social-breadcrumb"></small></div><div class="social-header-tools"><span id="social-online-count">1명</span><button id="social-invite" type="button">연결 초대</button><button id="social-back" type="button">← 월드맵</button></div></div><div class="social-layout"><div id="social-stage" class="social-stage"><div id="social-image-frame" class="social-image-frame"></div></div><aside class="social-user-panel"><h4>♧　USER LIST</h4><div id="social-peer-list"></div><p>같은 사이트의 다른 탭과 직접 연결한 상대방이 표시됩니다.</p></aside></div>';
  addClassicRoomToolbar();
  $('social-back').onclick=back;
  $('social-invite').onclick=openInvite;
  sceneInit=true;
  if('ResizeObserver' in window){resize=new ResizeObserver(fit);resize.observe($stage())}
  render();
 }
 function regionState(region){
  state.region=region==='south'?'south':'north';
  state.district=REGIONS[state.region].districts[3][0];
  state.view='town';state.roomId=null;state.position={x:52,y:76};
 }
 function openRegion(region){
  regionState(region);if(sceneInit)render();
 }
 function back(){
  if(state.view==='room'){openDirectory();return}
  if(state.view==='directory'){state.view='town';state.roomId=null;render();return}
  window.__ROG_TEST__?.go('sky');
 }
 function render(){
  if(!sceneInit)return;
  $root()?.classList.toggle('classic-chat-room',state.view==='room');
  const frame=$('social-image-frame');frame.replaceChildren();
  if(state.view==='board')renderBulletin(frame);
  if(state.view==='town')renderTown(frame);
  if(state.view==='directory')renderDirectory(frame);
  if(state.view==='room')renderRoom(frame);
  updateHeader();fit();changeScope(scope());
 }

 function boardPosts(){
   try{const all=JSON.parse(localStorage.getItem('leaf_recordable_posts_v1')||'[]');
     return Array.isArray(all)?all.slice(-100).filter(x=>x&&typeof x.title==='string'):[]}
   catch{return []}
 }
 function saveBoardPosts(posts){try{localStorage.setItem('leaf_recordable_posts_v1',JSON.stringify(posts.slice(-100)))}catch{}}
 function openBoard(){
   state.region='north';state.view='board';state.roomId=null;
   if(sceneInit)render();
 }
 function renderBulletin(frame){
   frame.className='social-image-frame social-bulletin';
   frame.style.backgroundImage='url("./original/WorldMap/worldmapback.png")';
   frame.innerHTML='<section class="recordable-board"><header><div><b>RECORDABLE</b><small>레코르다블 · 기사단 게시판</small></div><button id="recordable-create">+ 글쓰기</button></header><div class="recordable-list"><div class="recordable-columns"><b>NO.</b><b>제목</b><b>작성자</b><b>작성일</b></div><div id="recordable-rows"></div></div><footer>게시글은 브라우저에 보관되며 연결된 상대방과 공유됩니다. 원작 운영 게시판과는 별개입니다.</footer></section>';
   $('recordable-create').onclick=createBoardPost;
   renderBoardList();
 }
 function renderBoardList(){
   const list=$('recordable-rows');if(!list)return;
   list.replaceChildren();
   const posts=boardPosts().reverse();
   if(!posts.length){
     const empty=document.createElement('p');empty.className='recordable-empty';
     empty.textContent='첫 게시글을 작성해 주세요. · 원작 기사단 게시판 복원';
     list.append(empty);return;
   }
   posts.forEach((post,i)=>{
     const row=document.createElement('button');row.className='recordable-row';
     const no=document.createElement('span');no.textContent=String(posts.length-i);
     const title=document.createElement('b');title.textContent=post.title;
     const author=document.createElement('span');author.textContent=post.author;
     const date=document.createElement('time');date.textContent=new Date(post.created).toLocaleDateString('ko-KR');
     row.append(no,title,author,date);
     row.onclick=()=>{const body=document.createElement('article');body.className='recordable-article';
       const h=document.createElement('h3');h.textContent=post.title;
       const meta=document.createElement('small');meta.textContent=post.author+' · '+new Date(post.created).toLocaleString('ko-KR');
       const content=document.createElement('p');content.textContent=post.body;
       body.append(h,meta,content);popup('게시글 열람',body);
     };
     list.append(row);
   });
 }
 function createBoardPost(){
   const form=document.createElement('form');form.className='social-modal-form recordable-compose';
   form.innerHTML='<label>제목<input name="title" maxlength="65" required placeholder="제목을 입력하세요"></label><label>내용<textarea name="body" maxlength="800" required placeholder="내용을 작성하세요"></textarea></label><button type="submit">게시글 등록</button>';
   form.onsubmit=e=>{e.preventDefault();const input=new FormData(form);const title=safe(input.get('title'),65),body=safe(input.get('body'),800);
     if(!title||!body)return;
     const post={id:uuid(),author:nick(),title,body,created:now()};
     const posts=boardPosts();posts.push(post);saveBoardPosts(posts);
     sendLocal({kind:'bulletinPost',post});sendRTC({kind:'bulletinPost',post});
     closePopup();renderBoardList();
   };
   popup('레코르다블 · 기사단 글쓰기',form);
 }
 function renderTown(frame){
  frame.className='social-image-frame social-town-map';
  frame.style.backgroundImage='url("./original/ChatTown/'+REGIONS[state.region].art+'.png")';
  REGIONS[state.region].districts.forEach(([name,x,y,w,h],idx)=>{
   const b=document.createElement('button');b.className='social-district-hotspot';b.type='button';
   b.style.cssText='left:'+x+'px;top:'+y+'px;width:'+w+'px;height:'+h+'px;';
   b.title=name+' · 채팅방 입장';
   b.setAttribute('aria-label',name+' 채팅 지역');
   const count=onlinePeers('district:'+state.region+':'+name).length;
   if(count){const countLabel=document.createElement('span');countLabel.textContent=count+'명';b.append(countLabel)}
   b.onclick=()=>{state.district=name;state.view='directory';state.roomId=null;render()};
   frame.append(b);
  });
 }
 function renderDirectory(frame=$('social-image-frame')){
  if(state.view!=='directory')return;
  frame.className='social-image-frame social-room-directory';
  frame.style.backgroundImage='url("./original/ChatTown/'+REGIONS[state.region].art+'.png")';
  frame.innerHTML='<div class="social-directory"><div class="social-directory-heading"><b>CHATTING ROOM · <span id="social-directory-name"></span></b><button id="social-new-room">+ 채팅방 만들기</button></div><div id="social-directory-list"></div><p>접속 인원은 현재 실제로 연결된 탭과 직접 연결 사용자 기준입니다.</p></div>';
  $('social-directory-name').textContent=state.district;
  $('social-new-room').onclick=showCreateRoom;
  const list=$('social-directory-list');
  for(const [i,r] of catalogue().entries()){
   const b=document.createElement('button');b.className='social-directory-row';b.dataset.room=r.id;
   const num=document.createElement('span');num.className='social-room-number';num.textContent=String(i+1).padStart(2,'0');
   const name=document.createElement('b');name.textContent=r.name;
   const lock=document.createElement('small');lock.textContent=r.passwordProof?'🔒':'♧';
   const occupancy=document.createElement('span');occupancy.className='social-room-users';occupancy.textContent=onlinePeers('room:'+r.id).length+'명 접속';
   const arrow=document.createElement('span');arrow.textContent='입장 ›';
   b.append(num,lock,name,occupancy,arrow);
   b.onclick=()=>joinRoom(r.id);
   list.append(b);
  }
  updateCounts();
 }
 function joinRoom(id){
  const room=roomById(id);if(!room)return;
  if(room.passwordProof){
   askText('비공개 채팅방','방 비밀번호',true,async value=>{
    try{
     if(await deriveRoomProof(value,room.passwordSalt)===room.passwordProof)enterRoom(room);
     else systemLine('비밀번호가 일치하지 않습니다.');
    }catch{systemLine('비밀번호 검증을 진행할 수 없습니다.')}
   });return;
  }
  enterRoom(room);
 }
 function openDirectory(){
  state.view='directory';state.roomId=null;render();
 }
 function enterRoom(room){
  if(room.region!==state.region){state.region=room.region}
  state.district=room.district;state.roomId=room.id;state.view='room';
  const seats=roomSeats(room.background);
  const hash=[...tabId].reduce((a,c)=>(a*31+c.charCodeAt(0))>>>0,0);
  state.position={...seats[hash%seats.length]};
  render();
 }
 function roomAvatar(user,index){
  const figure=document.createElement('button');figure.className='social-avatar';
  figure.type='button';figure.dataset.peer=user.id;
  const pos=place(user,index);figure.style.left=pos.x+'%';figure.style.top=pos.y+'%';
  const sprite=document.createElement('img');sprite.alt='';sprite.src='./original/Registry/'+avatars[user.avatar%avatars.length]+'.png';
  const tag=document.createElement('span');tag.className='social-avatar-name';tag.textContent=user.nick;
  figure.append(sprite,tag);
  if(user.id===tabId)figure.classList.add('self');
  figure.onclick=e=>{
   e.stopPropagation();
   if(user.id===tabId)openAvatarMenu();
   else showPeerInfo(user);
  };
  return figure;
 }
 function renderOccupants(){
  if(state.view!=='room')return;
  const layer=$('social-avatar-layer');if(!layer)return;
  const users=onlinePeers('room:'+state.roomId);
  for(const stale of [...layer.querySelectorAll('.social-avatar')]){
   if(!users.some(p=>p.id===stale.dataset.peer))stale.remove();
  }
  const occupied=new Set();
  // Stable order keeps each avatar at the same snapped seat on every client.
  users.sort((a,b)=>String(a.id).localeCompare(String(b.id)));
  users.forEach((user,i)=>{
   let node=[...layer.querySelectorAll('.social-avatar')].find(el=>el.dataset.peer===user.id);
   if(!node){node=roomAvatar(user,i);layer.append(node)}
   const pos=place(user,i,occupied);
   occupied.add(pos.seat);
   node.dataset.seat=String(pos.seat);
   node.style.left=pos.x+'%';node.style.top=pos.y+'%';
   node.style.zIndex=String(Math.round(pos.y));
   node.querySelector('.social-avatar-name').textContent=user.nick;
   node.classList.toggle('self',user.id===tabId);
  });
 }
 function showBubble(sender,text){
  if(state.view!=='room')return;
  const layer=$('social-avatar-layer');if(!layer)return;
  const node=[...layer.querySelectorAll('.social-avatar')].find(el=>el.dataset.peer===sender);
  if(!node)return;
  node.querySelector('.social-speech')?.remove();
  const bubble=document.createElement('div');bubble.className='social-speech';bubble.textContent=safe(text,55);bubble.setAttribute('role','status');node.append(bubble);
  setTimeout(()=>{if(bubble.isConnected)bubble.remove()},5000);
 }
 // The original T sprites (table/furniture) are independent foreground layers.
 // They use a red chroma key in the archived client, not CSS transparency.
 function addRoomForeground(layer,background){
  const art=roomLayout(background).foreground;if(!art)return;
  const canvas=document.createElement('canvas');
  canvas.className='social-room-foreground';
  canvas.setAttribute('aria-hidden','true');
  canvas.dataset.source=art.file;
  canvas.style.cssText='left:'+art.x+'px;top:'+art.y+'px;width:'+art.w+
   'px;height:'+art.h+'px;z-index:'+art.depth+';';
  layer.append(canvas);
  const img=new Image();
  img.onload=()=>{
   canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});
   ctx.drawImage(img,0,0);
   const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
   // Remove only the near-pure red bitmap transparency; keep warm table art.
   for(let i=0;i<pixels.data.length;i+=4){
    const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
    if(r>=242&&g<=18&&b<=18)pixels.data[i+3]=0;
   }
   ctx.putImageData(pixels,0,0);
   canvas.dataset.ready='true';
  };
  img.onerror=()=>{canvas.dataset.ready='error';console.error('Missing original room foreground:',img.src)};
  img.src='./original/ChatRoom/'+art.file+'.png';
 }
 function renderRoom(frame){
  frame.className='social-image-frame social-interior';
  const room=currentRoom();
  if(!room){openDirectory();return}
  frame.style.backgroundImage='url("'+roomTemplate(room.background)+'")';
  const avatarLayer=document.createElement('div');avatarLayer.className='social-avatar-layer';avatarLayer.id='social-avatar-layer';
  frame.append(avatarLayer);
  addRoomForeground(avatarLayer,room.background);
  const controls=document.createElement('div');controls.className='social-interior-controls';
  const outfit=document.createElement('button');outfit.textContent='캐릭터 변경';outfit.onclick=openAvatarMenu;controls.append(outfit);
  if(!room.preset&&room.owner===nick()){
   const close=document.createElement('button');close.textContent='방 닫기';close.onclick=()=>closeRoom(room.id);controls.append(close);
  }
  frame.append(controls);
  frame.addEventListener('click',e=>{
   if(e.target.closest('button')||e.target.closest('.social-room-title'))return;
   const rect=frame.getBoundingClientRect();const x=100*(e.clientX-rect.left)/rect.width,y=100*(e.clientY-rect.top)/rect.height;
   const others=onlinePeers('room:'+state.roomId).filter(p=>p.id!==tabId);
   const occupied=new Set(others.map(p=>closestSeat(p.position?.x??52,p.position?.y??76)));
   const seat=closestSeat(x,y,occupied);
   state.position={...roomSeats()[seat]};
   sendLocal({kind:'move',position:state.position});sendRTC({kind:'move',from:tabId,position:state.position});presence();
   renderOccupants();
  });
  renderOccupants();
 }
 function showPeerInfo(user){
  const content=document.createElement('div');content.className='social-peer-card';
  const img=document.createElement('img');img.src='./original/Registry/'+avatars[user.avatar%avatars.length]+'.png';img.alt='';
  const info=document.createElement('div');info.textContent=user.nick+' · 현재 접속 중';
  content.append(img,info);popup('접속자 정보',content);
 }
 function openAvatarMenu(){
  const content=document.createElement('div');content.className='social-avatar-chooser';
  avatars.forEach((filename,i)=>{
   const b=document.createElement('button');b.type='button';b.title='캐릭터 '+(i+1);
   const img=document.createElement('img');img.src='./original/Registry/'+filename+'.png';img.alt='';
   b.append(img);b.onclick=()=>{state.avatar=i;saveAvatar();closePopup();presence();renderOccupants()};
   content.append(b);
  });popup('아바타 선택 · 원본 포리프 캐릭터',content);
 }
 function saveAvatar(){try{localStorage.setItem('leaf_social_avatar',String(state.avatar))}catch{}}
 function popup(title,body){
  closePopup();
  const root=document.createElement('div');root.className='social-modal';root.id='social-modal';
  const panel=document.createElement('div');panel.className='social-modal-panel';
  const header=document.createElement('div');header.className='social-modal-title';
  const span=document.createElement('b');span.textContent=title;
  const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','닫기');close.onclick=closePopup;
  header.append(span,close);panel.append(header,body);root.append(panel);
  root.addEventListener('click',e=>{if(e.target===root)closePopup()});
  document.body.append(root);return panel;
 }
 function closePopup(){$('social-modal')?.remove()}
 function askText(title,placeholder,password,cb){
  const body=document.createElement('form');body.className='social-modal-form';
  const input=document.createElement('input');input.type=password?'password':'text';input.maxLength=36;input.placeholder=placeholder;input.required=true;
  const submit=document.createElement('button');submit.textContent='확인';submit.type='submit';
  body.append(input,submit);body.onsubmit=e=>{e.preventDefault();const val=input.value;closePopup();cb(val)};
  popup(title,body);input.focus();
 }
 function showCreateRoom(){
  const body=document.createElement('form');body.className='social-modal-form';
  body.innerHTML='<label>방 제목<input name="name" placeholder="방 이름" maxlength="26" required></label><label>배경<select name="background"><option value="2">서재</option><option value="3">클로버 응접실</option><option value="5">벽난로가 있는 방</option><option value="4">햇빛이 드는 방</option><option value="0">숲속 광장</option><option value="1">숲속 오솔길</option></select></label><label>비밀번호 (선택)<input name="password" type="password" maxlength="24" placeholder="비우면 공개방"></label><button type="submit">방 만들기</button>';
  body.onsubmit=async e=>{
   e.preventDefault();const form=new FormData(body);
   const name=safe(form.get('name'),26);
   if(!name)return;
   const password=safe(form.get('password'),24),salt=password?uuid():'';
   if(password&&password.length<6){const field=body.querySelector('[name="password"]');field.setCustomValidity('비밀번호는 6자 이상이어야 합니다.');field.reportValidity();return}
   const proof=password?await deriveRoomProof(password,salt):'';
   const room={id:uuid(),name,region:state.region,district:state.district,owner:nick(),
    passwordProof:proof,passwordSalt:salt,background:Number(form.get('background'))||2,created:now()};
   state.rooms.push(room);saveRooms();sendLocal({kind:'roomCreated',room});sendRTC({kind:'roomCreated',room});
   closePopup();enterRoom(room);
  };
  popup('새로운 4LEAF 채팅방 개설',body);
 }
 function closeRoom(roomId){
  const room=roomById(roomId);
  if(!room||room.preset||room.owner!==nick())return;
  state.rooms=state.rooms.filter(r=>r.id!==roomId);
  saveRooms();sendLocal({kind:'roomClosed',roomId});sendRTC({kind:'roomClosed',roomId});
  openDirectory();
 }
 function transportMessage(p,source){
  acceptPacket(p,source);
 }
 async function openInvite(){
  const panel=document.createElement('div');panel.className='social-connect-panel';
  panel.innerHTML='<p>별도 서버를 사용하지 않고 브라우저끼리 직접 연결합니다. 양쪽 기기에서 생성한 코드를 복사·교환해야 하며 네트워크에 따라 연결되지 않을 수 있습니다.</p><div class="social-connect-buttons"><button id="social-create-offer">① 초대 코드 만들기</button><button id="social-make-answer">② 상대 초대 수락</button></div><label>내 초대 코드<textarea id="social-output-offer" readonly rows="3"></textarea></label><button id="social-copy-offer">초대 복사</button><label>상대 초대 코드<textarea id="social-input-offer" rows="3"></textarea></label><label>내 응답 코드<textarea id="social-output-answer" readonly rows="3"></textarea></label><button id="social-copy-answer">응답 복사</button><label>상대 응답 코드<textarea id="social-input-answer" rows="3"></textarea></label><button id="social-apply-answer">③ 응답 연결</button><p id="social-connect-state" role="status"></p>';
  popup('4LEAF Messenger · 다른 기기 연결',panel);
  const status=text=>{const el=$('social-connect-state');if(el)el.textContent=text};
  const options={iceServers:[{urls:'stun:stun.l.google.com:19302'},{urls:'stun:stun1.l.google.com:19302'}]};
  const encode=obj=>btoa(JSON.stringify(obj));
  const decode=(value,type)=>{let result;try{result=JSON.parse(atob(String(value).replace(/\s/g,'')))}catch{throw Error('연결 코드 형식이 올바르지 않습니다.')};if(result?.type!==type||typeof result.sdp!=='string'||!result.sdp.startsWith('v=0')||result.sdp.length>90000)throw Error('잘못된 연결 코드입니다.');return result};
  const gather=pc=>new Promise(resolve=>{if(pc.iceGatheringState==='complete')return resolve();let timer;const finish=()=>{pc.removeEventListener('icegatheringstatechange',change);clearTimeout(timer);resolve()};const change=()=>{if(pc.iceGatheringState==='complete')finish()};pc.addEventListener('icegatheringstatechange',change);timer=setTimeout(finish,10500)});
  const newPeer=role=>{
   if(!('RTCPeerConnection' in window))throw Error('이 브라우저는 WebRTC를 지원하지 않습니다.');
   try{dataChannel?.close();rtc?.close()}catch{}
   rtcRole=role;rtc=new RTCPeerConnection(options);dataChannel=null;
   rtc.ondatachannel=e=>bindRTC(e.channel);
   rtc.onconnectionstatechange=()=>{if(rtc?.connectionState==='failed')status('연결 실패 · 다른 네트워크에서 다시 시도하세요.')};
   return rtc;
  };
  const bindRTC=ch=>{
   dataChannel=ch;
   ch.onopen=()=>{
     status('직접 연결 성공. 이제 채팅 메시지가 두 기기에 실시간으로 전달됩니다.');
     sendRTC({kind:'hello',peer:compactPresence()});
     if(rtcRole==='host')sendRTC({kind:'syncLocation',region:state.region,district:state.district,roomId:state.roomId,room:currentRoom()});
     presence();
   };
   ch.onclose=()=>{status('직접 연결이 종료됐습니다.');updateCounts()};
   ch.onmessage=e=>{
     if(typeof e.data!=='string'||e.data.length>150000)return;
     let p;try{p=JSON.parse(e.data)}catch{return}
     if(p.kind==='syncLocation'&&rtcRole==='guest'){
       if(p.region&&REGIONS[p.region]){
         state.region=p.region;state.district=safe(p.district,36);
         if(p.room?.id&&!roomById(p.room.id)&&!p.room.preset){state.rooms.push(p.room);saveRooms()}
         if(p.roomId){const room=roomById(p.roomId);if(room)enterRoom(room)}
         else{state.view='directory';render()}
         if($('rooms')?.classList.contains('hidden'))window.__ROG_TEST__?.go('rooms');
       }
       return;
     }
     transportMessage(p,'rtc');
   };
  };
  $('social-create-offer').onclick=async()=>{
   try{
     const pc=newPeer('host');bindRTC(pc.createDataChannel('leaf-chat',{ordered:true}));
     await pc.setLocalDescription(await pc.createOffer());await gather(pc);
     $('social-output-offer').value=encode({type:'offer',sdp:pc.localDescription.sdp});
     status('초대 코드를 상대 기기에 전달하고 응답을 기다리세요.');
   }catch(e){status(e.message)}
  };
  $('social-make-answer').onclick=async()=>{
   try{
     const offer=decode($('social-input-offer').value,'offer'),pc=newPeer('guest');
     await pc.setRemoteDescription({type:'offer',sdp:offer.sdp});
     await pc.setLocalDescription(await pc.createAnswer());await gather(pc);
     $('social-output-answer').value=encode({type:'answer',sdp:pc.localDescription.sdp});
     status('응답 코드를 호스트 기기로 보내세요.');
   }catch(e){status(e.message)}
  };
  $('social-apply-answer').onclick=async()=>{
   try{
     if(!rtc||rtcRole!=='host')throw Error('먼저 초대 코드를 만드세요.');
     const answer=decode($('social-input-answer').value,'answer');
     await rtc.setRemoteDescription({type:'answer',sdp:answer.sdp});
     status('상대와 직접 연결하는 중…');
   }catch(e){status(e.message)}
  };
  const copy=async id=>{
   const field=$(id);if(!field)return;
   try{await navigator.clipboard.writeText(field.value);status('코드를 복사했습니다.')}
   catch{field.select();status('텍스트를 선택했습니다. 직접 복사하세요.')}
  };
  $('social-copy-offer').onclick=()=>copy('social-output-offer');
  $('social-copy-answer').onclick=()=>copy('social-output-answer');
 }
 function installTransport(){
  if('BroadcastChannel' in window){
   channel=new BroadcastChannel('4leaf_social_presence_v3');
   channel.onmessage=e=>{if(e.data?.from===tabId)return;acceptPacket(e.data,'local')};
  }
  window.addEventListener('storage',e=>{
   if(e.key==='leaf_social_broadcast'&&e.newValue){try{const data=JSON.parse(e.newValue);if(data.from!==tabId)acceptPacket(data,'local')}catch{}}
   if(e.key==='leaf_social_rooms_v3'){state.rooms=loadRooms();if(state.view==='directory')renderDirectory()}
  });
  window.addEventListener('pagehide',()=>{sendLocal({kind:'bye',id:tabId});sendRTC({kind:'bye',id:tabId})});
  pulse=setInterval(()=>{
   presence();
   for(const [id,p] of state.peers)if(now()-p.last>17000)state.peers.delete(id);
   updateCounts();
  },4200);
 }
 function init(){
  try{state.avatar=Math.max(0,Math.min(avatars.length-1,Number(localStorage.getItem('leaf_social_avatar'))||0))}catch{}
  build();installTransport();
  const form=$('chat-form');
  if(form){
   const oldForm=form.onsubmit;
   form.onsubmit=e=>{
     const social=['sky','city','rooms'].some(id=>!$(id)?.classList.contains('hidden'));
     if(!social){if(oldForm)return oldForm.call(form,e);return}
     e.preventDefault();const input=$('message'),v=input.value.trim();input.value='';publishText(v);
   };
  }
  window.addEventListener('leaf-route-change',e=>{
    const route=e.detail?.route;
    if(route==='sky')changeScope('world');
    else if(route==='city')changeScope('city');
    else if(route==='rooms')render();
  });
  const oldRename=$('rename')?.onclick;
  if($('rename'))$('rename').onclick=(...args)=>{
   if(oldRename)oldRename(...args);
   setTimeout(presence,700);
  };
  presence();render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 window.__LEAF_SOCIAL__={openRegion,openBoard,openDirectory,joinRoom,enterRoom,createRoom:(name,background=2)=>{
  const room={id:uuid(),name:safe(name,26),region:state.region,district:state.district,owner:nick(),passwordProof:'',passwordSalt:'',background,created:now()};
  state.rooms.push(room);saveRooms();sendLocal({kind:'roomCreated',room});enterRoom(room);return room.id;
 },send:publishText,getState:()=>({region:state.region,district:state.district,view:state.view,scope:state.scope,roomId:state.roomId,people:onlinePeers(),rooms:catalogue()}),
 sendRTC,now,render,transportMessage};
})();