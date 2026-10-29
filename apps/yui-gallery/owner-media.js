/* Owner media stays behind the authenticated gateway. No credentials in URLs. */
'use strict';
window.YuiPrivate=(()=>{
 const cache=new Map(),inflight=new Map();let session=null;
 function readSession(){
  // Render's first-party owner gallery uses a Secure HttpOnly cookie instead
  // of a client-visible bearer token. GitHub Pages preserves old session flow.
  if(location.pathname.startsWith('/gallery/'))return {api:location.origin,token:null,cookie:true};
  try{const s=JSON.parse(sessionStorage.getItem('yui-owner-session'));if(!s?.token)return null;const u=new URL(s.api);if(u.username||u.password||u.pathname!=='/'||u.search||u.hash)return null;if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))return null;return {api:u.origin,token:s.token}}catch{return null}
 }
 async function request(path){const r=await fetch(session.api+path,{headers:session.token?{Authorization:'Bearer '+session.token}:{},credentials:session.cookie?'same-origin':'omit',cache:'no-store'});if(!r.ok)throw Error('보관소 HTTP '+r.status);return r}
 async function albums(){
  session=readSession();if(!session)return [];
  const d=await (await request('/api/yui/catalog')).json();if(d.schema_version!==1||!Array.isArray(d.albums))throw Error('보관소 목록 형식 오류');
  return d.albums.map(a=>{
   if(!/^[a-z0-9][a-z0-9-]{1,100}$/.test(a.id)||!Array.isArray(a.images))throw Error('보관소 작품 형식 오류');
   return {...a,ownerHosted:true,images:a.images.map(p=>{
    if(!Number.isInteger(p.number)||p.number<1||!Number.isInteger(p.bytes)||p.bytes<1||!/^[a-f0-9]{64}$/.test(p.sha256))throw Error('보관소 사진 검증 정보 오류');
    return {...p,url:'owner:'+a.id+':'+p.number,ownerAlbum:a.id,extension:p.key?.split('.').pop()};
   })};
  });
 }
 async function asset(p,kind='original'){
  if(!session)session=readSession();
  if(!session)throw Error('보관소 연결 없음');
  if(kind==='cover'){
   const version=(p.preview_sha256||p.sha256||'').slice(0,24);
   return session.api+'/api/cover/yui/'+encodeURIComponent(p.ownerAlbum)+'/'+p.number+'?v='+version;
  }
  const selected=kind==='preview'&&p.preview?'preview':'original';
  // The server verifies SHA-256 before returning the image. Returning the
  // same-origin URL lets Safari decode and cache it natively without loading
  // thousands of image blobs into JavaScript memory or hashing on the phone.
  return session.api+'/api/yui/media/'+encodeURIComponent(p.ownerAlbum)+'/'+p.number+'/'+selected;
 }

 return {albums,asset};
})();
