'use strict';
// Prevent stale SHA or an excluded/wrong-model source being painted as the
// configured representative image. Data-only QA, no face/identity inference.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
for(const model of ['yui','mimmi']){
 const root=path.resolve(__dirname,'..',model+'-gallery');
 const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
 const covers=read('album-covers.json').covers||{};
 const owner=read('owner-index.json');
 const local=read('stored-albums.json');
 const excluded=read('identity-exclusions.json');
 const deniedIds=new Set([...(excluded.excluded_album_ids||[]),
                          ...(excluded.excluded_source_ids||[])]);
 const deniedSha=new Set(excluded.excluded_image_sha256||[]);
 const albums=[...(owner.albums||[]),...(local.albums||[])];
 let checked=0;
 for(const [id,conf] of Object.entries(covers)){
  assert.equal(deniedIds.has(id),false,'excluded model/work has a cover: '+id);
  assert.match(conf.sha256,/^[a-f0-9]{64}$/,'invalid cover sha '+id);
  assert.equal(deniedSha.has(conf.sha256),false,'excluded photo used as cover: '+id);
  const candidates=albums.filter(a=>a.id===id).flatMap(a=>a.images||[]);
  const matched=candidates.find(p=>p.sha256===conf.sha256);
  assert.ok(matched,model+' '+id+' representative SHA is not a saved image');
  if(Number.isSafeInteger(matched.number))
   assert.equal(conf.number,matched.number,model+' '+id+' wrong photo number');
  assert.equal(conf.width,matched.width,model+' '+id+' wrong photo width');
  assert.equal(conf.height,matched.height,model+' '+id+' wrong photo height');
  assert.ok(Array.isArray(conf.position)&&conf.position.length===2&&
    conf.position.every(n=>Number.isFinite(n)&&n>=0&&n<=100),
    model+' '+id+' invalid crop');
  checked++;
 }
 console.log('GALLERY_CURATED_COVER_SAVED_SHA_AND_EXCLUSION_PASS',model,checked);
}
