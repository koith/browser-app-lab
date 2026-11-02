'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const source=model=>fs.readFileSync(path.join(ROOT,'apps',model+'-gallery','saved-photo-union.js'),'utf8');
const sandbox={window:{}};
vm.runInNewContext(source('mimmi'),sandbox,{filename:'saved-photo-union.js'});
const join=sandbox.window.SavedGalleryPhotoUnion.join;
assert.equal(source('mimmi'),source('yui'),'Mimmi/Yui must share same verified merge algorithm');

function expectedSHA(groups){
 const works=new Map();
 for(const albums of groups)for(const a of albums){
  if(!works.has(a.id))works.set(a.id,new Set());
  for(const p of a.images||[])works.get(a.id).add(p.sha256);
 }
 return works;
}
function indexed(model){
 const d=path.join(ROOT,'apps',model+'-gallery');
 const local=JSON.parse(fs.readFileSync(path.join(d,'stored-albums.json'))).albums
  .map(a=>({...a,images:a.images.map((p,i)=>({...p,
   number:Number.isInteger(p.number)&&p.number>0?p.number:i+1}))}));
 const owner=JSON.parse(fs.readFileSync(path.join(d,'owner-index.json'))).albums
  .map(a=>({...a,images:a.images.map(p=>({...p,url:'owner:'+a.id+':'+p.number,
    ownerAlbum:a.id}))}));
 return [local,owner];
}
for(const model of ['mimmi','yui']){
 const input=indexed(model);
 const before=expectedSHA(input);
 const joined=join(input);
 const after=new Map(joined.map(a=>[a.id,a]));
 for(const [album,set] of before){
  const work=after.get(album);
  assert.ok(work,'work removed: '+model+'/'+album);
  assert.equal(work.images.length,set.size,'SHA row lost/duplicated: '+model+'/'+album);
  assert.equal(new Set(work.images.map(p=>p.sha256)).size,set.size);
  assert.equal(new Set(work.images.map(p=>p.number)).size,set.size,'display position collision: '+model+'/'+album);
  for(const p of work.images){
   assert.ok(Number.isSafeInteger(p.number)&&p.number>0);
   if(p.ownerAlbum){
    assert.equal(p.url,'owner:'+p.ownerAlbum+':'+p.storageNumber,'real storage route changed');
   }
   if(p.vaultAlbum)
    assert.equal(p.url,'vault:'+p.vaultModel+':'+p.vaultAlbum+':'+p.storageNumber);
  }
 }
 const photoCount=joined.reduce((n,a)=>n+a.images.length,0);
 console.log('GALLERY_SHA_UNION_ALL_SAVED_ORIGINALS_PRESERVED',model,
   'works',joined.length,'distinctSHA',photoCount);
}
{
 const p=(number,sha,route)=>({number,sha256:sha.repeat(64),bytes:100000,
   url:route});
 const local=p(1,'a','stored-albums/work/1.jpg');
 const remote={...p(1,'b','owner:work:1'),ownerAlbum:'work'};
 const idem={...p(2,'a','owner:work:2'),ownerAlbum:'work'};
 const first=join([[{id:'work',images:[local]}],[{id:'work',images:[remote,idem]}]]);
 const merged=first[0].images;
 assert.equal(merged.length,2,'one SHA repeated twice must not become new photograph');
 assert.equal(new Set(merged.map(p=>p.number)).size,2);
 assert.equal(merged.find(p=>p.sha256==='b'.repeat(64)).storageNumber,1);
 assert.equal(merged.find(p=>p.sha256==='a'.repeat(64)).ownerAlbum,'work',
  'exact-SHA local copy must use independently stored owner original');
 assert.equal(merged.find(p=>p.sha256==='a'.repeat(64)).storageNumber,2);
 const second=join([[{id:'work',images:merged}],[{id:'work',images:merged}]]);
 assert.equal(second[0].images.length,2,'repeat merge must be idempotent');
}
console.log('GALLERY_NUMBER_COLLISION_EXACT_SHA_STORAGE_ROUTING_PASS');
