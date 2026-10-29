/* Personal archive: verified, device-local image bytes. No external image origins or credentials. */
(function(root){
'use strict';
const DB='photobook-personal-vault-v1',MAX_ENTRY=30*1024*1024,MAX_ITEMS=15000;
const hex=b=>Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('');
const digest=async b=>hex(await crypto.subtle.digest('SHA-256',await b.arrayBuffer()));
function database(){
 return new Promise((resolve,reject)=>{
  const req=indexedDB.open(DB,1);
  req.onupgradeneeded=()=>{const db=req.result;db.createObjectStore('media');db.createObjectStore('albums')};
  req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
 });
}
async function operation(store,mode,run){
 const db=await database();
 return new Promise((resolve,reject)=>{
  const tx=db.transaction(store,mode),req=run(tx.objectStore(store));
  req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
  tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
 }).finally(()=>db.close());
}
const get=(store,key)=>operation(store,'readonly',s=>s.get(key));
const put=(store,key,value)=>operation(store,'readwrite',s=>s.put(value,key));
const readAll=store=>operation(store,'readonly',s=>s.getAll());
const u16=(v,n)=>v.getUint16(n,true),u32=(v,n)=>v.getUint32(n,true);
async function zipEntries(file){
 if(!file||!file.name.toLowerCase().endsWith('.zip')||file.size>2*1024**3)throw Error('2GB 이하 ZIP 보관본을 선택하세요.');
 const tailBytes=await file.slice(Math.max(0,file.size-65557)).arrayBuffer(),v=new DataView(tailBytes);
 let e=-1;for(let i=v.byteLength-22;i>=0;i--)if(u32(v,i)===0x06054b50){e=i;break}
 if(e<0||u16(v,e+10)>MAX_ITEMS||u16(v,e+10)===65535)throw Error('ZIP 목차가 없거나 너무 큽니다.');
 const count=u16(v,e+10),size=u32(v,e+12),start=u32(v,e+16);
 if(start+size>file.size||size>4*1024*1024)throw Error('ZIP 목차 크기가 올바르지 않습니다.');
 const central=new DataView(await file.slice(start,start+size).arrayBuffer()),decoder=new TextDecoder(),entries=new Map();let p=0;
 for(let i=0;i<count;i++){
  if(p+46>central.byteLength||u32(central,p)!==0x02014b50)throw Error('ZIP 목차가 손상되었습니다.');
  const method=u16(central,p+10),compressed=u32(central,p+20),bytes=u32(central,p+24),
        nl=u16(central,p+28),el=u16(central,p+30),cl=u16(central,p+32),offset=u32(central,p+42);
  if(p+46+nl+el+cl>central.byteLength)throw Error('ZIP 경로가 손상되었습니다.');
  const name=decoder.decode(new Uint8Array(central.buffer,central.byteOffset+p+46,nl));
  if(name&&!name.endsWith('/')&&!name.startsWith('/')&&!name.split('/').some(s=>s==='..'||s==='.')&&!entries.has(name)){
   if(![0,8].includes(method)||bytes>MAX_ENTRY)throw Error('지원하지 않는 압축 방식 또는 30MB 초과 파일: '+name);
   entries.set(name,{method,compressed,bytes,offset});
  }
  p+=46+nl+el+cl;
 }
 async function extract(name){
  const x=entries.get(name);if(!x)throw Error('ZIP에 실파일이 없습니다: '+name);
  const h=new DataView(await file.slice(x.offset,x.offset+30).arrayBuffer());
  if(h.byteLength!==30||u32(h,0)!==0x04034b50)throw Error('ZIP 사진 헤더가 손상되었습니다.');
  const off=x.offset+30+u16(h,26)+u16(h,28);
  if(off+x.compressed>file.size)throw Error('ZIP 사진 범위가 올바르지 않습니다.');
  const source=file.slice(off,off+x.compressed);
  let blob=source;
  if(x.method===8){
   if(!('DecompressionStream' in root))throw Error('이 브라우저에서 압축 해제할 수 없습니다. 무압축 ZIP을 이용하세요.');
   try{blob=await new Response(source.stream().pipeThrough(new DecompressionStream('deflate-raw'))).blob()}
   catch{throw Error('ZIP 압축을 해제하지 못했습니다. 무압축 ZIP으로 다시 저장해 주세요.')}
  }
  if(blob.size!==x.bytes)throw Error('ZIP 파일 크기 불일치: '+name);
  return blob;
 }
 return {entries,extract};
}
function validate(manifest,model){
 if(!manifest||manifest.model!==model||!Array.isArray(manifest.albums))throw Error('이 모델의 보관본 ZIP이 아닙니다.');
 const albums=[],ids=new Set();let count=0;
 for(const a of manifest.albums){
  if(typeof a.id!=='string'||!/^[a-z0-9][a-z0-9-]{1,100}$/.test(a.id)||ids.has(a.id)||!Array.isArray(a.images))throw Error('화보 식별 정보가 잘못되었습니다.');
  ids.add(a.id);const nums=new Set();
  const images=a.images.map(p=>{
   if(!Number.isSafeInteger(p.number)||p.number<1||nums.has(p.number)||!Number.isSafeInteger(p.bytes)||p.bytes<5000||p.bytes>MAX_ENTRY||
      !/^[a-f0-9]{64}$/.test(p.sha256)||!Number.isSafeInteger(p.width)||p.width<100||!Number.isSafeInteger(p.height)||p.height<100||
      typeof p.url!=='string'||!/^photos\/[a-f0-9]{64}\.(jpg|jpeg|webp|png)$/i.test(p.url)||!p.url.includes(p.sha256))throw Error('사진의 파일 검증 정보가 잘못되었습니다.');
   nums.add(p.number);return {number:p.number,sha256:p.sha256,bytes:p.bytes,width:p.width,height:p.height,url:p.url};
  });
  count+=images.length;if(count>MAX_ITEMS)throw Error('ZIP 사진이 너무 많습니다.');
  albums.push({id:a.id,title:String(a.title||a.id),publisher:String(a.publisher||''),expected:Number.isSafeInteger(a.expected)?a.expected:null,images});
 }
 if(!count||manifest.physical_verified_image_count!==undefined&&manifest.physical_verified_image_count!==count)throw Error('사진 수량이 일치하지 않습니다.');
 return {albums,count};
}
async function importZip(file,model,progress=()=>{}){
 const {entries,extract}=await zipEntries(file);
 const path=[...entries.keys()].find(x=>x==='manifest.json'||x.endsWith('/manifest.json'));
 if(!path)throw Error('manifest.json이 없는 ZIP입니다.');
 const manifest=JSON.parse(await (await extract(path)).text());
 const {albums,count}=validate(manifest,model),prefix=path.slice(0,-'manifest.json'.length),seen=new Set();let done=0;
 progress('실제 사진 '+count+'장의 바이트와 SHA-256을 검증합니다.');
 for(const a of albums)for(const p of a.images){
  if(!seen.has(p.sha256)){
   const blob=await extract(prefix+p.url),bytes=await blob.arrayBuffer();
   if(bytes.byteLength!==p.bytes||hex(await crypto.subtle.digest('SHA-256',bytes))!==p.sha256)throw Error('사진 SHA-256 검증 실패: '+p.sha256.slice(0,12));
   // WebKit cannot reliably persist file-backed Blob slices in IndexedDB.
   // Store a structured-cloneable ArrayBuffer; create a Blob only for display.
   await put('media',model+':'+p.sha256,bytes);
   seen.add(p.sha256);
  }
  done++;if(done%10===0||done===count)progress('검증·보관 '+done+' / '+count+'장');
 }
 // Merge incremental verified batches by album and photo number. Do not discard previously saved positions.
 for(const a of albums){
  const key=model+':'+a.id,previous=await get('albums',key),byNumber=new Map();
  for(const p of previous?.images||[])byNumber.set(p.number,p);
  for(const p of a.images){
   const prior=byNumber.get(p.number);
   // Higher actual image resolution wins. Equal resolution prefers the newly imported bytes.
   if(!prior||p.width*p.height>=prior.width*prior.height)byNumber.set(p.number,p);
  }
  const images=[...byNumber.values()].sort((x,y)=>x.number-y.number);
  const expected=Math.max(previous?.expected||0,a.expected||0)||null;
  await put('albums',key,{...previous,...a,model,expected,images,imported_at:new Date().toISOString()});
 }
 if(root.navigator?.storage?.persist)try{await root.navigator.storage.persist()}catch{}
 return {albums:albums.length,images:count,unique:seen.size};
}
async function albums(model){
 const rows=await readAll('albums');
 return rows.filter(a=>a.model===model).map(a=>({...a,vaultHosted:true,images:a.images.map(p=>({
  ...p,originalExtension:p.url?.split('.').pop(),url:'vault:'+model+':'+a.id+':'+p.number,vaultAlbum:a.id,vaultModel:model
 }))}));
}
const cache=new Map();
async function asset(p){
 const key=p.vaultModel+':'+p.sha256;
 if(cache.has(key))return cache.get(key);
 const saved=await get('media',key);
 const ext=p.originalExtension||'';
 const mime=ext==='webp'?'image/webp':ext==='png'?'image/png':'image/jpeg';
 const blob=saved instanceof ArrayBuffer?new Blob([saved],{type:mime}):saved instanceof Blob?saved:null;
 if(!blob||blob.size!==p.bytes||await digest(blob)!==p.sha256)throw Error('이 기기의 저장본이 없거나 손상되었습니다. ZIP을 다시 가져오세요.');
 const url=URL.createObjectURL(blob);cache.set(key,url);
 if(cache.size>40){const first=cache.keys().next().value;URL.revokeObjectURL(cache.get(first));cache.delete(first)}
 return url;
}
root.PhotoVault={importZip,albums,asset};
})(globalThis);
