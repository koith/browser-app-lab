'use strict';
/* Actual existing published SHA+bytes from both gallery manifests:
 * verify owner albums sharing byte-identical public photos never call Render.
 */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
function rows(model,file){return JSON.parse(fs.readFileSync(path.join(root,'apps',model+'-gallery',file),'utf8')).albums;}
function key(p){return [p.sha256,p.bytes,p.width,p.height].join('|');}
for(const model of ['mimmi','yui']){
 const directory=path.join(root,'apps',model+'-gallery');
 const owner=rows(model,'owner-index.json');
 const local=rows(model,'stored-albums.json');
 const bySha=new Map(),sameAlbum=new Set();
 for(const album of local)for(const p of album.images){
   if(!bySha.has(key(p)))bySha.set(key(p),p);
   sameAlbum.add(album.id+'|'+key(p));
 }
 const unrelated=[];
 for(const album of owner)for(const p of album.images){
   if(bySha.has(key(p))&&!sameAlbum.has(album.id+'|'+key(p)))
     unrelated.push({...p,ownerAlbum:album.id,albumId:album.id,
       url:'owner:'+album.id+':'+p.number,name:album.title||album.id});
 }
 assert.ok(unrelated.length>=(model==='mimmi'?150:5),
   model+' expected real same-SHA Pages copies in other albums');
 const html=fs.readFileSync(path.join(directory,'index.html'),'utf8');
 const a=html.indexOf('function localPhotoKey(id,p){');
 const b=html.indexOf('\nconst ownerObserver=',a);
 assert.ok(a>0&&b>a);
 const ctx={localStored:local,stored:[],localPreviewIndex:new Map(),
   localStoredByExactSha:new Map(),canonicalId:id=>id,
   validImages:album=>album.images,
   esc:txt=>String(txt).replace(/"/g,'&quot;'),
   rotationAttributes:()=>''};
 vm.createContext(ctx);
 vm.runInContext(html.slice(a,b)+
   ';globalThis.api={rebuildLocalPreviewIndex,localSavedFor,photoHTML,exactSavedViewerCopy}',ctx);
 ctx.api.rebuildLocalPreviewIndex();
 let supported=0,withoutProvider=0;
 for(const p of unrelated){
   const local=ctx.api.localSavedFor(p);
   assert.ok(local&&local.url.startsWith('stored-albums/'),
     model+' exact cross-album bytes must resolve locally');
   assert.equal(key(local),key(p));
   assert.equal(ctx.api.exactSavedViewerCopy(p).url,local.url);
   const card=ctx.api.photoHTML(p,0);
   assert.ok(card.includes('src="'+local.url+'"'),
     model+' must paint existing SHA-verified public photo without 503');
   assert.ok(card.includes('data-owner="'+p.url+'"'),
     model+' original owner metadata must remain available');
   supported++;
   if(p.bytes>700000)withoutProvider++;
   for(const changes of [{sha256:'a'.repeat(64)}, {bytes:p.bytes+1},
      {width:p.width+1},{height:p.height+1}]){
     if(changes.sha256===p.sha256)continue;
     assert.equal(ctx.api.localSavedFor({...p,...changes}),null,
       model+' must not substitute a different SHA/size/dimension');
   }
 }
 console.log('GALLERY_CROSS_ALBUM_EXACT_STATIC_FALLBACK_PASS',JSON.stringify({
   model,owner_cross_album_photos:supported,
   large_exact_originals_now_prefer_pages:withoutProvider,
   no_new_public_files:true,other_model_content_never_indexed:true
 }));
}
