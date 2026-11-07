// Private, read-only B2/R2 S3 transport. No bucket creation or anonymous URLs.
const encoder = new TextEncoder();
const EMPTY_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
const hex = b => [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
const sha = async s => hex(await crypto.subtle.digest('SHA-256',encoder.encode(s)));
const hmac = async (key,text) => {
  const k=await crypto.subtle.importKey('raw',typeof key==='string'?encoder.encode(key):key,
    {name:'HMAC',hash:'SHA-256'},false,['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC',k,encoder.encode(text)));
};
const encode = text => encodeURIComponent(text).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());

export function privateS3Config(env) {
  const {OWNER_S3_ENDPOINT:endpoint,OWNER_S3_BUCKET:bucket,OWNER_S3_REGION:region,
    OWNER_S3_ACCESS_KEY_ID:key,OWNER_S3_SECRET_ACCESS_KEY:secret}=env;
  if (![endpoint,bucket,region,key,secret].every(x=>typeof x==='string'&&x.length))return null;
  let u;try{u=new URL(endpoint)}catch{return null}
  if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||u.port||u.pathname!=='/'||
     !/^[a-z0-9][a-z0-9-]{2,62}$/.test(bucket)||key.length<12||secret.length<12)return null;
  const b2=/^s3\.([a-z0-9-]+)\.backblazeb2\.com$/.exec(u.hostname);
  const r2=/^[a-f0-9]{32}\.r2\.cloudflarestorage\.com$/.test(u.hostname);
  if(!((b2&&region===b2[1])||(r2&&region==='auto')))return null;
  return {endpoint:u.origin,bucket,region,key,secret};
}

export async function signedS3Get(config,key,now=new Date()) {
  if(typeof key!=='string'||key.length>1100||!key||/[%\\\x00-\x1f]/.test(key)||
     key.split('/').some(x=>!x||x==='.'||x==='..'))throw Error('INVALID_PRIVATE_OBJECT_KEY');
  const url=new URL('/'+[config.bucket,...key.split('/')].map(encode).join('/'),config.endpoint);
  const date=now.toISOString().replace(/[-:]|\.\d{3}/g,''),day=date.slice(0,8);
  const scope=day+'/'+config.region+'/s3/aws4_request';
  const names='host;x-amz-content-sha256;x-amz-date';
  const headers='host:'+url.host+'\nx-amz-content-sha256:'+EMPTY_SHA+'\nx-amz-date:'+date+'\n';
  const canonical=['GET',url.pathname,'',headers,names,EMPTY_SHA].join('\n');
  let signing=await hmac('AWS4'+config.secret,day);
  for(const part of [config.region,'s3','aws4_request'])signing=await hmac(signing,part);
  const signature=hex(await hmac(signing,['AWS4-HMAC-SHA256',date,scope,await sha(canonical)].join('\n')));
  return new Request(url,{redirect:'error',headers:{
    'x-amz-content-sha256':EMPTY_SHA,'x-amz-date':date,
    Authorization:'AWS4-HMAC-SHA256 Credential='+config.key+'/'+scope+', SignedHeaders='+names+', Signature='+signature
  }});
}

export function privateS3Bucket(env,fetcher=fetch) {
  const config=privateS3Config(env);
  if(!config)return null;
  return {
    // Stable catalog cache identity without persisting secret values in keys.
    cacheIdentity:[config.endpoint,config.bucket,config.region,config.key].join('|'),
    async get(key) {
      const response=await fetcher(await signedS3Get(config,key));
      if(response.status===404)return null;
      if(response.status!==200||response.redirected)throw Error('PRIVATE_S3_READ_FAILED');
      const limit=key.endsWith('/metadata/catalog.json')?6_000_000:8_000_000;
      const declared=response.headers.get('content-length');
      if(declared!==null&&(!/^[0-9]+$/.test(declared)||Number(declared)>limit)){
        await response.body?.cancel();throw Error('PRIVATE_S3_OBJECT_TOO_LARGE');
      }
      const chunks=[];let total=0;
      if(!response.body)throw Error('PRIVATE_S3_EMPTY_BODY');
      const reader=response.body.getReader();
      try{
        while(true){const part=await reader.read();if(part.done)break;
          total+=part.value.length;if(total>limit){await reader.cancel();throw Error('PRIVATE_S3_OBJECT_TOO_LARGE')}
          chunks.push(part.value);
        }
      }finally{reader.releaseLock()}
      if(declared!==null&&total!==Number(declared))throw Error('PRIVATE_S3_LENGTH_MISMATCH');
      const bytes=new Uint8Array(total);let at=0;
      for(const part of chunks){bytes.set(part,at);at+=part.length}
      return {size:total,arrayBuffer:async()=>bytes.buffer,text:async()=>new TextDecoder().decode(bytes)};
    }
  };
}
