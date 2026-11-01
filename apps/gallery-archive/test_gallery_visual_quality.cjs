/* Unit checks of ambiguous source quality and publisher branding. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const BASE=path.resolve(__dirname,'..');
for(const model of ['yui','mimmi']){
 const root=path.join(BASE,model+'-gallery');
 const quality=require(path.join(root,'image-quality.js'));
 const publisher=require(path.join(root,'publishers.js'));
 const registry=JSON.parse(fs.readFileSync(path.join(root,'publishers.json'),'utf8'));
 const sample=(width,height,bytes,extra={})=>({width,height,bytes,sha256:'a'.repeat(64),...extra});
 const clean=sample(1200,1800,540000,{source_url:'https://publisher.example/img.jpg'});
 const upscaled=sample(3200,4800,560000,{source_url:'https://cosplay.pixibb.com/watermarked.jpg',sha256:'b'.repeat(64)});
 assert.equal(quality.preferred(upscaled,clean),clean,'Prefer usable clean archival original to PixiBB watermark');
 assert.equal(quality.preferred(clean,upscaled),clean,'Source order must not change quality decision');
 const normal=sample(1400,2000,510000);
 const artificial=sample(3000,4200,520000,{sha256:'c'.repeat(64)});
 assert.equal(quality.preferred(normal,artificial),normal,'Flag pixel-only inflated fake resolution');
 assert.equal(quality.preferred(artificial,normal),normal,'Suspicious upscaled bytes cannot win by dimensions alone');
 const realLarge=sample(3300,4800,3400000,{sha256:'d'.repeat(64)});
 assert.equal(quality.preferred(normal,realLarge),realLarge,'Real higher information density should win');
 const verified=sample(900,1300,240000,{publisher_original_verified:true,sha256:'e'.repeat(64)});
 assert.equal(quality.preferred(upscaled,verified),verified,'Verified publisher original must beat watermark');
 const same={...normal,ownerAlbum:'same-album'};
 assert.equal(quality.preferred(normal,same),same,'SHA-identical owner file wins ties');
 for(const item of registry.publishers){
  const logo=publisher.logo(item);
  if(logo){
   assert.equal(item.logo.verified_official,true,model+' '+item.id);
   assert.ok(['official_publisher_logo','official_site_logo','official_store_logo'].includes(item.logo.asset_role),'Wrong brand identity role: '+item.id);
  }
 }
 if(model==='yui')for(const id of ['sweetbox','bcut','milkybomb']){
  const p=registry.publishers.find(a=>a.id===id);assert.equal(publisher.logo(p),null,'Wrong borrowed mark must not show for '+id);
 }
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.ok(html.includes('image-quality.js?v=1'),model+' loads quality scorer');
 assert.ok(html.includes("ownerPhotoIndex.get(e.target.dataset.owner)"),model+' uses indexed lookup');
 assert.ok(html.includes('requestAnimationFrame(()=>append(end))'),model+' paints details incrementally');
 assert.ok(html.includes('GalleryPhotoQuality.preferred(previous,p)'),model+' actually ranks duplicates');
 console.log('GALLERY_QUALITY_LOGO_FAST_ENTRY_UNIT_PASS',model);
}
