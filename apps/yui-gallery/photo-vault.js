/* Personal archive: verified, device-local image bytes. No external image origins or credentials. */
(function(root){
'use strict';
const DB='photobook-personal-vault-v1';
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
const readAll=store=>operation(store,'readonly',s=>s.getAll());
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
 if(!blob||blob.size!==p.bytes||await digest(blob)!==p.sha256)throw Error('이 기기의 저장본이 없거나 손상되었습니다.');
 const url=URL.createObjectURL(blob);cache.set(key,url);
 if(cache.size>40){const first=cache.keys().next().value;URL.revokeObjectURL(cache.get(first));cache.delete(first)}
 return url;
}
root.PhotoVault={albums,asset};
})(globalThis);
