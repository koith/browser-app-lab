'use strict';
/* ChatTown/ChatRoom.pak social reconstruction.
   Actual messages and real occupant counts: BroadcastChannel across tabs and
   optional encrypted WebRTC DataChannel between two devices. No fake online NPCs. */
(function(){
 const $=id=>document.getElementById(id);
 const W=794,H=528;
 const REGIONS={
  north:{title:'북 하이아칸',art:'northback',districts:[
   ['실버 호라이즌',72,55,164,91],['화이트 크리스탈',253,95,165,91],['퓨어 시티',433,81,167,93],['샤이닝 브리즈',608,58,165,101],
   ['윈트리 아이스',35,193,169,99],['스노우 폴',226,237,168,95],['스위트 자스민',568,194,178,95],['그린 에메랄드',401,284,168,94]
  ]},
  south:{title:'남 하이아칸',art:'southback',districts:[
   ['블루 사파이어',65,57,175,91],['헤이즐리 웨이브',253,93,163,96],['미쉘 에메랄드',438,67,170,97],['엘핀 포레스트',608,57,178,95],
   ['아루아 코랄',34,192,170,99],['블랙씨 아린',226,235,166,99],['브라브 지피트',581,193,174,101],['미스틱 머메이드',405,290,171,96]
  ]}
 };
 // Native ChatTown/*.pak selection graphics have 4 horizontal button states
 // (142px per frame) and named rows (74px high). These 16 labels account
 // for every extracted Plain/Sea/Snow button entry: never invent a hover glow.
 const TOWN_SIGN_SPRITES={
  '실버 호라이즌':['snowbtn',0],'화이트 크리스탈':['snowbtn',1],
  '퓨어 시티':['snowbtn',2],'윈트리 아이스':['snowbtn',3],'스노우 폴':['snowbtn',4],
  '샤이닝 브리즈':['plainbtn',0],'스위트 자스민':['plainbtn',1],
  '그린 에메랄드':['plainbtn',2],'미쉘 에메랄드':['plainbtn',3],
  '엘핀 포레스트':['plainbtn',4],'브라브 지피트':['plainbtn',5],
  '블루 사파이어':['seabtn',0],'헤이즐리 웨이브':['seabtn',1],
  '아루아 코랄':['seabtn',2],'블랙씨 아린':['seabtn',3],
  '미스틱 머메이드':['seabtn',4]
 };
 // Measured by matching the unselected 142x74 source sprite against each
 // 794x404 native ChatTown backdrop. Both north and south use the same sign
 // anchors; source-template normalized correlations range ~0.969..0.996.
 const TOWN_SIGN_PIXEL_ANCHORS=[[85,63],[265,104],[448,88],[625,69],
                               [48,199],[239,244],[588,203],[417,295]];
 const originalTemplates=[2,3,5,4,0,1];
 // The same original ChatTown client also runs offline. When a separate HTTPS
 // authority is configured, remote occupancy/rooms replace browser guesses.
 const central=window.__LEAF_CENTRAL_CHAT__||{enabled:false};
 const centralRooms=new Map(),centralCounts=new Map();
 // Native v0.9 ChatTown supported a spatial room area (up to 200 rooms per
 // town per the 2002 announcement). Exact historical room positions/labels
 // are not available in the recovered image assets. These are deterministic,
 // unoccupied, permanently accessible restoration rooms, NOT claimed to be
 // a transcript of the original service's room catalogue.
 const ROOM_MAP={width:1480,height:1120};
 // Original IMG/bgtile.png is 725x485 and repeats across the estate.
 // Register unoccupied public-room hit areas over actual huts/building art,
 // not unrelated blank terrain underneath invented wooden rectangles.
 // The exact 0.9 server's room layout is still not recovered.
 const PUBLIC_POSITIONS=[
  [14,75],    // tile (0,0): straw hut at ~56x109
  [275,17],   // tile (0,0): timber building at ~319x54
  [435,115],  // tile (0,0): green-roof house at ~487x158
  [739,75],   // tile (1,0): same native hut in repeated terrain
  [1160,115], // tile (1,0): red-roof house
  [435,600],  // tile (0,1): green-roof house
  [739,560],  // tile (1,1): first thatch-roof hut
  [1025,788]  // tile (1,1): source lower green-roof house
 ];
 const staticRooms=new Map();
 for(const region of ['north','south']){
  REGIONS[region].districts.forEach(([district],di)=>{
   for(let i=0;i<PUBLIC_POSITIONS.length;i++){
    const id='leaf-public-'+region+'-'+di+'-'+i;
    staticRooms.set(id,{id,name:'채팅방 '+String(di*8+i+1).padStart(2,'0'),region,district,
     owner:'',ownerId:'',passwordProof:'',passwordSalt:'',background:originalTemplates[i%originalTemplates.length],
     capacity:12,created:0,preset:true,mapX:PUBLIC_POSITIONS[i][0],mapY:PUBLIC_POSITIONS[i][1]});
   }
  });
 }
 const publicCatalogue=()=>[...staticRooms.values()].filter(r=>r.region===state.region&&r.district===state.district);

 // A historic 2-person chat-room event is documented. Other limits are
 // restoration controls, not claims about the original server's room menu.
 const allowedCapacity=n=>[2,4,8,12].includes(Number(n))?Number(n):12;
 const allowedBackground=n=>Number.isInteger(Number(n))&&Number(n)>=0&&Number(n)<=5?Number(n):2;
 const avatars=['sava00','sava82','sava06','sava01','sava85','sava02','sava84','sava04','sava03','sava83','sava05','sava86'];
 const now=()=>Date.now(),uuid=()=>crypto.randomUUID?.()||Math.random().toString(36).slice(2)+String(Date.now());
 const safe=(s,max=100)=>String(s??'').replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,max);
 // A previous reconstruction mistranscribed the third North Haiacan sign.
 // Preserve rooms already saved under that misspelling when loading storage.
 const sourceDistrict=s=>{const name=safe(s,40);return name==='프레이 시티'?'퓨어 시티':name};
 const tabId=(()=>{try{const key='leaf_social_tab_identity_v1';let id=sessionStorage.getItem(key);if(!id){id=uuid();sessionStorage.setItem(key,id)}return id}catch{return uuid()}})();
 const nick=()=>safe($('profile-name')?.textContent||'Guest',12)||'Guest';
 const state={region:'north',district:REGIONS.north.districts[3][0],view:'town',roomId:null,rooms:loadRooms(),peers:new Map(),seen:new Set(),bubble:null,scope:'world',avatar:0,facing:1,position:{x:52,y:76},roomMapOffsets:Object.create(null)};
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
    id:safe(r.id,70),name:safe(r.name,26),region:r.region,district:sourceDistrict(r.district),owner:safe(r.owner,24),ownerId:safe(r.ownerId||'',100),
    passwordProof:safe(r.passwordProof||'',65),passwordSalt:safe(r.passwordSalt||'',75),background:allowedBackground(r.background),capacity:allowedCapacity(r.capacity),created:Number(r.created)||0
   })):[];
  }catch{return []}
 }
 function saveRooms(){try{localStorage.setItem('leaf_social_rooms_v3',JSON.stringify(state.rooms))}catch{}}
 function currentRoom(){
  return roomById(state.roomId);
 }
 function roomById(id){
  return central.enabled?(centralRooms.get(id)||staticRooms.get(id)||null):
   (state.rooms.find(r=>r.id===id)||staticRooms.get(id)||null);
 }
 // ChatRoom/room0..room5 are six BACKGROUND IMAGES, not six historical
 // permanently open server rooms. A real original server supplied the room
 // catalogue. Only display rooms actually created and shared by participants.
 function catalogue(){
  const source=central.enabled?[...centralRooms.values()]:state.rooms;
  return source.filter(r=>r.region===state.region&&r.district===state.district)
   .sort((a,b)=>b.created-a.created);
 }
 function roomOccupancy(roomId){
  return central.enabled?(centralCounts.get(roomId)||0):onlinePeers('room:'+roomId).length;
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
   avatar:state.avatar,facing:state.facing,position:{x:state.position.x,y:state.position.y},last:now()};
 }
 function sendLocal(packet){
  const msg={v:1,from:tabId,...packet};
  try{channel?.postMessage(msg)}catch{}
  try{localStorage.setItem('leaf_social_broadcast',JSON.stringify({...msg,_ts:now(),_salt:uuid()}))}catch{}
 }
 function sendRTC(packet){
  if(dataChannel?.readyState!=='open')return;
  const data={v:1,from:tabId,...packet};
  try{dataChannel.send(JSON.stringify(data))}catch{}
 }
 function presence(announce=true){
  const self=compactPresence();
  if(announce&&!central.enabled){sendLocal({kind:'presence',peer:self});sendRTC({kind:'presence',peer:self})}
  if(central.enabled&&central.ready&&central.joinedId===state.roomId){
   central.presence({nick:self.nick,avatar:self.avatar,facing:self.facing,position:self.position})
    .catch(e=>console.warn('ChatTown presence:',e.message));
  }
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
    district:sourceDistrict(user.district),view:safe(user.view,15),avatar:Math.max(0,Math.min(avatars.length-1,Number(user.avatar)||0)),
    position:user.position&&Number.isFinite(user.position.x)&&Number.isFinite(user.position.y)?user.position:null,
    facing:user.facing===-1?-1:1,last:now(),source};
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
   if(source==='local')sendRTC({kind:'chat',...entry});
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
        district:sourceDistrict(r.district),owner:safe(r.owner,24),ownerId:safe(r.ownerId||'',100),passwordProof:safe(r.passwordProof,65),passwordSalt:safe(r.passwordSalt,75),
        background:allowedBackground(r.background),capacity:allowedCapacity(r.capacity),created:Number(r.created)||now()};
       state.rooms.push(incoming);saveRooms();if(state.view==='directory')renderDirectory();
     }
   }else{
     const target=roomById(p.roomId);
     // A connected participant must not evict another room owner's members.
     if(target?.ownerId&&p.from!==target.ownerId)return;
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
 // Earlier web reconstructions incorrectly used dice TOWN SELECT channel
 // numbers to partition ChatTown conversations. Read their saved history into
 // the correct chat-only regional scopes, without deleting any old keys.
 function migrateLegacyChatHistory(){
  try{
   const prefix='leaf_social_log_',pending=new Map();
   for(let i=0;i<localStorage.length;i++){
    const key=localStorage.key(i);
    if(!key||!key.startsWith(prefix))continue;
    const oldScope=decodeURIComponent(key.slice(prefix.length));
    const legacy=/^(town|district):(north|south):([a-z]+):([1-4])(?::(.*))?$/.exec(oldScope);
    if(!legacy)continue;
    const target=legacy[1]==='town'?'town:'+legacy[2]:'district:'+legacy[2]+':'+legacy[5];
    if(legacy[1]==='district'&&!legacy[5])continue;
    const entries=JSON.parse(localStorage.getItem(key)||'[]');
    if(!Array.isArray(entries))continue;
    const batch=pending.get(target)||[];
    for(const entry of entries.slice(-90)){
     if(!entry||typeof entry.id!=='string'||typeof entry.text!=='string')continue;
     batch.push({...entry,scope:target});
    }
    pending.set(target,batch);
   }
   for(const [target,batch] of pending){
    const merged=new Map(roomHistory(target).map(entry=>[entry.id,entry]));
    for(const entry of batch)merged.set(entry.id,entry);
    const values=[...merged.values()].sort((a,b)=>(Number(a.time)||0)-(Number(b.time)||0)).slice(-90);
    localStorage.setItem(historyKey(target),JSON.stringify(values));
   }
  }catch(e){console.warn('Legacy chat history migration was skipped:',e)}
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
  // The original conversation pane starts with messages, not a fabricated
  // restoration/debugging banner. Genuine server warnings still use systemLine.
  // Connection-scope information remains available in room controls.
  for(const item of roomHistory(state.scope))renderMessage(item);
 }
 // Contemporary 2001 service press documented /주사위 and /묵 /찌 /빠.
 // They were room chat toys, NOT dice-game rules or RPS match scoring.
 // Native command-specific pictograms are not yet recovered: Unicode is a
 // functional placeholder so the remote player still sees the actual action.
 function originalChatToy(command){
  if(command==='/주사위'){
   const roll=1+Math.floor(Math.random()*6);
   return ['⚀','⚁','⚂','⚃','⚄','⚅'][roll-1]+' 주사위 '+roll;
  }
  return ({'/묵':'✊ 묵','/찌':'✌ 찌','/빠':'✋ 빠'})[command]||null;
 }
 function publishText(text){
  const v=safe(text,250);if(!v)return;
  if(v==='/help'){systemLine('/주사위 · /묵 · /찌 · /빠 · /nick 별명 · /me 행동');return}
  if(v.startsWith('/nick ')){$('rename')?.click();return}
  const content=originalChatToy(v)||(v.startsWith('/me ')?'＊ '+nick()+' '+v.slice(4):v);
  const item={kind:'chat',id:uuid(),scope:state.scope,user:nick(),text:content,sender:tabId,time:now()};
  if(central.enabled&&state.view==='room'&&(!central.ready||central.joinedId!==state.roomId)){
   systemLine('중앙 채팅방에 실제 입장한 뒤 메시지를 보낼 수 있습니다.');return;
  }
  if(central.enabled&&state.view==='room'){
   // Do not create a visible or saved "sent" message before the authority
   // accepts it. Failed sends must not masquerade as genuine chat history.
   central.chat(content).then(result=>{
    const entry=result.entry;if(!entry)return;
    const confirmed={id:entry.id,scope:'room:'+entry.roomId,user:entry.user,
     text:entry.text,sender:tabId,time:entry.time};
    storeMessage(confirmed);
    if(state.view==='room'&&state.roomId===entry.roomId){
     renderMessage(confirmed);showBubble(tabId,entry.text);
    }
   }).catch(e=>systemLine('서버 메시지 전송 실패: '+e.message));
  }else{
   storeMessage(item);renderMessage(item);showBubble(tabId,content);
   sendLocal(item);sendRTC(item)
  }
 }
 function onlinePeers(sc=state.scope){
  const fresh=[compactPresence()];
  for(const peer of state.peers.values()){
   if(central.enabled&&peer.source!=='central')continue;
   if(now()-peer.last<17000&&peer.id!==tabId)fresh.push(peer);
  }
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
    const count=roomOccupancy(row.dataset.room);
    const badge=row.querySelector('.social-room-users');
    if(badge){
     const full=count>=allowedCapacity(roomById(row.dataset.room)?.capacity);
     badge.textContent=count+'/'+allowedCapacity(roomById(row.dataset.room)?.capacity)+'명';
     row.classList.toggle('social-room-full',full);
     const arrow=row.lastElementChild;if(arrow)arrow.textContent=full?'정원 초과':'입장 ›';
    }
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
 // ChatTown northback/southback are native 794×404 illustrations, whereas
 // ChatRoom interiors are native 794×528. Never fill the missing 124 pixels
 // with a fabricated information banner or squeeze the town into room space.
 const sceneHeight=()=>state.view==='town'?404:H;
 function fit(){
  const region=$stage(),frame=$('social-image-frame');if(!region||!frame)return;
  const h=sceneHeight();
  const scale=Math.min(region.clientWidth/W,region.clientHeight/h);
  frame.style.height=h+'px';
  frame.style.transform='translate3d('+((region.clientWidth-W*scale)/2)+'px,'+((region.clientHeight-h*scale)/2)+'px,0) scale('+scale+')';
 }
 // On narrow screens expose the native user list on demand without changing
 // the original source-sized room or fabricating occupants.
 function setMobilePeersOpen(open){
  const root=$root(),button=$('social-peers-toggle');
  const expanded=Boolean(open&&state.view==='room');
  root?.classList.toggle('social-peers-open',expanded);
  if(button){
   button.setAttribute('aria-expanded',String(expanded));
   button.setAttribute('aria-label',expanded?'참여자 목록 닫기':'참여자 목록 보기');
   button.textContent=expanded?'목록 닫기':'참여자';
  }
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
   {row:7,title:'게임 안내',act:()=>$('help')?.click()},
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
  // Keep native ChatRoom/userlist.png in the existing participant panel.
  const peers=document.createElement('button');
  peers.type='button';peers.id='social-peers-toggle';
  peers.className='social-peers-toggle';peers.textContent='참여자';
  peers.setAttribute('aria-controls','social-peer-panel');
  peers.setAttribute('aria-expanded','false');
  peers.setAttribute('aria-label','참여자 목록 보기');
  peers.onclick=()=>setMobilePeersOpen(!$root()?.classList.contains('social-peers-open'));
  bar.append(peers);
  header.append(bar);
 }
 // The recovered ChatRoom/userlist bitmap is the original 150×38 header
 // with vivid-green chroma-key pixels. Composite it instead of drawing the
 // invented English USER LIST label.
 function renderNativeUserListHeader(){
  const canvas=$('social-original-userlist');if(!canvas)return;
  // Browsers taint file:// image canvases even when the art is next to the
  // HTML file. Keep a readable text header in the offline archive rather than
  // throwing SecurityError; public HTTP(S) uses the exact chroma-keyed sprite.
  if(location.protocol==='file:'){canvas.dataset.ready='offline-fallback';return}
  const image=new Image();
  image.onload=()=>{
   if(!canvas.isConnected)return;
   try{
    canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(image,0,0);
    const frame=ctx.getImageData(0,0,canvas.width,canvas.height);
    for(let i=0;i<frame.data.length;i+=4){
     const r=frame.data[i],g=frame.data[i+1],b=frame.data[i+2];
     if(g>220&&r<65&&b<90&&g>r*1.7&&g>b*1.6)frame.data[i+3]=0;
    }
    ctx.putImageData(frame,0,0);
    canvas.dataset.ready='true';
   }catch{canvas.dataset.ready='offline-fallback'}
  };
  image.onerror=()=>{canvas.dataset.ready='error';console.error('Original ChatRoom userlist bitmap missing')};
  image.src='./original/ChatRoom/userlist.png';
 }
 function build(){
  const root=$root();if(!root)return;
  root.replaceChildren();root.classList.add('leaf-social-scene');
  root.innerHTML='<div class="social-header"><div><strong id="social-location-title">하이아칸</strong><small id="social-breadcrumb"></small></div><div class="social-header-tools"><span id="social-online-count">1명</span><button id="social-chat-north" type="button">북 하이아칸</button><button id="social-chat-south" type="button">남 하이아칸</button><button id="social-invite" type="button">연결 초대</button><button id="social-back" type="button">← 월드맵</button></div></div><div class="social-layout"><div id="social-stage" class="social-stage"><div id="social-image-frame" class="social-image-frame"></div></div><aside class="social-user-panel" id="social-peer-panel"><div class="social-user-titlebar"><canvas id="social-original-userlist" width="150" height="38" aria-label="원본 참여자 목록"></canvas><h4>참여자 목록</h4></div><div id="social-peer-list"></div><p>같은 사이트의 다른 탭과 직접 연결한 상대방이 표시됩니다.</p></aside></div>';
  addClassicRoomToolbar();
  renderNativeUserListHeader();
  $('social-back').onclick=back;
  $('social-chat-north').onclick=()=>openRegion('north');
  $('social-chat-south').onclick=()=>openRegion('south');
  $('social-invite').onclick=openInvite;
  root.addEventListener('keydown',event=>{
   if(event.key==='Escape'&&root.classList.contains('social-peers-open')){
    setMobilePeersOpen(false);
    $('social-peers-toggle')?.focus();
    event.stopPropagation();
   }
  });
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
  window.__LEAF_NATIVE_ROOM_PANELS__?.beforeRender();
  if(state.view!=='room')setMobilePeersOpen(false);
  $root()?.classList.toggle('classic-chat-room',state.view==='room');
  $root()?.classList.toggle('native-town-scene',state.view==='town');
  $root()?.classList.toggle('native-directory-scene',state.view==='directory');
  $('social-close-room')?.remove();
  const frame=$('social-image-frame');frame.replaceChildren();
  if(state.view==='board')renderBulletin(frame);
  if(state.view==='town')renderTown(frame);
  if(state.view==='directory')renderDirectory(frame);
  if(state.view==='room')renderRoom(frame);
  updateHeader();fit();changeScope(scope());
  window.__LEAF_NATIVE_ROOM_PANELS__?.afterRender();
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
   const sign=TOWN_SIGN_SPRITES[name];
   if(sign){
    b.dataset.sprite=sign[0];b.dataset.spriteRow=String(sign[1]);
    b.style.setProperty('--town-sprite','url("./original/ChatTown/'+sign[0]+'.png")');
    b.style.setProperty('--town-sprite-y',(-74*sign[1])+'px');
    // Position foreground hover art at the EXACT native backdrop coordinates;
    // the larger approximate interaction hitbox remains unchanged.
    const [sx,sy]=TOWN_SIGN_PIXEL_ANCHORS[idx];
    b.style.setProperty('--town-sprite-left',(sx-x)+'px');
    b.style.setProperty('--town-sprite-top',(sy-y)+'px');
   }
   b.title=name+' · 채팅방 입장';
   b.setAttribute('aria-label',name+' 채팅 지역');
   const count=onlinePeers('district:'+state.region+':'+name).length;
   if(count){const countLabel=document.createElement('span');countLabel.textContent=count+'명';b.append(countLabel)}
   b.onclick=()=>{
    state.district=name;state.view='directory';state.roomId=null;render();
    if(central.enabled&&central.ready)
     central.list(state.region,state.district).catch(e=>systemLine('서버 방 목록 조회 실패: '+e.message));
   };
   frame.append(b);
  });
 }
 // 4LEAF 0.9 expands the world-like room estate, not a linear HTML list.
 // Each room is an independent button; the map can pan on both axes.
 function renderDirectory(frame=$('social-image-frame')){
  if(state.view!=='directory')return;
  frame.className='social-image-frame social-room-directory';
  frame.style.backgroundImage='url("./original/ChatTown/'+REGIONS[state.region].art+'.png")';
  frame.innerHTML='<section class="social-directory"><header class="social-directory-heading"><b>CHATTING TOWN · <span id="social-directory-name"></span></b><button id="social-new-room" type="button">+ 채팅방 만들기</button></header><div id="social-map-viewport" class="social-map-viewport" tabindex="0" aria-label="채팅방 지도. 방향키 또는 드래그로 사방 이동"><div id="social-map-plane" class="social-map-plane"><div class="social-map-terrain" aria-hidden="true"></div><div id="social-directory-list" class="social-map-rooms"></div></div></div><footer class="social-map-toolbar"><span>지도 드래그 · 방향키 / 휠 이동 · 표시 인원은 실제 연결 사용자</span><div class="social-map-directions"><button type="button" data-pan="left" aria-label="왼쪽 이동">◀</button><button type="button" data-pan="up" aria-label="위쪽 이동">▲</button><button type="button" data-pan="down" aria-label="아래쪽 이동">▼</button><button type="button" data-pan="right" aria-label="오른쪽 이동">▶</button></div></footer></section>';
  $('social-directory-name').textContent=state.district;
  $('social-new-room').onclick=showCreateRoom;
  const list=$('social-directory-list'),rooms=[...publicCatalogue(),...catalogue()];
  for(const [i,r] of rooms.entries()){
   const b=document.createElement('button');
   b.type='button';b.className=r.preset?'social-public-room':'social-directory-row';
   b.dataset.room=r.id;b.title=r.name+' · 입장';b.setAttribute('aria-label',r.name+' 채팅방 입장');
   const position=r.preset?{x:r.mapX,y:r.mapY}:customRoomPosition(r);
   b.style.left=position.x+'px';b.style.top=position.y+'px';
   const number=document.createElement('span');number.className='social-room-number';
   number.textContent=r.preset?String(i+1).padStart(2,'0'):'✦';
   const name=document.createElement('b');name.textContent=r.name;
   const lock=document.createElement('small');lock.textContent=r.passwordProof?'🔒':'♧';
   const occupancy=document.createElement('span');occupancy.className='social-room-users';
   occupancy.textContent=roomOccupancy(r.id)+'/'+allowedCapacity(r.capacity)+'명';
   const arrow=document.createElement('span');arrow.className='social-room-action';arrow.textContent='입장 ›';
   b.append(number,lock,name,occupancy,arrow);
   if(!roomHasSpace(r)){b.classList.add('social-room-full');arrow.textContent='정원 초과'}
   b.onclick=()=>joinRoom(r.id);
   list.append(b);
  }
  setupRoomMap();
  updateCounts();
 }
 function customRoomPosition(room){
  // Stable spatial anchors without persisting a view-dependent pixel offset.
  let hash=2166136261;
  for(const ch of room.id){hash^=ch.charCodeAt(0);hash=Math.imul(hash,16777619)}
  return {x:110+(hash>>>0)%1200,y:125+((hash>>>10)>>>0)%860};
 }
 // IMG/bgtile.png is native extracted landscape art, not a screenshot or
 // generated imitation. Recover from intermittent Pages asset errors.
 function loadNativeRoomTerrain(plane){
  const source='./original/IMG/bgtile.png';
  const image=new Image();let retries=0;
  const attempt=()=>{
   if(!plane.isConnected)return;
   image.src=source+(retries?'?retry='+retries+'&at='+Date.now():'');
  };
  image.onload=()=>{
   if(!plane.isConnected)return;
   plane.style.backgroundImage='url("'+image.src+'")';
   plane.dataset.terrain='ready';
  };
  image.onerror=()=>{
   if(!plane.isConnected)return;
   if(retries<5){retries++;plane.dataset.terrain='retrying';
    setTimeout(attempt,Math.min(1800,250*2**retries));
   }else{plane.dataset.terrain='error';console.error('4LEAF original town terrain unavailable:',source)}
  };
  plane.dataset.terrain='loading';attempt();
 }
 function setupRoomMap(){
  const viewport=$('social-map-viewport'),plane=$('social-map-plane');
  if(!viewport||!plane)return;
  loadNativeRoomTerrain(plane);
  const key=state.region+':'+state.district;
  const saved=state.roomMapOffsets[key];
  let x=saved?.x??-(ROOM_MAP.width-viewport.clientWidth)/2;
  let y=saved?.y??-(ROOM_MAP.height-viewport.clientHeight)/2;
  const clamp=(v,max)=>Math.max(Math.min(0,v),Math.min(0,max));
  const placeMap=()=>{x=clamp(x,viewport.clientWidth-ROOM_MAP.width);
   y=clamp(y,viewport.clientHeight-ROOM_MAP.height);
   state.roomMapOffsets[key]={x,y};
   plane.style.transform='translate3d('+Math.round(x)+'px,'+Math.round(y)+'px,0)'};
  const pan=(dx,dy)=>{x+=dx;y+=dy;placeMap()};
  placeMap();
  let pointer=null;
  viewport.addEventListener('pointerdown',e=>{
   // Room clicks enter immediately; dragging starts only on empty terrain.
   if(e.button!==0||e.target.closest('button'))return;
   pointer={id:e.pointerId,x:e.clientX,y:e.clientY};
   viewport.setPointerCapture(e.pointerId);
  });
  viewport.addEventListener('pointermove',e=>{
   if(!pointer||e.pointerId!==pointer.id)return;
   const scale=viewport.getBoundingClientRect().width/viewport.clientWidth||1;
   pan((e.clientX-pointer.x)/scale,(e.clientY-pointer.y)/scale);
   pointer.x=e.clientX;pointer.y=e.clientY;
  });
  const release=e=>{if(pointer?.id===e.pointerId)pointer=null};
  viewport.addEventListener('pointerup',release);
  viewport.addEventListener('pointercancel',release);
  viewport.addEventListener('wheel',e=>{
   e.preventDefault();pan(-(e.deltaX||0),-(e.deltaY||0));
  },{passive:false});
  viewport.addEventListener('keydown',e=>{
   const steps={ArrowLeft:[95,0],ArrowRight:[-95,0],ArrowUp:[0,95],ArrowDown:[0,-95]};
   if(steps[e.key]){e.preventDefault();pan(...steps[e.key])}
  });
  for(const button of document.querySelectorAll('.social-map-directions button')){
   const steps={left:[150,0],right:[-150,0],up:[0,135],down:[0,-135]};
   button.onclick=()=>pan(...steps[button.dataset.pan]);
  }
 }
 function roomHasSpace(room){
  if(central.enabled)return central.joinedId===room.id||roomOccupancy(room.id)<allowedCapacity(room.capacity);
  return state.roomId===room.id&&state.view==='room'||onlinePeers('room:'+room.id).length<allowedCapacity(room.capacity);
 }
 function roomFullNotice(room){
  const body=document.createElement('div');body.className='social-modal-form';
  body.textContent='이 채팅방은 현재 '+allowedCapacity(room.capacity)+'명으로 가득 찼습니다. 다른 방을 선택해 주세요.';
  popup('채팅방 정원 초과',body);
 }
 function joinRoom(id){
  const room=roomById(id);if(!room)return;
  // A remotely cached count is advisory only; the central server must make
  // the final admission decision, including simultaneous joins and vacancies.
  if(!central.enabled&&!roomHasSpace(room)){roomFullNotice(room);return}
  if(central.enabled){
   const verifiedJoin=async password=>{
    try{
     if(!central.ready)throw Error('중앙 서버에 연결 중입니다.');
     await central.join(id,password);
     if(state.view!=='directory'){await central.leave();return}
     if(!enterRoom(room)){await central.leave();return}
     presence();
    }catch(e){
     if(/full|정원/i.test(e.message))roomFullNotice(room);
     else systemLine('채팅방 입장 실패: '+e.message);
    }
   };
   if(room.passwordProof)askText('비공개 채팅방','비밀번호',true,value=>{void verifiedJoin(value)});
   else void verifiedJoin('');
   return;
  }
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
  if(central.enabled&&central.joinedId)central.leave().catch(e=>systemLine('퇴장 처리 실패: '+e.message));
  state.view='directory';state.roomId=null;render();
  if(central.enabled&&central.ready)
   central.list(state.region,state.district).catch(e=>console.warn('ChatTown directory:',e.message));
 }
 function enterRoom(room){
  if(central.enabled&&central.joinedId!==room.id)return false;
  if(!roomHasSpace(room)){roomFullNotice(room);return false}
  if(room.region!==state.region){state.region=room.region}
  state.district=room.district;state.roomId=room.id;state.view='room';
  const seats=roomSeats(room.background);
  const hash=[...tabId].reduce((a,c)=>(a*31+c.charCodeAt(0))>>>0,0);
  state.position={...seats[hash%seats.length]};
  render();return true;
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
   if(user.id===tabId){state.facing*=-1;presence();renderOccupants();}
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
   const img=node.querySelector('img');
   const filename=avatars[user.avatar%avatars.length];
   if(!img.src.endsWith('/'+filename+'.png'))img.src='./original/Registry/'+filename+'.png';
   img.style.transform=(user.id===tabId?state.facing:user.facing)===-1?'scaleX(-1)':'';
  });
 }
 function showBubble(sender,text){
  if(state.view!=='room')return;
  const layer=$('social-avatar-layer');if(!layer)return;
  const node=[...layer.querySelectorAll('.social-avatar')].find(el=>el.dataset.peer===sender);
  if(!node)return;
  node.querySelector('.social-speech')?.remove();
  const bubble=document.createElement('div');bubble.className='social-speech';bubble.textContent=safe(text,55);bubble.setAttribute('role','status');node.append(bubble);
  // Actual archived 4LEAF talkbox pieces, assembled around real chat text.
  window.__LEAF_NATIVE_TALKBOX__?.apply(bubble);
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
  let retries=0;
  const path='./original/ChatRoom/'+art.file+'.png';
  const load=()=>{
   if(!canvas.isConnected)return;
   canvas.dataset.ready=retries?'retrying':'loading';
   // Pages/CDN can transiently return 503 during publication; cache-bust
   // retries rather than permanently losing authentic foreground furniture.
   img.src=path+(retries?'?retry='+retries+'&at='+Date.now():'');
  };
  img.onload=()=>{
   if(!canvas.isConnected)return;
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
  img.onerror=()=>{
   if(!canvas.isConnected)return;
   if(retries<5){
    retries++;
    setTimeout(load,Math.min(1800,250*2**retries));
   }else{
    canvas.dataset.ready='error';
    console.error('Original ChatRoom foreground unavailable after retries:',path);
   }
  };
  load();
 }
 function renderRoom(frame){
  frame.className='social-image-frame social-interior';
  const room=currentRoom();
  if(!room){openDirectory();return}
  frame.style.backgroundImage='url("'+roomTemplate(room.background)+'")';
  const avatarLayer=document.createElement('div');avatarLayer.className='social-avatar-layer';avatarLayer.id='social-avatar-layer';
  frame.append(avatarLayer);
  addRoomForeground(avatarLayer,room.background);
  // Original scene remains unobstructed; the avatar picker is in the recovered
  // top-toolbar icon row, while room owner actions stay in the window chrome.
  if(!room.preset&&room.ownerId===tabId||!room.preset&&!room.ownerId&&room.owner===nick()){
   const close=document.createElement('button');
   close.id='social-close-room';close.type='button';
   close.textContent='방 닫기';close.setAttribute('aria-label','현재 채팅방 닫기');
   close.onclick=()=>closeRoom(room.id);
   $root()?.querySelector('.social-header-tools')?.prepend(close);
  }
  frame.addEventListener('click',e=>{
   // Do not teleport from a click on a participant or UI overlay.
   if(e.target.closest('button, .social-room-title, .social-avatar'))return;
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
  body.innerHTML='<label>방 제목<input name="name" placeholder="방 이름" maxlength="26" required></label><label>배경<select name="background"><option value="2">서재</option><option value="3">클로버 응접실</option><option value="5">벽난로가 있는 방</option><option value="4">햇빛이 드는 방</option><option value="0">숲속 광장</option><option value="1">숲속 오솔길</option></select></label><label>정원<select name="capacity"><option value="12">12명</option><option value="8">8명</option><option value="4">4명</option><option value="2">2명 전용</option></select></label><label>비밀번호 (선택)<input name="password" type="password" maxlength="24" placeholder="비우면 공개방"></label><button type="submit">방 만들기</button>';
  body.onsubmit=async e=>{
   e.preventDefault();const form=new FormData(body);
   const name=safe(form.get('name'),26);
   if(!name)return;
   const password=safe(form.get('password'),24),salt=password?uuid():'';
   if(password&&password.length<6){const field=body.querySelector('[name="password"]');field.setCustomValidity('비밀번호는 6자 이상이어야 합니다.');field.reportValidity();return}
   const proof=password?await deriveRoomProof(password,salt):'';
   if(central.enabled){
    try{
     const created=await central.create({name,region:state.region,district:state.district,
      capacity:allowedCapacity(form.get('capacity')),background:allowedBackground(form.get('background')),password});
     const room={...centralRoom(created.room),ownerId:tabId,owner:nick()};
     centralRooms.set(room.id,room);centralCounts.set(room.id,0);
     await central.join(room.id,password);
     closePopup();enterRoom(room);presence();return;
    }catch(error){systemLine('채팅방 개설 실패: '+error.message);return}
   }
   const room={id:uuid(),name,region:state.region,district:state.district,owner:nick(),
    ownerId:tabId,passwordProof:proof,passwordSalt:salt,background:allowedBackground(form.get('background')),capacity:allowedCapacity(form.get('capacity')),created:now()};
   state.rooms.push(room);saveRooms();sendLocal({kind:'roomCreated',room});sendRTC({kind:'roomCreated',room});
   closePopup();enterRoom(room);
  };
  popup('새로운 4LEAF 채팅방 개설',body);
 }
 async function closeRoom(roomId){
  const room=roomById(roomId);
  if(!room||room.preset||(room.ownerId?room.ownerId!==tabId:room.owner!==nick()))return;
  if(central.enabled){
   try{
    await central.close(roomId);
    centralRooms.delete(roomId);centralCounts.delete(roomId);
    openDirectory();return;
   }catch(error){systemLine('방 닫기 실패: '+error.message);return}
  }
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

 function centralRoom(dto){
  return {id:dto.id,name:safe(dto.name,26),region:dto.region,
   district:sourceDistrict(dto.district),background:allowedBackground(dto.background),
   capacity:allowedCapacity(dto.capacity),preset:!!dto.preset,
   passwordProof:dto.locked?'server-locked':'',passwordSalt:'',
   ownerId:dto.isOwner?tabId:'',owner:dto.isOwner?nick():'',
   created:Number(dto.created)||0};
 }
 function initCentral(){
  if(!central.enabled)return;
  central.subscribe(event=>{
   if(event.type==='ready'){
    systemLine('중앙 채팅 서버 접속 완료 · 실제 다른 기기와 방 목록을 공유합니다.');
   }else if(event.type==='resumed'&&event.room){
    // Restore only a membership acknowledged by the authority, preserving
    // room capacity and owner privileges across browser reloads.
    const room=centralRoom(event.room);
    if(!room.preset)centralRooms.set(room.id,room);
    centralCounts.set(room.id,Number(event.room.occupants)||0);
    state.region=room.region;state.district=room.district;
    window.__ROG_TEST__?.go('rooms');
    enterRoom(room);
    presence();
   }else if(event.type==='rooms'){
    if(!event.rooms||!Array.isArray(event.rooms))return;
    for(const [id,r] of centralRooms)if(r.region===event.region&&r.district===event.district)centralRooms.delete(id);
    for(const r of event.rooms){
     centralCounts.set(r.id,Number(r.occupants)||0);
     if(!r.preset){
      // The server's isOwner flag is the ONLY source of room-management
      // privilege. A stale locally stored owner name cannot grant controls.
      centralRooms.set(r.id,centralRoom(r));
     }
    }
    if(state.view==='directory'&&event.region===state.region&&event.district===state.district)renderDirectory();
   }else if(event.type==='snapshot'){
    if(state.view==='room'&&central.joinedId===state.roomId&&!event.roomId){
     central.leave().catch(()=>{});
     state.view='directory';state.roomId=null;render();
     systemLine('접속해 있던 방이 닫히거나 서버에서 퇴장 처리되었습니다.');
     return;
    }
    for(const [id,p] of state.peers)if(p.source==='central')state.peers.delete(id);
    if(event.roomId===state.roomId&&state.view==='room'&&central.joinedId===state.roomId){
     for(const person of event.peers||[]){
      if(person.id===central.id)continue;
      state.peers.set(person.id,{id:person.id,nick:safe(person.nick,12),source:'central',
       scope:'room:'+state.roomId,roomId:state.roomId,avatar:Number(person.avatar)||0,
       facing:person.facing===-1?-1:1,position:person.position,last:now()});
     }
     for(const entry of event.entries||[]){
      if(entry.sender===central.id)continue;
      acceptPacket({v:1,kind:'chat',id:entry.id,scope:'room:'+event.roomId,
       sender:entry.sender,user:entry.user,text:entry.text,time:entry.time},'central');
     }
     renderOccupants();
    }
    updateCounts();
   }else if(event.type==='error'){
    console.warn('4LEAF central chat connection issue:',event.error?.message||event.error);
   }
  });
  central.connect(nick()).then(()=>{
   if(state.view==='directory')central.list(state.region,state.district).catch(e=>systemLine(e.message));
  }).catch(e=>systemLine('중앙 채팅 서버 접속 실패: '+e.message));
  setInterval(()=>{
   if(central.ready&&state.view==='directory')
    central.list(state.region,state.district).catch(e=>console.warn('ChatTown directory sync:',e.message));
  },3500);
 }
 function init(){
  migrateLegacyChatHistory();
  try{state.avatar=Math.max(0,Math.min(avatars.length-1,Number(localStorage.getItem('leaf_social_avatar'))||0))}catch{}
  build();installTransport();initCentral();
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
    if(central.enabled&&central.joinedId&&route!=='rooms'){
     central.leave().catch(e=>console.warn('Central ChatTown leave:',e.message));
     state.view='directory';state.roomId=null;
    }
    if(route==='sky')changeScope('world');
    else if(route==='city')changeScope('city');
    else if(route==='rooms')render();
    else changeScope('away:'+route); // leaving the scene vacates the chatroom; do not show ghost users in shop/game/help

  });
  const oldRename=$('rename')?.onclick;
  if($('rename'))$('rename').onclick=(...args)=>{
   if(oldRename)oldRename(...args);
   setTimeout(presence,700);
  };
  presence();render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 window.__LEAF_SOCIAL__={openRegion,openBoard,openDirectory,joinRoom,enterRoom,createRoom:(name,background=2,capacity=12)=>{
  const room={id:uuid(),name:safe(name,26),region:state.region,district:state.district,owner:nick(),ownerId:tabId,passwordProof:'',passwordSalt:'',background:allowedBackground(background),capacity:allowedCapacity(capacity),created:now()};
  state.rooms.push(room);saveRooms();sendLocal({kind:'roomCreated',room});enterRoom(room);return room.id;
 },send:publishText,getState:()=>({region:state.region,district:state.district,view:state.view,scope:state.scope,roomId:state.roomId,people:onlinePeers(),rooms:catalogue()}),
 sendRTC,now,render,transportMessage};
})();