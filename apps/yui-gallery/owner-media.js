/* Owner media stays behind the authenticated gateway. No credentials in URLs. */
'use strict';
window.YuiPrivate=(()=>{
 const cache=new Map(),inflight=new Map();let session=null;
 // Public gateway address contains no key. Worker returns only short-lived,
 // exact-SHA signed image URLs for already recorded gallery photo references.
 const CLOUDFLARE_GATEWAY='https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev/';
 let cloudApiPromise=null;
 async function cloudAsset(p,kind){
  if(!cloudApiPromise)cloudApiPromise=import('../gallery-archive/cloudflare-owner-gateway/pages-client.mjs')
   .then(m=>m.pagesGateway({endpoint:CLOUDFLARE_GATEWAY,model:'yui'}));
  const api=await cloudApiPromise;
  return api.asset(p,kind);
 }
 function readSession(){
  // Render's first-party owner gallery uses a Secure HttpOnly cookie instead
  // of a client-visible bearer token. GitHub Pages preserves old session flow.
  if(location.pathname.startsWith('/gallery/'))return {api:location.origin,token:null,cookie:true};
  // GitHub Pages opens immediately; asynchronously load SHA-verified archive media from the existing gateway.
  if(location.hostname==='koith.github.io')return {api:'https://mimmi-private-gallery-free.onrender.com',token:null,cookie:false};
  try{const s=JSON.parse(sessionStorage.getItem('yui-owner-session'));if(!s?.token)return null;const u=new URL(s.api);if(u.username||u.password||u.pathname!=='/'||u.search||u.hash)return null;if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))return null;return {api:u.origin,token:s.token}}catch{return null}
 }
 async function request(path){const r=await fetch(session.api+path,{headers:session.token?{Authorization:'Bearer '+session.token}:{},credentials:session.cookie?'same-origin':'omit',cache:'default'});if(!r.ok)throw Error('보관소 HTTP '+r.status);return r}
 function fromIndex(d){
  // The static SHA-verified catalog can render every album immediately,
  // before a sleeping API server starts. Only file metadata is public.
  if(d?.schema_version!==1||d.model!=='yui'||!Array.isArray(d.albums))throw Error('보관소 목록 형식 오류');
  return d.albums.map(a=>{
   if(!/^[a-z0-9][a-z0-9-]{1,100}$/.test(a.id)||!Array.isArray(a.images))throw Error('보관소 작품 형식 오류');
   return {...a,ownerHosted:true,images:a.images.map(p=>{
    if(!Number.isInteger(p.number)||p.number<1||!Number.isInteger(p.bytes)||p.bytes<1||!/^[a-f0-9]{64}$/.test(p.sha256))throw Error('보관소 사진 검증 정보 오류');
    return {...p,url:'owner:'+a.id+':'+p.number,ownerAlbum:a.id,extension:p.key?.split('.').pop()};
   })};
  });
 }
 function reconcile(current,incoming){
  const merged=new Map(current.map(a=>[a.id,{...a,images:a.images.slice()}]));
  for(const album of incoming){
   const prior=merged.get(album.id);if(!prior){merged.set(album.id,album);continue;}
   const photos=new Map(prior.images.map(p=>[p.number,p]));
   for(const p of album.images){const old=photos.get(p.number);
    if(!old||globalThis.GalleryPhotoQuality?.preferred(old,p)===p)photos.set(p.number,p);
   }
   merged.set(album.id,{...album,...prior,images:[...photos.values()].sort((a,b)=>a.number-b.number)});
  }
  return [...merged.values()];
 }
 async function albums(){
  session=readSession();if(!session)return [];
  return fromIndex(await (await request('/api/yui/catalog')).json());
 }
 async function asset(p,kind='original'){
  if(!session)session=readSession();
  if(!session)throw Error('보관소 연결 없음');
  if(location.hostname==='koith.github.io'){
   try{return await cloudAsset(p,kind)}
   catch(error){
    // Keep legacy owner access only for photos not yet present in the replica.
    // Do not convert 403, 5xx, or SHA/auth failures into a false success.
    if(error?.message!=='GALLERY_GATEWAY_HTTP_404')throw error;
   }
  }
  if(kind==='cover'){
   const version=(p.preview_sha256||p.sha256||'').slice(0,24);
   return session.api+'/api/cover/yui/'+encodeURIComponent(p.ownerAlbum)+'/'+(p.storageNumber??p.number)+'?v='+version;
  }
  const selected=kind==='preview'&&p.preview?'preview':'original';
  // The server verifies SHA-256 before returning the image. Returning the
  // same-origin URL lets Safari decode and cache it natively without loading
  // thousands of image blobs into JavaScript memory or hashing on the phone.
  return session.api+'/api/yui/media/'+encodeURIComponent(p.ownerAlbum)+'/'+(p.storageNumber??p.number)+'/'+selected+'?v='+(selected==='preview'?p.preview_sha256:p.sha256);
 }

 return {albums,asset,fromIndex,reconcile};
})();
