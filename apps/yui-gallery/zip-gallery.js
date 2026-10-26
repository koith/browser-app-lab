'use strict';
const el=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles={'athletic-club104':'Athletic Club','teddy-bear97':'SWEETBOX · Teddy Bear','wet-yui80':'Wet Yui','yuis-present33':'SWEETBOX · Yui’s Present','green91':'Green (AI 보정 웹판)'};
const albums=new Map(),urlCache=new Map();let active=null,selected=0,observer=null,renderVersion=0;
function setStatus(s,bad=false){el('status').textContent=s;el('status').classList.toggle('error',bad)}
function mb(n){return (n/1048576).toFixed(1)+'MB'}
async function hash(bytes){
 const buf=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buf))).map(n=>n.toString(16).padStart(2,'0')).join('');
}
function save(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),40000)}
async function addArchive(zip,raw,label){
 const entry=zip.file('manifest.json');if(!entry)throw Error(label+': manifest.json 없음');
 const m=JSON.parse(await entry.async('string')),id=m.id==='v04'?'teddy-bear97':String(m.id);
 if(!/^[a-z0-9][a-z0-9-]{1,100}$/.test(id))throw Error(label+': 안전하지 않은 작품 ID');
 const rows=m.images;if(!Array.isArray(rows)||rows.length<1||rows.length>5000)throw Error(id+': 사진 목록 오류');
 const expected=m.advertised_count??m.declared??m.display_count??m.expected;
 if(Number.isInteger(expected)&&expected!==rows.length)throw Error(id+': 출처 수량과 파일 수 불일치');
 const images=[],seen=new Set();let total=0,area=0,minW=Infinity,maxW=0;
 for(const [i,r] of rows.entries()){
  const n=Number(r.number??r.n??i+1),file=String(r.file||'');
  if(!Number.isInteger(n)||n<1||seen.has(n)||!/^[0-9]{3,4}\.(jpg|jpeg|png|webp)$/i.test(file))throw Error(id+': 잘못된 사진 순번/파일명');
  seen.add(n);const img=zip.file('images/'+file);
  if(!img||!/^[a-f0-9]{64}$/.test(r.sha256||''))throw Error(id+': 파일·해시 누락');
  if(img._data?.uncompressedSize>140000000)throw Error(id+': 파일 크기 초과');
  const bytes=await img.async('uint8array');
  if(bytes.byteLength!==r.bytes||await hash(bytes)!==r.sha256)throw Error(id+': '+file+' 원본 SHA-256 불일치');
  const w=Number(r.width),h=Number(r.height);
  if(!(w>0&&h>0))throw Error(id+': 이미지 해상도 오류');
  total+=bytes.byteLength;area+=w*h;minW=Math.min(minW,w);maxW=Math.max(maxW,w);
  images.push({n,file,entry:img,width:w,height:h,bytes:r.bytes,sha:r.sha256});
 }
 images.sort((a,b)=>a.n-b.n);
 const a={id,title:titles[id]||m.title||id,images,total,area:area/images.length,minW,maxW,raw,quality:id==='green91'?'AI 보정 공개 웹판':'공개 웹판'};
 const old=albums.get(id);
 if(!old||old.images.length<a.images.length||(old.images.length===a.images.length&&old.area<a.area))albums.set(id,a);
 return id+' '+images.length+'장 확인';
}
async function openFile(file){
 const outer=await JSZip.loadAsync(file,{checkCRC32:true});
 const inner=Object.keys(outer.files).filter(k=>k.toLowerCase().endsWith('.zip')&&!outer.files[k].dir);
 if(inner.length){
  const result=[];
  for(const k of inner){
   const e=outer.file(k);
   if(e._data?.uncompressedSize>150000000)throw Error(k+': 압축 내부 파일 초과');
   const raw=await e.async('uint8array');
   result.push(await addArchive(await JSZip.loadAsync(raw,{checkCRC32:true}),new Blob([raw],{type:'application/zip'}),k));
  }
  return result;
 }
 return [await addArchive(outer,file,file.name)];
}
el('files').onchange=async e=>{
 if(!window.JSZip){setStatus('ZIP 라이브러리 로드 실패: 인터넷 연결 확인',true);return}
 const files=Array.from(e.target.files);if(!files.length)return;
 e.target.disabled=true;const ok=[],bad=[];
 try{
  for(const [i,f] of files.entries()){
   setStatus('파일 '+(i+1)+'/'+files.length+' · '+f.name+' 사진 SHA-256 전수 검사 중');
   try{ok.push(...await openFile(f))}catch(err){bad.push(f.name+': '+err.message)}
  }
  showAlbums();
  setStatus('검증된 실물 파일 '+[...albums.values()].reduce((v,a)=>v+a.images.length,0)+'장 · '+albums.size+'개 화보\n'+ok.join('\n')+(bad.length?'\n실패: '+bad.join('; '):''),!!bad.length);
 }finally{e.target.disabled=false}
};
async function photoUrl(a,p){
 const key=a.id+'/'+p.n+'/'+p.sha;if(urlCache.has(key))return urlCache.get(key);
 const bytes=await p.entry.async('uint8array');
 if(bytes.byteLength!==p.bytes||await hash(bytes)!==p.sha)throw Error('이미지 재검증 실패');
 const type=p.file.endsWith('.png')?'image/png':p.file.endsWith('.webp')?'image/webp':'image/jpeg';
 const url=URL.createObjectURL(new Blob([bytes],{type}));urlCache.set(key,url);
 if(urlCache.size>100){const first=urlCache.keys().next().value;URL.revokeObjectURL(urlCache.get(first));urlCache.delete(first)}
 return url;
}
function previews(selector,items){
 if(observer)observer.disconnect();const version=++renderVersion;
 observer=new IntersectionObserver(async entries=>{
  for(const e of entries){if(!e.isIntersecting)continue;observer.unobserve(e.target);
   const a=items.find(x=>x.id===e.target.dataset.album)||active;
   const i=Number(e.target.dataset.i||0);if(!a||!a.images[i])continue;
   try{const url=await photoUrl(a,a.images[i]);if(version===renderVersion&&e.target.isConnected)e.target.src=url}
   catch(err){e.target.alt='이미지 오류: '+err.message}
  }
 },{rootMargin:'350px'});
 document.querySelectorAll(selector).forEach(x=>observer.observe(x));
}
function albumDownload(a){if(a?.raw)save(a.raw,a.id+'_verified_web.zip')}
function showAlbums(){
 const all=[...albums.values()].sort((a,b)=>a.title.localeCompare(b.title,'ko'));
 const q=el('query').value.toLocaleLowerCase(),items=all.filter(a=>a.title.toLocaleLowerCase().includes(q));
 el('summary').textContent=all.length+'개 화보 · 실제 검증 '+all.reduce((n,a)=>n+a.images.length,0)+'장';
 el('albums').innerHTML=items.map(a=>'<article class="album"><img class="cover" data-album="'+esc(a.id)+'" data-i="0" alt="'+esc(a.title)+'"><strong>'+esc(a.title)+'</strong><p>실파일 '+a.images.length+'장 · '+mb(a.total)+'<br>'+a.minW+'–'+a.maxW+'px · '+esc(a.quality)+'</p><div class="actions"><button data-open="'+esc(a.id)+'">화보 열람</button><button data-zip="'+esc(a.id)+'">ZIP ↓</button></div></article>').join('');
 document.querySelectorAll('[data-open]').forEach(x=>x.onclick=()=>showAlbum(x.dataset.open));
 document.querySelectorAll('[data-zip]').forEach(x=>x.onclick=()=>albumDownload(albums.get(x.dataset.zip)));
 previews('#albums .cover',items);
}
el('query').oninput=showAlbums;
function showAlbum(id){
 active=albums.get(id);if(!active)return;
 el('list').hidden=true;el('detail').hidden=false;el('name').textContent=active.title;
 el('stats').textContent='실제 보관 '+active.images.length+'장 · '+mb(active.total)+' · '+active.quality+' · 발행사 원본 아님';
 el('photos').innerHTML=active.images.map((p,i)=>'<div class="tile" data-i="'+i+'"><img data-i="'+i+'" alt="사진 '+p.n+'"><small>#'+p.n+' · '+p.width+'×'+p.height+'</small></div>').join('');
 document.querySelectorAll('.tile').forEach(x=>x.onclick=()=>openImage(Number(x.dataset.i)));
 previews('#photos img',[active]);
}
el('back').onclick=()=>{active=null;el('detail').hidden=true;el('list').hidden=false;showAlbums()};
el('albumZip').onclick=()=>albumDownload(active);
let requested=0;
async function openImage(i){
 if(!active)return;
 selected=(i+active.images.length)%active.images.length;const thisRequest=++requested;
 const p=active.images[selected];el('viewer').classList.add('open');el('full').removeAttribute('src');
 el('viewerinfo').textContent=(selected+1)+'/'+active.images.length+' · 파일 검증 중';
 try{const url=await photoUrl(active,p);if(requested!==thisRequest)return;el('full').src=url;el('viewerinfo').textContent=(selected+1)+'/'+active.images.length+' · '+p.width+'×'+p.height}
 catch(err){if(requested===thisRequest)el('viewerinfo').textContent='파일 오류: '+err.message}
}
el('previous').onclick=()=>openImage(selected-1);
el('next').onclick=()=>openImage(selected+1);
el('close').onclick=()=>{el('viewer').classList.remove('open');el('full').removeAttribute('src')};
el('download').onclick=async()=>{if(!active)return;const p=active.images[selected],bytes=await p.entry.async('uint8array');if(await hash(bytes)!==p.sha){setStatus('원본 해시 불일치',true);return}save(new Blob([bytes]),active.id+'-'+p.file)};
document.addEventListener('keydown',e=>{if(e.key==='Escape')el('close').click();if(el('viewer').classList.contains('open')&&e.key==='ArrowRight')el('next').click();if(el('viewer').classList.contains('open')&&e.key==='ArrowLeft')el('previous').click()});
