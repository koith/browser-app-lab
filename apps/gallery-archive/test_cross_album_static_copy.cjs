#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ROOT=path.join(__dirname,'..');
const SHA='f'.repeat(64);
function load(model){
 const window={};
 const source=fs.readFileSync(path.join(ROOT,model+'-gallery/saved-photo-union.js'),'utf8');
 vm.runInNewContext(source,{window,Map,Set,Number,Array,TypeError}, {filename:model+'/saved-photo-union.js'});
 return window.SavedGalleryPhotoUnion.join;
}
function img(album,sha=SHA,bytes=15000,width=1200,height=1800,number=1){
 return {number,sha256:sha,bytes,width,height,url:'stored-albums/'+album+'/frame-001.jpg'};
}
function owner(album,photo){
 return { ...photo,ownerAlbum:album,url:'owner:'+album+':'+photo.number };
}
for(const model of ['mimmi','yui']){
 const join=load(model);
 const source={id:'physically-saved',images:[img('physically-saved')]};
 const archived={id:'private-only',images:[owner('private-only',img('physically-saved',SHA,15000,1200,1800,42))]};
 const items=join([[source][0]?[source]:[],[archived],[]]);
 const copy=items.find(a=>a.id==='private-only').images[0];
 assert.equal(copy.url,source.images[0].url,'must reuse same SHA physical Pages file');
 assert.equal(copy.originalAlbumId,'physically-saved');
 assert.equal(copy.shaPinnedLocalCopy,true);
 assert.equal(copy.ownerAlbum,undefined,'must NOT send recovered file back to unavailable Render');
 assert.equal(copy.number,42,'must retain original display numbering');

 for(const edited of [
   {...archived.images[0],bytes:14999},
   {...archived.images[0],width:1201},
   {...archived.images[0],height:1801},
   {...archived.images[0],sha256:'a'.repeat(64)}
 ]){
  const other=join([[source], [{id:'private-only',images:[edited]}],[]]).find(a=>a.id==='private-only').images[0];
  assert.equal(other.url,edited.url,'do not reuse bytes if SHA/dimensions/size differ');
  assert.equal(other.ownerAlbum,'private-only');
 }
 const fake={...source,images:[{...source.images[0],url:'https://untrusted.example/impersonated.jpg'}]};
 const denied=join([[fake],[archived],[]]).find(a=>a.id==='private-only').images[0];
 assert.equal(denied.ownerAlbum,'private-only','cannot use an arbitrary remote mirror as Pages proof');

 const physical=JSON.parse(fs.readFileSync(path.join(ROOT,model+'-gallery/stored-albums.json'),'utf8'));
 const catalogue=JSON.parse(fs.readFileSync(path.join(ROOT,model+'-gallery/owner-index.json'),'utf8'));
 const existing=physical.albums.map(a=>({...a,images:a.images||[]}));
 const privatePhotos=catalogue.albums.map(a=>({
  ...a,images:(a.images||[]).map(p=>({...p,ownerAlbum:a.id,url:'owner:'+a.id+':'+p.number}))
 }));
 const result=join([existing,privatePhotos,[]]);
 const byResult=new Map(result.map(a=>[a.id,new Map(a.images.map(p=>[p.sha256,p]))]));
 const byPublic=new Map();
 for(const a of existing)for(const p of a.images){
  if(!byPublic.has(p.sha256))byPublic.set(p.sha256,[]);
  byPublic.get(p.sha256).push({album:a.id,p});
 }
 let exactCross=0,recovered=0,wrong=0;
 for(const a of privatePhotos)for(const p of a.images){
  const matches=(byPublic.get(p.sha256)||[]).filter(v=>v.p.bytes===p.bytes&&v.p.width===p.width&&v.p.height===p.height);
  if(!matches.length||matches.some(v=>v.album===a.id))continue;
  exactCross++;
  const actual=byResult.get(a.id)?.get(p.sha256);
  assert(actual,{model,album:a.id,sha:p.sha256,why:'missing original'});
  if(actual.shaPinnedLocalCopy===true && actual.url?.startsWith('stored-albums/')){
   recovered++;assert.equal(actual.ownerAlbum,undefined);
   assert(matches.some(v=>v.p.url===actual.url),'real file SHA copy not from local index');
  }else wrong++;
 }
 assert.equal(wrong,0,model+' cross-album SHA records still going to Render');
 assert(recovered>0,'real persisted fallback not exercised for '+model);
 console.log('CROSS_ALBUM_EXISTING_PHOTOS_RESCUED',JSON.stringify({model,exact_cross_album_matches:exactCross,recovered,wrong,metadata_only:true}));
}
const mGroup={};
vm.runInNewContext(fs.readFileSync(path.join(ROOT,'mimmi-gallery/album-grouping.js'),'utf8'),{window:mGroup,URL,Set,Map,Number});
const fakeFrom={id:'old-edition',images:[{...img('physically-saved'),originalAlbumId:'physically-saved',shaPinnedLocalCopy:true}]};
const fakeTo={id:'unified-edition',images:Array.from({length:32},(_,i)=>img('unified-edition',('e'+String(i).padStart(63,'0')).slice(0,64),10000,600,900,i+1))};
const grouped=mGroup.MimmiAlbumGrouping.combine([fakeFrom,fakeTo],{'old-edition':'unified-edition'});
assert.equal(grouped.albums[0].images.find(p=>p.shaPinnedLocalCopy)?.originalAlbumId,'physically-saved','alias merge must not corrupt the physical folder');
console.log('CROSS_ALBUM_STATIC_COPY_AND_ALIAS_CONTRACT_PASS');
