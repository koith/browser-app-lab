'use strict';
// Optional HTTPS-only backend; no impact on the existing offline client.
(function(){
 // An explicit empty override is intentional: local/offline visual QA must
 // never accidentally depend on the unrelated public Render server.
 // Undefined means "use the production HTML meta endpoint".
 const configured=typeof window.LEAF_CENTRAL_API_URL==='string'
  ?window.LEAF_CENTRAL_API_URL
  :(location.protocol==='file:'?'':document.querySelector('meta[name="leaf-central-api"]')?.content);
 const raw=String(configured||'').trim();
 let endpoint='';
 try{
  const url=new URL(raw);
  if(url.protocol==='https:'||(url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))
   endpoint=url.origin+url.pathname.replace(/\/$/,'');
 }catch{}
 if(!endpoint){window.__LEAF_CENTRAL_CHAT__={enabled:false};return}
 let token='',id='',joinedId=null,lastSequence=0,ready=null,active=false;
 let lastNick='Guest',lastJoin=null,recovering=null,pollBusy=false,pollTimer=null;
 const listeners=new Set();
 const notify=e=>{for(const fn of listeners)try{fn(e)}catch(err){console.error('4LEAF central listener',err)}};
 const request=async(method,route,data)=>{
  const resp=await fetch(endpoint+route,{method,headers:{accept:'application/json',
   ...(data?{'content-type':'application/json'}:{}),...(token?{authorization:'Bearer '+token}:{})},
   body:data?JSON.stringify(data):undefined,cache:'no-store'});
  const reply=await resp.json();
  if(!resp.ok){const error=new Error(reply.error||'Central chat HTTP '+resp.status);
   error.status=resp.status;throw error;}
  return reply;
 };
 let mutations=Promise.resolve();
 const serialize=fn=>{const out=mutations.then(fn,fn);mutations=out.catch(()=>{});return out};
 async function connect(nick){
  if(ready)return ready;
  lastNick=String(nick||lastNick||'Guest');
  ready=(async()=>{
   let resume='';
   try{resume=sessionStorage.getItem('leaf_central_session_v1')||''}catch{}
   const result=await request('POST','/api/session',{nick:lastNick,resume});
   token=result.token;id=result.id;
   joinedId=result.room?.id||null;
   try{sessionStorage.setItem('leaf_central_session_v1',token)}catch{}
   active=true;notify({type:'ready',id});
   // The server alone decides whether a page reload still belongs to a room.
   if(result.room)notify({type:'resumed',room:result.room});
   // Reauth must not install a second poll timer on the same page.
   if(!pollTimer)pollTimer=setInterval(()=>{void poll()},1600);
   return result;
  })().catch(e=>{ready=null;throw e});
  return ready;
 }
 async function recoverSession(){
  // A single expired server session can cause simultaneous 401s from a
  // poll, a user message, and presence. Reauthenticate only once.
  if(recovering)return recovering;
  recovering=(async()=>{
   const wanted=joinedId;
   const membership=lastJoin?.id===wanted?lastJoin:null;
   ready=null;token='';id='';lastSequence=0;
   try{
    await connect(lastNick);
   }catch(error){
    // Keep the in-memory intended room for the next retry. Never claim that
    // the disconnected browser is currently an authenticated participant.
    joinedId=wanted;
    throw error;
   }
   if(!wanted)return;
   if(!membership){
    joinedId=null;notify({type:'membership-lost',roomId:wanted});
    return;
   }
   try{
    const joined=await request('POST','/api/rooms/'+encodeURIComponent(wanted)+'/join',
     {password:membership.password});
    joinedId=wanted;
    notify({type:'rejoined',room:joined.room,position:joined.position});
   }catch(error){
    joinedId=null;lastJoin=null;
    notify({type:'membership-lost',roomId:wanted,error});
   }
  })().finally(()=>{recovering=null});
  return recovering;
 }
 const withAuth=async fn=>{
  try{return await fn()}
  catch(error){
   if(error.status!==401)throw error;
   await recoverSession();
   return fn(); // retry only after a definitive 401 (not on an uncertain timeout)
  }
 };
 async function poll(){
  if(!active||pollBusy)return;
  if(!token){
   try{await recoverSession()}catch(error){notify({type:'error',error})}
   return;
  }
  pollBusy=true;
  try{
   const current=joinedId,seen=lastSequence,credential=token;
   const state=await request('GET','/api/snapshot?after='+seen);
   // An in-flight response from another room or previous session may not
   // advance the room's cursor or erase the newly joined membership.
   if(credential!==token||current!==joinedId)return;
   if(Number(state.nextSequence)<seen){
    // Server restarted or rolled back its volatile global sequence. Fetch
    // the current room's retained history again on the next poll.
    lastSequence=0;return;
   }
   lastSequence=Number(state.nextSequence)||0;
   notify({type:'snapshot',...state});
   if(current&&!state.roomId){
    joinedId=null;lastJoin=null;lastSequence=0;
    notify({type:'membership-lost',roomId:current});
   }
  }catch(error){
   if(error.status===401){
    try{await recoverSession()}catch(problem){notify({type:'error',error:problem})}
   }else notify({type:'error',error});
  }finally{pollBusy=false}
 }
 const afterReady=async()=>{if(!ready)throw Error('중앙 채팅 서버가 연결되지 않았습니다.');await ready};
 const list=async(region,district)=>{
  await afterReady();
  const state=await withAuth(()=>request('GET','/api/rooms?region='+encodeURIComponent(region)+'&district='+encodeURIComponent(district)));
  notify({type:'rooms',region,district,rooms:state.rooms});return state.rooms;
 };
 const join=(roomId,password='')=>serialize(async()=>{
  await afterReady();
  const result=await withAuth(()=>request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/join',{password}));
  joinedId=roomId;lastJoin={id:roomId,password};lastSequence=0;return result;
 });
 const leave=()=>serialize(async()=>{
  if(!joinedId)return {left:true};
  await afterReady();const result=await withAuth(()=>request('POST','/api/leave',{}));
  joinedId=null;lastJoin=null;lastSequence=0;return result;
 });
 const create=details=>serialize(async()=>{await afterReady();return withAuth(()=>request('POST','/api/rooms',details))});
 const close=roomId=>serialize(async()=>{await afterReady();return withAuth(()=>request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/close',{}))});
 const transfer=(roomId,targetId)=>serialize(async()=>{await afterReady();return withAuth(()=>request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/transfer',{targetId}))});
 const kick=(roomId,targetId)=>serialize(async()=>{await afterReady();return withAuth(()=>request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/kick',{targetId}))});
 const chat=async text=>{await afterReady();return withAuth(()=>request('POST','/api/chat',{text}))};
 const presence=async details=>{await afterReady();return withAuth(()=>request('POST','/api/presence',details))};
 window.__LEAF_CENTRAL_CHAT__={enabled:true,connect,list,join,leave,create,close,transfer,kick,chat,presence,
  get ready(){return Boolean(token)},get id(){return id},get joinedId(){return joinedId},
  subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn)},
  disconnect:()=>{active=false;joinedId=null;lastJoin=null;listeners.clear();
   if(pollTimer){clearInterval(pollTimer);pollTimer=null}}};
})();