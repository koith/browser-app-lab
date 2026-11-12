'use strict';
// Actual stored gallery corpus audit: names, publisher provenance, exact cover
// SHA ownership and the difference between publisher and repost/mirror sites.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const pubKinds=new Set(['creator_public_photographs','official_event_report',
 'public_editorial_photos','public_board_photographs','public_photographer_portfolio']);
for(const model of ['mimmi','yui']){
 const d=path.join(root,model+'-gallery');
 require(path.join(d,'gallery-labels.js'));
 const labels=globalThis[model==='mimmi'?'MimmiLabels':'YuiLabels'];
 const pub=require(path.join(d,'publishers.js'));
 const registry=JSON.parse(fs.readFileSync(path.join(d,'publishers.json'),'utf8'));
 const local=JSON.parse(fs.readFileSync(path.join(d,'stored-albums.json'),'utf8'));
 const owner=JSON.parse(fs.readFileSync(path.join(d,'owner-index.json'),'utf8'));
 const covers=JSON.parse(fs.readFileSync(path.join(d,'album-covers.json'),'utf8')).covers||{};
 const exclusions=JSON.parse(fs.readFileSync(path.join(d,'identity-exclusions.json'),'utf8'));
 const excluded=new Set(exclusions.excluded_album_ids||[]);
 const albums=new Map();
 // Prefer owner titles when the local copy reused a prior album label.
 for(const group of [local.albums||[],owner.albums||[]])for(const a of group){
  if(excluded.has(a.id))continue;
  const prev=albums.get(a.id);
  albums.set(a.id,{...(prev||{}),...a,images:[...(prev?.images||[]),...(a.images||[])]});
 }
 const summaries={},unknown=[],risk=[],invalidCovers=[],missingCovers=[];
 for(const album of albums.values()){
  if(!album.images.length)continue;
  const label=labels.describe(album), key=pub.key(album,registry,labels.describe);
  summaries[key]=(summaries[key]||0)+1;
  if(key==='unknown')unknown.push({id:album.id,title:album.title,publisher:label.publisher,
   explicit:album.publisher||'',source:album.source||'',site:album.site||''});
  if(!String(album.title||'').trim())risk.push({id:album.id,why:'title_blank'});
  if(label.publisher==='미확인' && key!=='unknown' && key!=='public')
   risk.push({id:album.id,why:'unrecognized_display_publisher'});
  if(!covers[album.id])missingCovers.push({id:album.id,local:(local.albums||[]).some(a=>a.id===album.id),
   owner:(owner.albums||[]).some(a=>a.id===album.id)});
 }
 for(const [id,cover] of Object.entries(covers)){
  const album=albums.get(id);
  if(!album)invalidCovers.push({id,why:'unavailable_or_excluded_album'});
  else if(!album.images.some(p=>p.sha256===cover.sha256))
   invalidCovers.push({id,why:'SHA_does_not_belong_to_real_album',sha:cover.sha256});
  if(!/^[a-f0-9]{64}$/.test(cover.sha256||''))
   invalidCovers.push({id,why:'bad_sha'});
 }
 console.log('G10_SAVED_PUBLISHER_COVER_AUDIT',JSON.stringify({
  model,work_count:albums.size,groups:summaries,unknown_count:unknown.length,
  unknown:unknown.slice(0,50),missing_cover_count:missingCovers.length,
  missingCovers:missingCovers.slice(0,85),invalidCovers,risk:risk.slice(0,40)
 }));
 assert.deepEqual(invalidCovers,[],'Album cover SHA must belong to original saved album');
}
