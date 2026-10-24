'use strict';
// Standalone, authoritative 4LEAF ChatTown backend. Node 22+, no packages.
// Run behind HTTPS, with LEAF_CENTRAL_ORIGINS set to the trusted front-end origin.
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {randomUUID,randomBytes,scryptSync,timingSafeEqual,createHash}=require('node:crypto');
const REGIONS={
 north:['실버 호라이즌','화이트 크리스탈','퓨어 시티','샤이닝 브리즈','윈트리 아이스','스노우 폴','스위트 자스민','그린 에메랄드'],
 south:['블루 사파이어','헤이즐리 웨이브','미쉘 에메랄드','엘핀 포레스트','아루아 코랄','블랙씨 아린','브라브 지피트','미스틱 머메이드']
};
const safe=(s,n)=>String(s??'').replace(/[\x00-\x1f\x7f]/g,' ').trim().slice(0,n);
const valid=(r,d)=>Object.hasOwn(REGIONS,r)&&REGIONS[r].includes(d);
const secretFingerprint=token=>createHash('sha256').update(token).digest('hex');
function makeServer(options={}){
 const clock=options.now||Date.now;
 const store=options.storageFile||process.env.LEAF_CENTRAL_STORAGE||'';
 const origins=(options.origins??process.env.LEAF_CENTRAL_ORIGINS??'').split(',').map(x=>x.trim()).filter(Boolean);
 const sessions=new Map(),rooms=new Map(),history=new Map(),kicked=new Map();let sequence=0;
 if(store&&fs.existsSync(store)){
  const archive=JSON.parse(fs.readFileSync(store,'utf8'));
  for(const r of archive.rooms||[])if(r?.id&&valid(r.region,r.district))rooms.set(r.id,r);
  for(const [id,lines] of archive.history||[])if(Array.isArray(lines))history.set(id,lines.slice(-200));
  sequence=Number(archive.sequence)||0;
 }
 const save=()=>{
  if(!store)return;
  fs.mkdirSync(path.dirname(store),{recursive:true});
  const temp=store+'.'+process.pid+'.tmp';
  fs.writeFileSync(temp,JSON.stringify({rooms:[...rooms.values()],history:[...history.entries()],sequence}),{mode:0o600});
  fs.renameSync(temp,store);
 };
 const count=id=>[...sessions.values()].filter(s=>s.roomId===id).length;
 // Source ChatRoom 794x528 seat locations are currently picture-measured WEB
 // coordinates, NOT recovered 2002 room SEAT table. Keep the identical table
 // in the browser until EXE seat data is recovered, but ONLY this authority
 // allocates seats when two actual browsers click/join in the same instant.
 const SEATS=Object.freeze([
  [[21,66],[38,66],[55,66],[73,66],[20,80],[38,80],[55,80],[74,80],[22,92],[39,92],[57,92],[74,92]],
  [[24,64],[42,64],[60,64],[76,64],[22,78],[40,78],[59,78],[76,78],[22,91],[40,91],[59,91],[76,91]],
  [[20,63],[37,63],[55,63],[73,63],[21,78],[38,78],[56,78],[73,78],[22,92],[39,92],[57,92],[74,92]],
  [[19,83],[38,72],[59,72],[81,83],[24,94],[39,94],[56,94],[72,94],[22,69],[77,69],[39,83],[61,83]],
  [[17,65],[32,61],[45,70],[61,72],[73,64],[91,65],[8,97],[29,97],[48,97],[73,97],[91,97],[52,62]],
  [[20,66],[38,66],[56,66],[74,66],[20,81],[39,81],[57,81],[75,81],[22,93],[39,93],[57,93],[74,93]]
 ]);
 const nativeSeats=r=>SEATS[Number(r?.background)]||SEATS[2];
 const closestSeat=(list,target,occupied=new Set())=>{
  const x=Number(target?.x)||52,y=Number(target?.y)||76;
  const ranked=list.map(([sx,sy],i)=>({i,score:(sx-x)**2*2.26+(sy-y)**2}))
   .sort((a,b)=>a.score-b.score||a.i-b.i);
  return (ranked.find(item=>!occupied.has(item.i))||ranked[0]).i;
 };
 const reserveSeat=(session,target)=>{
  if(!session.roomId)return null;
  const r=room(session.roomId);
  if(!r)return null;
  const seats=nativeSeats(r),occupied=new Set();
  for(const peer of sessions.values()){
   if(peer===session||peer.roomId!==session.roomId)continue;
   occupied.add(closestSeat(seats,peer.position));
  }
  const i=closestSeat(seats,target,occupied);
  session.position={x:seats[i][0],y:seats[i][1]};
  return i;
 };
 const sourceRoom=id=>{
  const m=/^leaf-public-(north|south)-([0-7])-([0-7])$/.exec(id||'');
  if(!m)return null;
  const region=m[1],district=REGIONS[region][+m[2]],slot=+m[3];
  return {id,name:'채팅방 '+String(+m[2]*8+slot+1).padStart(2,'0'),region,district,
   preset:true,background:[2,3,5,4,0,1][slot%6],capacity:12,created:0};
 };
 const room=id=>rooms.get(id)||sourceRoom(id);
 const dto=(r,user)=>({id:r.id,name:r.name,region:r.region,district:r.district,
  background:r.background,capacity:r.capacity,preset:!!r.preset,
  created:r.created,locked:!!r.passwordHash,occupants:count(r.id),
  // Never trust client-supplied room owners; expose ownership only to its
  // authenticated server-side session. This survives page reloads.
  isOwner:!!user&&!r.preset&&r.ownerId===user.id});
 const clean=()=>{for(const [token,s] of sessions)if(clock()-s.lastSeen>45000)sessions.delete(token);
  for(const [key,until] of kicked)if(clock()>=until)kicked.delete(key)};
 const ticker=setInterval(clean,10000);ticker.unref?.();
 const send=(res,code,data,origin)=>{
  res.writeHead(code,{'content-type':'application/json; charset=utf-8','cache-control':'no-store',
   'x-content-type-options':'nosniff',...(origin&&origins.includes(origin)?{
    'access-control-allow-origin':origin,'vary':'Origin'}:{})});
  res.end(JSON.stringify(data));
 };
 const fail=(status,msg)=>{const e=new Error(msg);e.status=status;throw e};
 const parse=async req=>{
  let size=0,buffers=[];
  for await(const chunk of req){size+=chunk.length;if(size>8192)fail(413,'Body too large');buffers.push(chunk)}
  try{const b=JSON.parse(Buffer.concat(buffers).toString('utf8')||'{}');
   if(b&&typeof b==='object'&&!Array.isArray(b))return b}catch{}
  fail(400,'Expected JSON object');
 };
 const handler=async(req,res)=>{
  const origin=String(req.headers.origin||'');
  if(origin&&!origins.includes(origin)){send(res,403,{error:'Origin forbidden'},'');return}
  if(req.method==='OPTIONS'){
   res.writeHead(204,{'access-control-allow-origin':origin,'access-control-allow-methods':'GET,POST,OPTIONS',
    'access-control-allow-headers':'authorization,content-type','access-control-max-age':'600'});
   res.end();return;
  }
  try{
   clean();const u=new URL(req.url,'http://localhost'),route=u.pathname;
   if(req.method==='GET'&&route==='/api/health')return send(res,200,{ok:true,version:1},origin);
   if(req.method==='POST'&&route==='/api/session'){
    const b=await parse(req);
    let token=/^[a-f0-9]{64}$/.test(b.resume||'')?b.resume:'';
    let existing=token&&sessions.get(token);
    if(!existing&&token){
     const owner=[...rooms.values()].find(r=>r.ownerTokenHash===secretFingerprint(token));
     if(owner)existing={id:owner.ownerId,nick:safe(b.nick,12)||'Guest'};
    }
    if(!existing){token=randomBytes(32).toString('hex');existing={id:randomUUID()}}
    const id=existing.id;
    if(!sessions.has(token))sessions.set(token,{id,roomId:null,nick:safe(b.nick,12)||'Guest',
     avatar:0,facing:1,position:{x:52,y:76},lastSeen:clock(),recent:[]});
    else{const prior=sessions.get(token);prior.lastSeen=clock();prior.nick=safe(b.nick,12)||prior.nick}
    const session=sessions.get(token);
    const restored=session.roomId&&room(session.roomId);
    return send(res,201,{token,id,ttlMs:45000,
     room:restored?dto(restored,session):null},origin);
   }
   const token=/^Bearer ([a-f0-9]{64})$/.exec(req.headers.authorization||'')?.[1];
   const s=sessions.get(token);
   if(!s)fail(401,'Session required');
   s.lastSeen=clock();
   if(req.method==='GET'&&route==='/api/rooms'){
    const region=u.searchParams.get('region'),district=u.searchParams.get('district');
    if(!valid(region,district))fail(400,'Unknown ChatTown area');
    const i=REGIONS[region].indexOf(district);
    const permanent=Array.from({length:8},(_,slot)=>sourceRoom('leaf-public-'+region+'-'+i+'-'+slot));
    const extra=[...rooms.values()].filter(r=>r.region===region&&r.district===district);
    return send(res,200,{rooms:[...permanent,...extra].map(r=>dto(r,s))},origin);
   }
   if(req.method==='POST'&&route==='/api/rooms'){
    const b=await parse(req),district=safe(b.district,40);
    if(!valid(b.region,district))fail(400,'Unknown ChatTown area');
    const name=safe(b.name,26);
    if(!name)fail(400,'A room name is required');
    if([...rooms.values()].filter(r=>r.region===b.region&&r.district===district).length>=192)fail(409,'No free room slots');
    const capacity=+b.capacity,background=+b.background;
    if(![2,4,8,12].includes(capacity)||!Number.isInteger(background)||background<0||background>5)fail(400,'Invalid room type');
    const password=String(b.password||'');
    if(password&&(password.length<6||password.length>24))fail(400,'Password length 6–24');
    const salt=password?randomBytes(16).toString('hex'):'';
    const r={id:randomUUID(),region:b.region,district,name,capacity,background,preset:false,
     ownerId:s.id,ownerTokenHash:secretFingerprint(token),created:clock(),passwordSalt:salt,
     passwordHash:password?scryptSync(password,salt,32).toString('hex'):''};
    rooms.set(r.id,r);save();return send(res,201,{room:dto(r,s)},origin);
   }
   const action=/^\/api\/rooms\/([^/]+)\/(join|close|transfer|kick)$/.exec(route);
   if(req.method==='POST'&&action){
    const r=room(action[1]);if(!r)fail(404,'No such room');
    if(action[2]==='close'){
     if(r.preset||r.ownerId!==s.id)fail(403,'Only the owner can close a private room');
     rooms.delete(r.id);history.delete(r.id);
     for(const peer of sessions.values())if(peer.roomId===r.id)peer.roomId=null;
     save();return send(res,200,{closed:true},origin);
    }
    const b=await parse(req);
    if(action[2]==='transfer'||action[2]==='kick'){
     if(r.preset||r.ownerId!==s.id||s.roomId!==r.id)fail(403,'Only the current room owner can moderate joined peers');
     const targetId=safe(b.targetId,80);
     if(!targetId||targetId===s.id)fail(400,'Another joined participant is required');
     const peerEntry=[...sessions.entries()].find(([,peer])=>peer.roomId===r.id&&peer.id===targetId);
     if(!peerEntry)fail(404,'Target participant is not in this room');
     const [targetToken,target]=peerEntry;
     if(action[2]==='transfer'){
      // Only the authority decides ownership; change both the persistent
      // person id and the recoverable owner-secret fingerprint atomically.
      r.ownerId=target.id;r.ownerTokenHash=secretFingerprint(targetToken);
      save();return send(res,200,{transferred:true,room:dto(r,s),targetId},origin);
     }
     target.roomId=null;
     kicked.set(r.id+':'+target.id,clock()+120000);
     return send(res,200,{kicked:true,targetId,roomId:r.id},origin);
    }
    if(kicked.get(r.id+':'+s.id)>clock())fail(403,'Temporarily removed by the room owner');
    if(r.passwordHash){
     const guess=scryptSync(String(b.password||''),r.passwordSalt,32);
     if(!timingSafeEqual(guess,Buffer.from(r.passwordHash,'hex')))fail(403,'Incorrect password');
    }
    // Check and reserve in the same synchronous event-loop turn.
    if(s.roomId!==r.id&&count(r.id)>=r.capacity)fail(409,'Room is full');
    const rejoining=s.roomId===r.id;
    const wanted=rejoining?s.position:{x:52,y:76};
    s.roomId=r.id;
    const seat=reserveSeat(s,wanted);
    return send(res,200,{joined:true,room:dto(r,s),position:s.position,seat},origin);
   }
   if(req.method==='POST'&&route==='/api/leave'){
    s.roomId=null;return send(res,200,{left:true},origin);
   }
   if(req.method==='POST'&&route==='/api/presence'){
    const b=await parse(req);
    s.nick=safe(b.nick,12)||s.nick;
    if(Number.isInteger(b.avatar)&&b.avatar>=0&&b.avatar<12)s.avatar=b.avatar;
    if(b.facing===1||b.facing===-1)s.facing=b.facing;
    let seat=null;
    if(b.position&&Number.isFinite(b.position.x)&&Number.isFinite(b.position.y)){
     const target={x:Math.max(0,Math.min(100,b.position.x)),
      y:Math.max(0,Math.min(100,b.position.y))};
     if(s.roomId)seat=reserveSeat(s,target);
     else s.position=target;
    }
    return send(res,200,{ok:true,roomId:s.roomId,position:s.position,seat},origin);
   }
   if(req.method==='POST'&&route==='/api/chat'){
    if(!s.roomId||!room(s.roomId))fail(403,'Join a room first');
    const b=await parse(req),message=safe(b.text,250);
    if(!message)fail(400,'Empty message');
    s.recent=s.recent.filter(t=>clock()-t<5000);
    if(s.recent.length>=12)fail(429,'Rate limit');
    s.recent.push(clock());
    const item={id:randomUUID(),seq:++sequence,roomId:s.roomId,sender:s.id,
     user:s.nick,text:message,time:clock()};
    const lines=history.get(s.roomId)||[];
    lines.push(item);history.set(s.roomId,lines.slice(-200));save();
    return send(res,201,{entry:item},origin);
   }
   if(req.method==='GET'&&route==='/api/snapshot'){
    const roomId=s.roomId&&room(s.roomId)?s.roomId:null;
    const peers=roomId?[...sessions.values()].filter(x=>x.roomId===roomId).map(x=>({
     id:x.id,nick:x.nick,avatar:x.avatar,facing:x.facing,position:x.position,roomId:x.roomId
    })):[];
    const after=Math.max(0,Number(u.searchParams.get('after')||0)||0);
    return send(res,200,{roomId,peers,entries:(history.get(roomId)||[]).filter(x=>x.seq>after),
     room:roomId?dto(room(roomId),s):null,
     nextSequence:sequence,serverTime:clock()},origin);
   }
   fail(404,'Unknown endpoint');
  }catch(e){send(res,e.status||500,{error:e.status?e.message:'Internal error'},origin)}
 };
 const server=http.createServer((req,res)=>{void handler(req,res)});
 return {server,close:()=>{clearInterval(ticker);return new Promise(done=>server.close(done))},
  inspect:()=>({rooms:rooms.size,sessions:sessions.size})};
}
if(require.main===module){
 const port=Number(process.env.PORT||8787);
 makeServer().server.listen(port,process.env.HOST||'0.0.0.0',
  ()=>console.log('4LEAF central chat authority listening on '+port));
}
module.exports={makeServer,REGIONS};
