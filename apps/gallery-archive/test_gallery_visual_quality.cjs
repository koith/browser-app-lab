/* Real optical-quality evidence must outrank watermark, size, bytes, origin. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const BASE=path.resolve(__dirname,'..');
const measured=(score)=>({method:'decoded-pixel-v1',confidence:'measured',score});
const paired=(previous,relation)=>({method:'paired-decoded-pixel-v1',confidence:'measured',same_photo_verified:true,compared_to_sha256:previous.sha256,relation});
for(const model of ['yui','mimmi']){
 const root=path.join(BASE,model+'-gallery');
 const quality=require(path.join(root,'image-quality.js'));
 const publisher=require(path.join(root,'publishers.js'));
 const registry=JSON.parse(fs.readFileSync(path.join(root,'publishers.json'),'utf8'));
 const sample=(width,height,bytes,extra={})=>{
  const item={width,height,bytes,sha256:'a'.repeat(64),...extra};
  // Bind synthetic measured evidence to its exact fixture bytes.
  if(item.visual_quality){
   item.visual_quality={...item.visual_quality,
     ...(item.visual_quality.method==='decoded-pixel-v1'
       ?{photo_sha256:item.sha256}
       :{candidate_sha256:item.sha256})};
  }
  return item;
 };
 const watermarked=sample(1600,2400,700000,{sha256:'b'.repeat(64),source_url:'https://cosplay.pixibb.com/watermarked.jpg',visual_quality:measured(90)});
 const blurryClean=sample(2000,3000,1450000,{sha256:'c'.repeat(64),watermark_status:'absent_verified',visual_quality:measured(45)});
 assert.equal(quality.preferred(watermarked,blurryClean),watermarked,'A visibly better watermarked photo must beat blurry clean copy');
 assert.equal(quality.preferred(blurryClean,watermarked),watermarked,'Quality is independent of input order and watermark');
 const cleanSharp=sample(1400,2100,600000,{sha256:'d'.repeat(64),watermark_status:'absent_verified',visual_quality:measured(96)});
 assert.equal(quality.preferred(watermarked,cleanSharp),cleanSharp,'Higher optical quality wins first even at lower dimensions and size');
 const cleanTie=sample(2000,3100,300000,{sha256:'e'.repeat(64),watermark_status:'absent_verified',visual_quality:measured(87)});
 assert.equal(quality.preferred(watermarked,cleanTie),cleanTie,'Verified clean edition wins only when measured quality is comparable');
 assert.equal(quality.preferred(cleanTie,watermarked),cleanTie,'Tie-break is order independent');
 const unknownClean=sample(3200,4800,2500000,{sha256:'f'.repeat(64),watermark_status:'absent_verified'});
 const unknownMarked=sample(850,1100,90000,{sha256:'0'.repeat(64),watermark_status:'present_verified'});
 assert.equal(quality.preferred(unknownMarked,unknownClean),unknownMarked,'No actual quality measurement means preserve, never assume clean is higher quality');
 assert.equal(quality.preferred(unknownClean,unknownMarked),unknownClean,'No megapixel/byte winner when visual quality is unknown');
 const physical=sample(640,960,62000,{sha256:'4'.repeat(64),ownerAlbum:'same-work'});
 const staticPreview=sample(4800,7200,6000000,{sha256:'5'.repeat(64)});
 assert.equal(quality.preferred(staticPreview,physical),physical,'Never lose owner originals because public copy has larger pixel dimensions');
 assert.equal(quality.preferred(physical,staticPreview),physical,'Owner original preservation must be source-order independent');
 const measuredStatic={...staticPreview,visual_quality:{...measured(96),photo_sha256:staticPreview.sha256}};
 const measuredArchive={...physical,visual_quality:{...measured(40),photo_sha256:physical.sha256}};
 assert.equal(quality.preferred(measuredArchive,measuredStatic),measuredStatic,'Clearly superior measured optical quality wins even over owner storage');
 const knownOld=sample(900,1300,135000,{sha256:'1'.repeat(64)});
 const provenBetter=sample(800,1200,120000,{sha256:'2'.repeat(64),watermark_status:'present_verified',visual_quality:paired(knownOld,'higher')});
 assert.equal(quality.preferred(knownOld,provenBetter),provenBetter,'Actual same-photo pixel improvement beats even a watermark');
 const provenWorse=sample(3500,4900,2400000,{sha256:'3'.repeat(64),watermark_status:'absent_verified',visual_quality:paired(knownOld,'lower')});
 assert.equal(quality.preferred(knownOld,provenWorse),knownOld,'Upscaled and watermark-free must not beat optically better original');
 const verifiedTie={...provenWorse,visual_quality:{...paired(knownOld,'comparable'),candidate_sha256:provenWorse.sha256}};
 const comparableClean={...verifiedTie,visual_quality:{...paired(unknownMarked,'comparable'),candidate_sha256:verifiedTie.sha256}};
 assert.equal(quality.preferred(unknownMarked,comparableClean),comparableClean,'Verified clean copy wins a measured visual tie');
 // A quality score copied from another SHA must NOT promote unrelated
 // bytes even if its numerical score looks excellent.
 const prior=sample(800,1200,80000,{sha256:'6'.repeat(64),
   visual_quality:measured(60)});
 const candidate=sample(4800,7200,2500000,{sha256:'7'.repeat(64),
   visual_quality:measured(99),watermark_status:'absent_verified'});
 const stolenScore={...candidate,visual_quality:{
   ...candidate.visual_quality,photo_sha256:prior.sha256}};
 assert.equal(quality.score(stolenScore),null,'measured score must match candidate SHA');
 assert.equal(quality.preferred(prior,stolenScore),prior,
   'stale high quality score must not override byte-matched evidence');
 const forgedPair={...provenBetter,visual_quality:{
   ...provenBetter.visual_quality,candidate_sha256:'8'.repeat(64)}};
 assert.equal(quality.preferred(knownOld,forgedPair),knownOld,
   'paired optical evidence must be tied to the exact candidate file');
 const exact={...knownOld,ownerAlbum:'same-work'};
 assert.equal(quality.preferred(knownOld,exact),exact,'Identical SHA prefers existing first-party archive bytes');
 assert.equal(quality.watermarkStatus({watermark_status:'unknown'}),'unknown','Unknown is not verified watermark-free');
 for(const item of registry.publishers){
  const logo=publisher.logo(item);
  if(logo){
   assert.equal(item.logo.verified_official,true,model+' '+item.id);
   assert.ok(['official_publisher_logo','official_site_logo','official_store_logo'].includes(item.logo.asset_role),'Wrong brand identity role: '+item.id);
  }
 }
 if(model==='yui')for(const id of ['sweetbox','bcut','milkybomb']){
  assert.equal(publisher.logo(registry.publishers.find(a=>a.id===id)),null,'Unverified borrowed mark '+id);
 }
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 const owner=fs.readFileSync(path.join(root,'owner-media.js'),'utf8');
 assert.ok(html.includes('image-quality.js?v=2'),model+' cache-busts quality scorer');
 // A different SHA is a distinct stored file, even when two source catalogs
 // reuse a display number. Optical ranking remains for true replacement
 // decisions inside the authenticated owner-catalog reconciliation.
 assert.ok(html.includes('SavedGalleryPhotoUnion.join([localStored,ownerStored,vaultStored])'),model+' retains SHA-distinct saved photo variants');
 assert.ok(html.includes('src="saved-photo-union.js"'),model+' loads the real stored-photo merge module');
 assert.ok(owner.includes('globalThis.GalleryPhotoQuality?.preferred(old,p)'),model+' avoids megapixel-only async overwrite');
 console.log('GALLERY_OPTICAL_QUALITY_FIRST_WATERMARK_SECOND_PASS',model);
}
