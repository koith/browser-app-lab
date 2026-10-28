/* Owner media stays behind the authenticated gateway. No credentials in URLs. */
'use strict';
window.MimmiPrivate=(()=>{
 const cache=new Map(),inflight=new Map();let session=null;
 function readSession(){
  try{const s=JSON.parse(sessionStorage.getItem('mimmi-owner-session'));if(!s?.token)return null;const u=new URL(s.api);if(u.username||u.password||u.pathname!=='/'||u.search||u.hash)return null;if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))return null;return {api:u.origin,token:s.token}}catch{return null}
 }
 async function request(path){const r=await fetch(session.api+path,{headers:{Authorization:'Bearer '+session.token},cache:'no-store'});if(!r.ok)throw Error('보관소 HTTP '+r.status);return r}
 async function albums(){
  session=readSession();if(!session)return [];
  const d=await (await request('/api/catalog')).json();if(d.schema_version!==1||!Array.isArray(d.albums))throw Error('보관소 목록 형식 오류');
  return d.albums.map(a=>{
   if(!/^[a-z0-9][a-z0-9-]{1,100}$/.test(a.id)||!Array.isArray(a.images))throw Error('보관소 작품 형식 오류');
   return {...a,ownerHosted:true,images:a.images.map(p=>{
    if(!Number.isInteger(p.number)||p.number<1||!Number.isInteger(p.bytes)||p.bytes<1||!/^[a-f0-9]{64}$/.test(p.sha256))throw Error('보관소 사진 검증 정보 오류');
    return {...p,url:'owner:'+a.id+':'+p.number,ownerAlbum:a.id,extension:p.key?.split('.').pop()};
   })};
  });
 }
 async function asset(p){
  if(cache.has(p.url))return cache.get(p.url);
  if(inflight.has(p.url))return inflight.get(p.url);
  const job=(async()=>{
   const r=await request('/api/media/'+encodeURIComponent(p.ownerAlbum)+'/'+p.number+'/original');const b=await r.blob();
   if(b.size!==p.bytes)throw Error('보관본 크기 불일치');
   const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await b.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');
   if(sha!==p.sha256)throw Error('보관본 SHA-256 불일치');
   const url=URL.createObjectURL(b);cache.set(p.url,url);
   if(cache.size>64){const oldest=cache.keys().next().value;URL.revokeObjectURL(cache.get(oldest));cache.delete(oldest)}
   return url;
  })();inflight.set(p.url,job);try{return await job}finally{inflight.delete(p.url)}
 }
 return {albums,asset};
})();
