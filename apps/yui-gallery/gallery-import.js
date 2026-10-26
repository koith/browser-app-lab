'use strict';
/* Photo first. Local ZIPs are optional; all image processing stays on device. */
const importNames={'athletic-club104':'Athletic Club','teddy-bear97':'SWEETBOX · Teddy Bear','wet-yui80':'Wet Yui','yuis-present33':'SWEETBOX · Yui’s Present','green91':'Green (AI 보정 웹판)'};
async function photoDigest(bytes){
 const raw=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw))).map(n=>n.toString(16).padStart(2,'0')).join('');
}
function note(message,bad=false){
 const n=el('notice');if(!n)return;
 n.textContent=message;n.hidden=false;n.classList.toggle('bad',bad);
}
async function parsePhotobook(zip,label){
 const mEntry=zip.file('manifest.json');if(!mEntry)throw Error(label+': 목록 없음');
 const m=JSON.parse(await mEntry.async('string'));
 const id=m.id==='v04'?'teddy-bear97':m.id;
 if(!/^[a-z0-9][a-z0-9-]{1,100}$/.test(id)||!Array.isArray(m.images)||m.images.length<1||m.images.length>5000)throw Error(label+': 목록 형식 오류');
 const rows=m.images,expected=m.advertised_count??m.declared??m.display_count??m.expected;
 if(Number.isInteger(expected)&&expected!==rows.length)throw Error(label+': 전체 장수 불일치');
 const seen=new Set(),raw=[];
 for(const [i,item] of rows.entries()){
  const number=Number(item.number??item.n??i+1),filename=String(item.file||'');
  if(!Number.isInteger(number)||number<1||seen.has(number)||!/^[0-9]{3,4}\.(jpg|jpeg|png|webp)$/i.test(filename))throw Error(label+': 파일명 또는 순번 오류');
  seen.add(number);
  const entry=zip.file('images/'+filename);
  if(!entry||entry._data?.uncompressedSize>30000000)throw Error(label+': 이미지 누락 또는 크기 초과');
  const blob=await entry.async('uint8array');
  if(blob.length!==item.bytes||await photoDigest(blob)!==item.sha256)throw Error(label+': 사진 해시 검증 실패 #'+number);
  const w=Number(item.width),h=Number(item.height);
  if(!(w>0&&h>0))throw Error(label+': 픽셀 크기 누락');
  raw.push({number,bytes:blob,width:w,height:h,sha256:item.sha256,filename});
 }
 raw.sort((a,b)=>a.number-b.number);
 const area=raw.reduce((sum,p)=>sum+p.width*p.height,0)/raw.length;
 return {id,title:importNames[id]||m.title||id,site:'내 화보',area,raw};
}
async function parseZipImport(file){
 if(file.size>180000000)throw Error(file.name+': ZIP 180MB 초과');
 const outer=await JSZip.loadAsync(file,{checkCRC32:true});
 const inner=Object.keys(outer.files).filter(p=>p.toLowerCase().endsWith('.zip')&&!outer.files[p].dir);
 if(!inner.length)return [await parsePhotobook(outer,file.name)];
 const found=[];
 for(const path of inner){
  const f=outer.file(path);
  if(f._data?.uncompressedSize>150000000)throw Error(path+': ZIP 크기 초과');
  const data=await f.async('uint8array');
  found.push(await parsePhotobook(await JSZip.loadAsync(data,{checkCRC32:true}),path));
 }
 return found;
}
function activateImports(imported){
 const sorted=[...imported.values()];
 const ids=new Set(sorted.map(x=>x.id));
 if(ids.has('teddy-bear97'))ids.add('v04');
 state.albums=state.albums.filter(a=>!ids.has(a.id));
 state.photoSet=state.photoSet.filter(p=>!ids.has(p.album));
 for(const a of sorted){
  const albumImages=[];
  for(const item of a.raw){
   const mime=item.filename.toLowerCase().endsWith('.png')?'image/png':item.filename.toLowerCase().endsWith('.webp')?'image/webp':'image/jpeg';
   const url=URL.createObjectURL(new Blob([item.bytes],{type:mime}));
   albumImages.push({url,sha256:item.sha256,width:item.width,height:item.height});
   state.photoSet.push({url,title:a.title,album:a.id,number:item.number,stored:true,width:item.width,height:item.height});
  }
  state.albums.push({id:a.id,title:a.title,site:'내 화보',images:albumImages,expected:albumImages.length});
 }
 state.album=null;state.view='photos';el('search').value='';render();
}
el('files').addEventListener('change',async e=>{
 const files=[...e.target.files];if(!files.length)return;
 if(!window.JSZip){note('압축파일 처리에 필요한 연결을 확인해 주세요.',true);return}
 e.target.disabled=true;
 const results=new Map(),errors=[];
 try{
  for(const [index,file] of files.entries()){
   note('사진 확인 중 · '+(index+1)+'/'+files.length);
   try{
    const groups=await parseZipImport(file);
    for(const a of groups){
     const old=results.get(a.id);
     if(!old||old.raw.length<a.raw.length||(old.raw.length===a.raw.length&&old.area<a.area))results.set(a.id,a);
    }
   }catch(error){errors.push(error.message)}
  }
  if(results.size)activateImports(results);
  const count=[...results.values()].reduce((s,a)=>s+a.raw.length,0);
  note(errors.length?('가져온 사진 '+count+'장 · 일부 오류: '+errors.join(', ')):(count+'장 불러왔습니다'),!!errors.length);
 }finally{e.target.disabled=false;e.target.value=''}
});
document.querySelector('.library-link[for="files"]')?.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el('files').click()}});
