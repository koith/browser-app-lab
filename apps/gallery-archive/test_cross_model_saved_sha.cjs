'use strict';
// Check every physically archived SHA across both model galleries, without
// asserting identity from a face or deleting any image.
const fs=require('node:fs'),path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const byModel={};
for(const model of ['mimmi','yui']){
 const dir=path.join(root,model+'-gallery');
 const read=file=>JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'));
 const exclusion=read('identity-exclusions.json');
 const excludedAlbum=new Set([...(exclusion.excluded_album_ids||[]),
   ...(exclusion.excluded_source_ids||[])]);
 const excludedURL=new Set(exclusion.excluded_source_urls||[]);
 const excludedSHA=new Set(exclusion.excluded_image_sha256||[]);
 const saved=[...read('stored-albums.json').albums,
              ...read('owner-index.json').albums];
 const sha=new Map();
 let scanned=0,filtered=0;
 for(const album of saved){
  if(excludedAlbum.has(album.id)||
      [album.source,...(album.source_pages||[])].some(u=>excludedURL.has(u))){
   filtered+=(album.images||[]).length;
   continue;
  }
  for(const photo of album.images||[]){
   if(excludedSHA.has(photo.sha256)){filtered++;continue;}
   assert.match(photo.sha256,/^[a-f0-9]{64}$/,
     model+' invalid saved-image hash for '+album.id);
   scanned++;
   if(!sha.has(photo.sha256))sha.set(photo.sha256,new Set());
   sha.get(photo.sha256).add(album.id);
  }
 }
 byModel[model]={sha,scanned,filtered};
}
const collisions=[];
for(const [sha,albums] of byModel.mimmi.sha){
 if(byModel.yui.sha.has(sha))
  collisions.push({sha,mimmi:[...albums],
    yui:[...byModel.yui.sha.get(sha)]});
}
assert.deepEqual(collisions,[],
  'Same photo bytes registered under two distinct models: '+JSON.stringify(
    collisions.slice(0,8)));
console.log('GALLERY_CROSS_MODEL_ORIGINAL_SHA_COLLISION_FREE_PASS',JSON.stringify({
  mimmi:{registered:byModel.mimmi.scanned,uniqueSHA:byModel.mimmi.sha.size,
    filtered:byModel.mimmi.filtered},
  yui:{registered:byModel.yui.scanned,uniqueSHA:byModel.yui.sha.size,
    filtered:byModel.yui.filtered},
  sharedSHA:collisions.length,
}));
