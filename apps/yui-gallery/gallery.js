'use strict';
const el=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={view:'photos',album:null,albums:[],photoSet:[],shown:[],selected:0};
function norm(s){return String(s||'').normalize('NFKC').toLocaleLowerCase()}
function title(a){return a.title==='Yui · 공개 미리보기 (화보 미분류)'?a.site+' · 공개 사진':a.title}
function isStored(x){return typeof x.url==='string'&&/^stored-albums\/[a-z0-9-]+\/[0-9a-z_.-]+\.(?:jpg|jpeg|png|webp)$/i.test(x.url)}
const safeExternal=url=>typeof url==='string'&&/^https:\/\//.test(url)?url:'';
function sourcePhoto(album,image,i){return {url:image.url,source_url:image.source_url||'',title:title(album),album:album.id,number:i+1,width:image.width||0,height:image.height||0,sha256:image.sha256||'',stored:true}}
function sourceSNS(x,i){const u=safeExternal(x.url);return {url:u,source_url:u,title:x.caption||'Yui',album:'sns',number:i+1,stored:false}}
function orderItems(items){return el('order').value==='reverse'?[...items].reverse():items}
function currentAlbums(){const q=norm(el('search').value);return state.albums.filter(a=>norm(title(a)+' '+a.site).includes(q))}
function cards(items){
 const root=el('photoGrid');state.shown=items;
 root.innerHTML=items.map((p,i)=>'<button type="button" class="photo-card" data-index="'+i+'" aria-label="'+esc(p.title)+' 사진 '+p.number+'"><img loading="lazy" decoding="async" src="'+esc(p.url)+'" alt="'+esc(p.title)+' 사진 '+p.number+'" '+(p.stored?'':'referrerpolicy="no-referrer"')+'><span class="photo-label">'+esc(p.title)+'</span></button>').join('');
 root.querySelectorAll('.photo-card').forEach(b=>b.onclick=()=>openViewer(+b.dataset.index));
 root.querySelectorAll('img').forEach(im=>im.onerror=()=>{const card=im.closest('.photo-card');card.classList.add('load-error');im.alt='이미지 불러오기 실패';card.style.minHeight='100px';});
 el('count').textContent=items.length+'장';
 el('empty').hidden=items.length!==0;
}
function renderAlbums(){
 const current=currentAlbums();
 el('albumGrid').innerHTML=current.map(a=>{
 const photos=a.images.filter(isStored);
 const cover=photos[0]?.url||'';
 return '<button type="button" class="album-card" data-id="'+esc(a.id)+'"><img class="album-cover" loading="lazy" src="'+esc(cover)+'" alt="'+esc(title(a))+' 표지"><span class="album-title">'+esc(title(a))+'</span><span class="album-sub">'+photos.length+'장</span></button>';
 }).join('');
 el('albumGrid').querySelectorAll('button').forEach(b=>b.onclick=()=>{state.album=b.dataset.id;state.view='photos';render()});
 el('count').textContent=current.length+'개';
 el('empty').hidden=current.length!==0;
}
function render(){
 const hasAlbum=!!state.album;
 el('heading').textContent=hasAlbum?title(state.albums.find(a=>a.id===state.album)||{}):state.view==='albums'?'화보':state.view==='sns'?'SNS':'사진';
 el('subhead').textContent='';
 el('photoGrid').hidden=state.view==='albums'&&!hasAlbum;
 el('albumGrid').hidden=state.view!=='albums'||hasAlbum;
 el('search').placeholder=state.view==='albums'?'화보 검색':'사진·화보 검색';
 if(state.view==='albums'&&!hasAlbum)renderAlbums();
 else if(state.view==='sns'){
  const q=norm(el('search').value);
  cards(orderItems(state.photoSet.filter(p=>p.album==='sns'&&norm(p.title).includes(q))));
 }else{
  const q=norm(el('search').value);
  cards(orderItems(state.photoSet.filter(p=>p.stored&&(!state.album||p.album===state.album)&&(!q||norm(p.title).includes(q)))));
 }
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',!hasAlbum&&b.dataset.view===state.view));
}
function openViewer(i){
 if(!state.shown.length)return;
 state.selected=(i+state.shown.length)%state.shown.length;const p=state.shown[state.selected];
 el('viewer').hidden=false;document.body.style.overflow='hidden';
 el('large').src=p.source_url&&p.album==='sns'?p.source_url:p.url;
 el('viewerTitle').textContent=p.title;
 el('position').textContent=(state.selected+1)+' / '+state.shown.length;
}
function closeViewer(){el('viewer').hidden=true;document.body.style.overflow='';el('large').removeAttribute('src')}
function changePhoto(delta){openViewer(state.selected+delta)}
el('close').onclick=closeViewer;el('prev').onclick=()=>changePhoto(-1);el('next').onclick=()=>changePhoto(1);
el('save').onclick=async()=>{
 const p=state.shown[state.selected];if(!p)return;
 const path=p.source_url&&p.album==='sns'?p.source_url:p.url;
 try{
  const r=await fetch(path);if(!r.ok)throw Error('HTTP '+r.status);
  const blob=await r.blob();if(!blob.type.startsWith('image/'))throw Error('Not an image');
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(p.album+'-'+String(p.number).padStart(4,'0')+'.'+(blob.type.includes('png')?'png':blob.type.includes('webp')?'webp':'jpg'));
  a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
 }catch{window.open(path,'_blank','noopener,noreferrer')}
};
el('viewer').onclick=e=>{if(e.target===el('viewer'))closeViewer()};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeViewer();if(el('viewer').hidden)return;if(e.key==='ArrowLeft')changePhoto(-1);if(e.key==='ArrowRight')changePhoto(1)});
let touchX=0;el('viewer').addEventListener('touchstart',e=>{touchX=e.changedTouches[0].clientX},{passive:true});el('viewer').addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-touchX;if(Math.abs(dx)>55)changePhoto(dx<0?1:-1)},{passive:true});
el('search').oninput=render;el('order').onchange=render;
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.album=null;state.view=b.dataset.view;el('search').value='';render();window.scrollTo({top:0,behavior:'instant'})});
async function initialize(){
 try{
  const [stored,sns]=await Promise.all([fetch('stored-albums.json').then(r=>{if(!r.ok)throw Error('stored');return r.json()}),fetch('feed.json').then(r=>r.ok?r.json():{images:[]}).catch(()=>({images:[]}))]);
  state.albums=(stored.albums||[]).filter(a=>Array.isArray(a.images)&&a.images.some(isStored));
  state.photoSet=[...state.albums.flatMap(a=>a.images.filter(isStored).map((x,i)=>sourcePhoto(a,x,i))),...(sns.images||[]).filter(x=>safeExternal(x.url)).map(sourceSNS)];
  // Photo list begins with the actual image files, not source links or a setup form.
  render();
 }catch(e){el('empty').hidden=false;el('empty').textContent='사진을 불러오지 못했습니다.';el('count').textContent='0장'}
}
initialize();
