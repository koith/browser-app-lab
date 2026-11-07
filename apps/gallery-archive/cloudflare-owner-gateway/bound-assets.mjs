// Files are internal Worker bindings. run_worker_first MUST be true on deploy.
// Catalogs are private Text modules, retrievable only by the owner's control API.
const parsedCatalogs=new WeakMap();
export function boundAssetBucket(env) {
  if(!env.ARCHIVE_ASSETS?.fetch||!env.ARCHIVE_CATALOGS)return null;
  return {cacheIdentity:env.ARCHIVE_CATALOGS,partitionedCatalogs:true,async get(key){
    if(typeof key!=='string'||!key||/[%\\\x00-\x1f]/.test(key)||
       key.split('/').some(s=>!s||s==='.'||s==='..'))throw Error('INVALID_BOUND_ASSET_KEY');
    const match=/^(mimmi|yui)\/metadata\/albums\/([a-z0-9-]+)\.json$/.exec(key);
    if(match){
      let models=parsedCatalogs.get(env.ARCHIVE_CATALOGS);
      if(!models){models=new Map();parsedCatalogs.set(env.ARCHIVE_CATALOGS,models)}
      if(!models.has(match[1])){
        const raw=env.ARCHIVE_CATALOGS[match[1]];
        if(typeof raw!=='string'||new TextEncoder().encode(raw).length>6_000_000)return null;
        const catalog=JSON.parse(raw);
        if(catalog?.schema_version!==1||catalog.model!==match[1]||!Array.isArray(catalog.albums))throw Error('BOUND_CATALOG_INVALID');
        const albums=new Map();
        for(const a of catalog.albums){if(albums.has(a.id))throw Error('BOUND_CATALOG_DUPLICATE_ALBUM');albums.set(a.id,a)}
        models.set(match[1],albums);
      }
      const album=models.get(match[1]).get(match[2]);if(!album)return null;
      const text=JSON.stringify({schema_version:1,model:match[1],albums:[album]});
      const bytes=new TextEncoder().encode(text);
      if(bytes.length>6_000_000)throw Error('BOUND_CATALOG_TOO_LARGE');
      return {size:bytes.length,text:async()=>text,arrayBuffer:async()=>bytes.buffer};
    }
    if(!/^(mimmi|yui)\/(originals|previews)\/[a-z0-9-]+\/[a-zA-Z0-9._ -]+$/.test(key))
      throw Error('INVALID_BOUND_ASSET_NAMESPACE');
    const path='/'+key.split('/').map(encodeURIComponent).join('/');
    const r=await env.ARCHIVE_ASSETS.fetch(new Request('https://assets.internal'+path,{redirect:'manual'}));
    if(r.status===404)return null;
    if(r.status!==200||r.redirected)throw Error('BOUND_ASSET_READ_FAILED');
    const declared=r.headers.get('content-length');
    if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>8_000_000)){
      await r.body?.cancel();throw Error('BOUND_ASSET_SIZE');
    }
    if(!r.body)throw Error('BOUND_ASSET_EMPTY');
    let size=0;const chunks=[],reader=r.body.getReader();
    try{while(true){const {value,done}=await reader.read();if(done)break;
      size+=value.length;if(size>8_000_000){await reader.cancel();throw Error('BOUND_ASSET_SIZE')}
      chunks.push(value);
    }}finally{reader.releaseLock()}
    if(declared!==null&&size!==Number(declared))throw Error('BOUND_ASSET_TRUNCATED');
    const bytes=new Uint8Array(size);let offset=0;
    for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length}
    return {size,arrayBuffer:async()=>bytes.buffer};
  }};
}
