'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

for(const model of ['mimmi','yui']){
 const html=fs.readFileSync(path.join(__dirname,'..',model+'-gallery','index.html'),'utf8');
 const a=html.indexOf('function localPhotoKey(id,p){');
 const b=html.indexOf('function photoHTML(p,i){',a);
 const c=html.indexOf('\nconst ownerObserver=',b);
 assert.ok(a>0&&b>a&&c>b,model+' exact thumbnail helpers must exist');
 const source=html.slice(a,c);
 const sha='a'.repeat(64);
 const local={sha256:sha,bytes:120000,width:800,height:1200,
   url:'stored-albums/safe/local.webp',number:1};
 const ctx={localStored:[{id:'safe',images:[local]}],
   stored:[{id:'safe',images:[local]}],localPreviewIndex:new Map(),
   canonicalId:id=>id,validImages:a=>a.images,
   esc:s=>String(s).replace(/"/g,'&quot;'),
   rotationAttributes:()=>''};
 vm.createContext(ctx);
 vm.runInContext(source+
   ';globalThis.testApi={rebuildLocalPreviewIndex,photoHTML,localPhotoKey,exactSavedViewerCopy}',ctx);
 const api=ctx.testApi;
 api.rebuildLocalPreviewIndex();
 const owner={...local,albumId:'safe',ownerAlbum:'safe',
   url:'owner:safe:1',name:'saved',number:1};
 assert.equal(api.exactSavedViewerCopy(owner).url,local.url,
   model+' lightbox must use exact same-SHA saved bytes');
 assert.equal(api.exactSavedViewerCopy({...owner,albumId:'other'}),null);
 assert.equal(api.exactSavedViewerCopy({...owner,sha256:'b'.repeat(64)}),null);
 assert.equal(api.exactSavedViewerCopy({...owner,bytes:120001}),null);
 assert.equal(api.exactSavedViewerCopy({...owner,width:801}),null);
 assert.equal(api.exactSavedViewerCopy({...owner,ownerAlbum:undefined}),null);
 const fast=api.photoHTML(owner,0);
 assert.ok(fast.includes('src="stored-albums/safe/local.webp"'),model);
 assert.ok(fast.includes('data-owner="owner:safe:1"'),model);
 assert.ok(fast.includes('data-owner-variant="local"'),model);
 assert.ok(fast.includes('decoding="async"'),model);
 const unrelated=api.photoHTML({...owner,albumId:'other'},0);
 assert.ok(!unrelated.includes('src="stored-albums/'),model+' album must match');
 const otherSha=api.photoHTML({...owner,sha256:'b'.repeat(64)},0);
 assert.ok(!otherSha.includes('src="stored-albums/'),model+' SHA must match');
 const otherSize=api.photoHTML({...owner,bytes:120001},0);
 assert.ok(!otherSize.includes('src="stored-albums/'),model+' byte size must match');
 const otherDimensions=api.photoHTML({...owner,width:801},0);
 assert.ok(!otherDimensions.includes('src="stored-albums/'),model+' dimensions must match');
 const massive={...local,bytes:700001};
 ctx.localStored=[{id:'safe',images:[massive]}];
 api.rebuildLocalPreviewIndex();
 const large=api.photoHTML({...owner,bytes:700001},0);
 assert.ok(!large.includes('src="stored-albums/'),model+' large originals lazy gateway');
 assert.equal(api.exactSavedViewerCopy({...owner,bytes:700001}).url,massive.url,
   model+' full-screen lightbox may use large SHA-identical committed originals');
 const direct=api.photoHTML({...owner,ownerAlbum:undefined,
   url:'stored-albums/safe/local.webp'},0);
 assert.ok(direct.includes('src="stored-albums/safe/local.webp"'),model);
 assert.ok(html.includes('const localCopy=cloudCover?localPreviewIndex.get(localPhotoKey(owned.id,selected)):null;'),
   model+' album covers must use shared O(1) index');
 assert.ok(html.includes('  rebuildLocalPreviewIndex();'),model+' index built after union');
 console.log('GALLERY_LOCAL_SHA_DETAIL_FASTPATH_AND_FALLBACK_PASS',model);
}
