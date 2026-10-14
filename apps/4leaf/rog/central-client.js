'use strict';
// Optional HTTPS-only backend; no impact on the existing offline client.
(function(){
 const raw=String(window.LEAF_CENTRAL_API_URL||document.querySelector('meta[name="leaf-central-api"]')?.content||'').trim();
 let endpoint='';
 try{
  const url=new URL(raw);
  if(url.protocol==='https:'||(url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))
   endpoint=url.origin+url.pathname.replace(/\/$/,'');
 }catch{}
 if(!endpoint){window.__LEAF_CENTRAL_CHAT__={enabled:false};return}
 let token='',id='',joinedId=null,lastSequence=0,ready=null,active=false;
 const listeners=new Set();
 const notify=e=>{for(const fn of listeners)try{fn(e)}catch(err){console.error('4LEAF central listener',err)}};
 const request=async(method,route,data)=>{
  const resp=await fetch(endpoint+route,{method,headers:{accept:'application/json',
   ...(data?{'content-type':'application/json'}:{}),...(token?{authorization:'Bearer '+token}:{})},
   body:data?JSON.stringify(data):undefined,cache:'no-store'});
  const reply=await resp.json();
  if(!resp.ok)throw Error(reply.error||'Central chat HTTP '+resp.status);
  return reply;
 };
 let mutations=Promise.resolve();
 const serialize=fn=>{const out=mutations.then(fn,fn);mutations=out.catch(()=>{});return out};
 async function connect(nick){
  if(ready)return ready;
  ready=(async()=>{
   let resume='';
   try{resume=sessionStorage.getItem('leaf_central_session_v1')||''}catch{}
   const result=await request('POST','/api/session',{nick,resume});
   token=result.token;id=result.id;
   try{sessionStorage.setItem('leaf_central_session_v1',token)}catch{}
   active=true;notify({type:'ready',id});
   setInterval(async()=>{
    if(!active)return;
    try{
     const current=joinedId;
     const state=await request('GET','/api/snapshot?after='+lastSequence);
     lastSequence=state.nextSequence;
     if(current===joinedId)notify({type:'snapshot',...state});
    }catch(error){notify({type:'error',error})}
   },1600);
   return result;
  })().catch(e=>{ready=null;throw e});
  return ready;
 }
 const afterReady=async()=>{if(!ready)throw Error('중앙 채팅 서버가 연결되지 않았습니다.');await ready};
 const list=async(region,district)=>{
  await afterReady();
  const state=await request('GET','/api/rooms?region='+encodeURIComponent(region)+'&district='+encodeURIComponent(district));
  notify({type:'rooms',region,district,rooms:state.rooms});return state.rooms;
 };
 const join=(roomId,password='')=>serialize(async()=>{
  await afterReady();
  const result=await request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/join',{password});
  joinedId=roomId;return result;
 });
 const leave=()=>serialize(async()=>{
  if(!joinedId)return {left:true};
  await afterReady();const result=await request('POST','/api/leave',{});
  joinedId=null;return result;
 });
 const create=details=>serialize(async()=>{await afterReady();return request('POST','/api/rooms',details)});
 const close=roomId=>serialize(async()=>{await afterReady();return request('POST','/api/rooms/'+encodeURIComponent(roomId)+'/close',{})});
 const chat=async text=>{await afterReady();return request('POST','/api/chat',{text})};
 const presence=async details=>{await afterReady();return request('POST','/api/presence',details)};
 window.__LEAF_CENTRAL_CHAT__={enabled:true,connect,list,join,leave,create,close,chat,presence,
  get ready(){return Boolean(token)},get id(){return id},get joinedId(){return joinedId},
  subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn)},
  disconnect:()=>{active=false;joinedId=null;listeners.clear()}};
})();