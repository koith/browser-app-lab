// Passwordless Pages transport for an explicitly configured, private-store
// Worker using the existing SHA-pinned gallery read policy. No storage tokens.
const SHA=/^[a-f0-9]{64}$/;
const ID=/^[a-z0-9][a-z0-9-]{1,99}$/;
export function pagesGateway({endpoint,model,fetcher=fetch,now=()=>Date.now()}) {
  const api=new URL(endpoint);
  if(api.protocol!=='https:'||api.username||api.password||api.port||api.pathname!=='/'||
     api.search||api.hash||!['mimmi','yui'].includes(model))throw Error('INVALID_GALLERY_GATEWAY');
  const cache=new Map(),inflight=new Map();
  // Browser networking may briefly reject a valid CORS request as a
  // TypeError while the free Worker route is propagating. Reissue ONLY this
  // idempotent signing request with bounded delay (0ms / 180ms / 650ms).
  // Never retry HTTP 401/403, non-network exceptions, invalid signatures,
  // or fall back to another host, model, photo, or SHA.
  async function fetchSignOnceMoreOnNetworkFailure(init) {
    const target=new URL('/api/v1/sign',api);
    for(let attempt=0;attempt<3;attempt++){
      try{return await fetcher(target,init)}
      catch(error){
        if(!(error instanceof TypeError)||attempt===2)throw error;
        await new Promise(resolve=>setTimeout(resolve,attempt===0?180:650));
      }
    }
  }
  async function sign(photo,variant) {
    const album=photo.ownerAlbum,number=photo.storageNumber??photo.number;
    const digest=variant==='original'?photo.sha256:photo.preview_sha256;
    const size=variant==='original'?photo.bytes:photo.preview_bytes;
    if(!ID.test(album)||!Number.isSafeInteger(number)||number<1||number>=10000||
       !SHA.test(digest)||!Number.isSafeInteger(size)||size<1||size>8_000_000)
      throw Error('INVALID_STORED_PHOTO');
    const key=[album,number,variant,digest,size].join('|');
    const previous=cache.get(key);
    if(previous&&previous.expires>now()+30_000)return previous.url;
    if(inflight.has(key))return inflight.get(key);
    const pending=(async()=>{
      const response=await fetchSignOnceMoreOnNetworkFailure({
        method:'POST',credentials:'omit',cache:'no-store',redirect:'error',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model,album,number,variant,sha256:digest})
      });
      if(response.status===404&&variant==='preview'){
        const url=await sign(photo,'original');
        const original=cache.get([album,number,'original',photo.sha256,photo.bytes].join('|'));
        if(original)cache.set(key,original);
        return url;
      }
      if(response.status!==200||response.redirected)throw Error('GALLERY_GATEWAY_HTTP_'+response.status);
      const data=await response.json();
      let url;try{url=new URL(data.url)}catch{throw Error('INVALID_SIGNED_PHOTO')}
      const expires=Number(data.expires_at),expectedPath='/api/v1/media/'+[model,album,number,variant].join('/');
      if(url.origin!==api.origin||url.username||url.password||url.hash||url.pathname!==expectedPath||
         data.sha256!==digest||data.bytes!==size||!Number.isSafeInteger(expires)||
         expires*1000<=now()+30_000||expires*1000>now()+305_000||
         url.searchParams.get('h')!==digest||url.searchParams.get('b')!==String(size)||
         url.searchParams.get('e')!==String(expires)||!SHA.test(url.searchParams.get('s')||'')||
         [...url.searchParams.keys()].length!==4)
        throw Error('INVALID_SIGNED_PHOTO');
      cache.set(key,{url:url.href,expires:expires*1000});return url.href;
    })();
    inflight.set(key,pending);
    try{return await pending}finally{inflight.delete(key)}
  }
  const asset=(photo,kind='original')=>{

    if(!['cover','preview','original'].includes(kind))return Promise.reject(Error('INVALID_PHOTO_VARIANT'));
    const preview=kind!=='original'&&photo.preview&&SHA.test(photo.preview_sha256||'')&&
      Number.isSafeInteger(photo.preview_bytes)&&photo.preview_bytes>0;
    return sign(photo,preview?'preview':'original');
  };
  // A fetched <img> can fail with a transient upstream 503 even after its
  // sign request succeeded. Never reuse that possibly cached signed response
  // on retry. Re-sign the SAME immutable SHA/album/number and keep h/b/e/s
  // as the only media URL query fields. No cache-busting query injection.
  const renew=(photo,kind='original')=>{
    if(!['cover','preview','original'].includes(kind))
      return Promise.reject(Error('INVALID_PHOTO_VARIANT'));
    const number=photo?.storageNumber??photo?.number;
    const album=photo?.ownerAlbum;
    const key=(variant,digest,size)=>[album,number,variant,digest,size].join('|');
    cache.delete(key('original',photo?.sha256,photo?.bytes));
    cache.delete(key('preview',photo?.preview_sha256,photo?.preview_bytes));
    return asset(photo,kind);
  };
  return {asset,renew};
}
