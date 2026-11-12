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
 assert.equal(merged.find(p=>p.sha256==='a'.repeat(64)).url,local.url,
  'byte-identical local original must remain the first-choice offline route');
 assert.equal(merged.find(p=>p.sha256==='a'.repeat(64)).ownerAlbum,undefined,
  'public local saved SHA must not be overwritten by sleeping gateway');
 const second=join([[{id:'work',images:merged}],[{id:'work',images:merged}]]);
 assert.equal(second[0].images.length,2,'repeat merge must be idempotent');
}
{
 const size=5000;
 const local=[],owner=[];
 for(let number=1;number<=size;number++){
  const sha=number.toString(16).padStart(64,'0');
  local.push({number,sha256:sha,bytes:100000,
    url:'stored-albums/heavy/'+number+'.jpg'});
  owner.push({number,sha256:sha,bytes:100000,
    url:'owner:heavy:'+number,ownerAlbum:'heavy'});
 }
 const start=performance.now();
 const merged=join([[{id:'heavy',images:local}],[{id:'heavy',images:owner}]]);
 const elapsed=Math.round(performance.now()-start);
 assert.equal(merged.length,1);
 assert.equal(merged[0].images.length,size,'large duplicate corpus must not lose or double-count photos');
 assert.ok(merged[0].images.every((p,i)=>p.url==='stored-albums/heavy/'+(i+1)+'.jpg' &&
   !p.ownerAlbum),'byte-identical Pages originals must win for every image');
 console.log('GALLERY_SHA_UNION_5000_PHOTO_PAGES_PRIORITY_PASS','elapsed_ms',elapsed);
}

{
 // A genuine Janus gallery has physically committed public samples
 // and owner-backed catalog records for the same album; never make an
 // existing local SHA depend on Render to display.
 const albums=indexed('mimmi');
 const local=albums[0].find(a=>a.id==='djawa-janus-scary-lantern-night');
 const owner=albums[1].find(a=>a.id==='djawa-janus-scary-lantern-night');
 assert.ok(local&&owner&&local.images.length>=7&&owner.images.length>=8);
 const copied=new Set(local.images.map(p=>p.sha256));
 const merged=join(albums).find(a=>a.id===local.id);
 for(const photo of merged.images){
   if(!copied.has(photo.sha256))continue;
   const prior=local.images.find(p=>p.sha256===photo.sha256);
   assert.equal(photo.url,prior.url,'Janus local saved original must survive union');
   assert.ok(fs.existsSync(path.join(ROOT,'apps','mimmi-gallery',photo.url)),
     'Janus saved original not present in current Pages source');
 }
 console.log('GALLERY_JANUS_SHA_IDENTICAL_LOCAL_ORIGINALS_SURVIVE_PASS');
}


{
 // Real regression: legacy v04 public previews are the exact same ten SHA
 // originals that the Teddy Bear owner index already provides, but v04 also
 // has an independently SHA-pinned owner original that MUST remain visible.
 const yui=indexed('yui');
 const aliases=JSON.parse(fs.readFileSync(path.join(ROOT,'apps/yui-gallery/album-aliases.json'))).aliases;
 const ownerV04=yui[1].find(a=>a.id==='v04');
 const ownerTeddy=yui[1].find(a=>a.id==='teddy-bear97');
 const localV04=yui[0].find(a=>a.id==='v04');
 assert.equal(aliases.v04,'teddy-bear97');
 assert.ok(ownerV04?.images.length>=1&&ownerTeddy?.images.length>=10&&localV04?.images.length>=10);
 const targetProofs=new Map(ownerTeddy.images.map(p=>[p.sha256,p]));
 const repeated=localV04.images.filter(p=>{
  const proof=targetProofs.get(p.sha256);
  return proof&&proof.bytes===p.bytes&&proof.width===p.width&&proof.height===p.height;
 });
 assert.equal(repeated.length,10,'the ten actual previews must match real canonical owner metadata');
 const merged=join(yui);
 const beforeTotal=merged.reduce((n,a)=>n+a.images.length,0);
 const after=sandbox.window.SavedGalleryPhotoUnion.dedupeAliasedPhysicalCopies(merged,aliases);
 const v04=after.find(a=>a.id==='v04'),teddy=after.find(a=>a.id==='teddy-bear97');
 assert.ok(v04&&teddy);
 assert.equal(v04.images.length,ownerV04.images.length,'no wrong Teddy Bear duplicate photos inside v04');
 assert.equal(v04.images[0].sha256,ownerV04.images[0].sha256,'exact owner original not hidden by legacy local previews');
 assert.equal(v04.images[0].number,1,'physical owner display number restored');
 assert.equal(v04.images[0].storageNumber,1,'actual owner route still points to original #1');
 assert.ok(teddy.images.every(p=>targetProofs.has(p.sha256)),'canonical album contains its owner originals');
 assert.equal(teddy.images.length,ownerTeddy.images.length,'canonical original photos stay viewable');
 assert.ok(teddy.images.some(p=>p.shaPinnedLocalCopy&&p.originalAlbumId==='v04'),
  'committed original local bytes remain reachable in the canonical album');
 assert.equal(after.reduce((n,a)=>n+a.images.length,0),beforeTotal-repeated.length,
  'only provably duplicated alias rows removed from viewer, not files');
 assert.equal(sandbox.window.SavedGalleryPhotoUnion.dedupeAliasedPhysicalCopies(after,aliases),after,
  'alias correction should be idempotent');
 console.log('YUI_V04_REAL_SHA_OWNER_ALBUM_EXACT_COPY_REASSIGN_PASS',JSON.stringify({
  aliased_local_copies_removed:repeated.length,owner_originals_preserved:v04.images.length,
  canonical_originals_preserved:teddy.images.length
 }));
}
{
 // Do not erase independent local/owner files or mismatched byte/dimension
 // records even when an alias name happens to match.
 const sha=x=>x.repeat(64);
 const row=(n,x,bytes,url)=>({number:n,sha256:sha(x),bytes,width:640,height:960,url});
 const owner={...row(1,'d',120,'owner:alias:1'),ownerAlbum:'alias',storageNumber:1};
 const alias={id:'alias',images:[row(1,'a',100,'stored-albums/alias/a.jpg'),
  row(2,'b',101,'stored-albums/alias/b.jpg'),owner]};
 const target={id:'target',images:[{...row(1,'a',100,'owner:target:1'),ownerAlbum:'target'},
  {...row(2,'b',999,'owner:target:2'),ownerAlbum:'target'}]};
 const raw=join([[alias],[target]]);
 const filtered=sandbox.window.SavedGalleryPhotoUnion.dedupeAliasedPhysicalCopies(raw,{alias:'target'});
 const separate=filtered.find(a=>a.id==='alias');
 assert.equal(separate.images.length,2,'different bytes and true owner SHA must not disappear');
 assert.ok(separate.images.some(p=>p.sha256===sha('b')));
 assert.ok(separate.images.some(p=>p.sha256===sha('d')&&p.ownerAlbum==='alias'));
 console.log('YUI_ALIAS_DEDUPE_PROTECTS_DISTINCT_STORAGE_AND_OWNER_PASS');
}

console.log('GALLERY_NUMBER_COLLISION_EXACT_SHA_STORAGE_ROUTING_PASS');
