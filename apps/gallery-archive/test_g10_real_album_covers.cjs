'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
for(const [model,total] of [['mimmi',80],['yui',39]]){
 const root=path.join(ROOT,model+'-gallery');
 const j=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
 const local=j('stored-albums.json'),owner=j('owner-index.json'),
  exclusions=j('identity-exclusions.json'),manifest=j('album-covers.json');
 const excludes=new Set(exclusions.excluded_album_ids||[]);
 const deniedSHA=new Set(exclusions.excluded_image_sha256||[]);
 const localBy=new Map(local.albums.map(a=>[a.id,a]));
 const ownerBy=new Map(owner.albums.map(a=>[a.id,a]));
 const covers=manifest.covers;
 assert.equal(Object.keys(covers).length,total,'all SHA-indexed saved albums need one safe cover');
 let decoded=0,ownerOnly=0,cropped=0,previous=0;
 for(const [id,c] of Object.entries(covers)){
  assert.equal(excludes.has(id),false,'excluded artist/work cannot appear: '+id);
  assert.match(c.sha256,/^[a-f0-9]{64}$/);
  assert.equal(deniedSHA.has(c.sha256),false);
  const l=localBy.get(id),o=ownerBy.get(id);
  assert.ok(l||o,id+' no saved work');
  const owner=(o?.images||[]).find(p=>p.sha256===c.sha256);
  const physical=(l?.images||[]).find(p=>p.sha256===c.sha256);
  assert.ok(owner||physical,model+' '+id+' cover not in its recorded album');
  const p=owner||physical;
  assert.equal(c.width,p.width);
  assert.equal(c.height,p.height);
  assert.ok(Array.isArray(c.position)&&c.position.length===2&&c.position.every(x=>Number.isFinite(x)&&x>=0&&x<=100));
  const method=c.method||'';
  if(method==='owner_index_same_work_sha_only_no_pixel_decode'){
   assert.ok(owner,'remote-only cover must use SHA verified owner index');
   ownerOnly++;
  } else if(method==='sha_verified_same_work_local_no_face_proven'||
            method==='verified_same_work_local_face_and_eye_region'){
   assert.ok(physical,model+' '+id+' local cover cannot refer to gateway-only copy');
   const file=path.join(root,physical.url);
   assert.ok(fs.existsSync(file));
   const digest=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
   assert.equal(digest,c.sha256,model+' '+id+' physical bytes changed');
   decoded++;
  }else previous++;
  if(Array.isArray(c.face)){
   const [x,y,w,h]=c.face;
   assert.ok(x>=0&&y>=0&&w>0&&h>0&&x+w<=c.width+1&&y+h<=c.height+1,
    model+' '+id+' incorrect face/crop coordinates');
   cropped++;
  }else assert.ok(method==='owner_index_same_work_sha_only_no_pixel_decode'||
      method==='sha_verified_same_work_local_no_face_proven'||
      method==='same_album_saved_sha_verified_no_identity_inference',
      model+' '+id+' must not claim a verified face region without decoded pixels');
 }
 if(model==='yui'){
  assert.equal(covers.v04.sha256,'b1bda6fc8a05d70d9f9d9f5cb852a4c8ce19311c220baf381f429ca54dcf4cee',
   'v04 cover must be distinct from Teddy Bear SHA, not old mislabeled preview');
  assert.equal(covers.v04.number,1,'original album v04 photo #1 must be kept');
 }
 if(model==='mimmi'){
  assert.equal(decoded,64,'all 64 local Mimmi works must use committed file bytes');
  assert.equal(ownerOnly,16,'16 owner-only albums must not invent local pixel proof');
  assert.ok(cropped>=20,'20 actual saved-photo face regions must be checked');
 }
 console.log('G10_ALL_REAL_SAVED_WORK_COVERS_PINNED_PASS',model,
  JSON.stringify({total,physical_file_sha_verified:decoded,owner_metadata_only:ownerOnly,
   bounded_face_regions:cropped,existing_curations_preserved:previous}));
}
