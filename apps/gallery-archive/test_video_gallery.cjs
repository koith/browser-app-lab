const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const all=[];
for(const model of ['yui','mimmi']){
 const base=path.join(root,model+'-gallery');
 const index=fs.readFileSync(path.join(base,'index.html'),'utf8');
 const page=fs.readFileSync(path.join(base,'videos.html'),'utf8');
 const data=JSON.parse(fs.readFileSync(path.join(base,'videos.json'),'utf8'));
 assert.equal((index.match(/href="videos\.html"/g)||[]).length,1,'Only one video navigation link: '+model);
 assert.match(page,/aria-label="동영상 목록"/);
 assert.doesNotMatch(page,/youtube-nocookie\.com\/embed/,'no unsolicited YouTube embeds');
 assert.match(page,/replaceChildren\(\)/,'closing player must remove media');
 assert.match(page,/\.playsInline=true/,'iOS inline playback');
 assert.equal(data.schema_version,1);assert.equal(data.model,model);
 assert.ok(Array.isArray(data.videos));
 const ids=new Set();
 for(const item of data.videos){
  assert.ok(!ids.has(item.id),'duplicate video item '+item.id);ids.add(item.id);
  assert.ok(item.title&&item.source_url?.startsWith('https://'));
  assert.ok(['local_mp4','source_only'].includes(item.kind),'only actual stored MP4 or source metadata');
  if(item.kind==='local_mp4'){
   assert.match(item.sha256,/^[0-9a-f]{64}$/);
   assert.equal(item.path,'stored-videos/'+item.sha256+'.mp4');
   assert.ok(fs.existsSync(path.join(base,item.path)),'archived video bytes required');
  }
 }
 const scripts=[...page.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)];
 assert.equal(scripts.length,1,'one inline script');
 new vm.Script(scripts[0][1],{filename:model+'-videos-inline.js'});
 assert.match(index,/<a href="videos\.html" class="mode-toggle"[^>]*>GALLERY<\/a>/,'photos logo GALLERY must toggle into MOVIE');
 assert.match(page,/<a class="mode-toggle" href="\.\/"[^>]*>MOVIE<\/a>/,'movie logo must toggle into GALLERY');
 assert.equal((page.match(/aria-current="page"/g)||[]).length,0,'mode switch must not live beside model nav');
 all.push({model,entries:data.videos.length,playable:data.videos.filter(i=>i.kind==='local_mp4').length,archived:data.videos.filter(i=>i.kind==='local_mp4').length});
}
assert.ok(JSON.parse(fs.readFileSync(path.join(root,'yui-gallery/videos.json'))).videos.some(x=>x.source_url==='https://jjtv.kr/15/154066'));
console.log('GALLERY_VIDEO_OFFLINE_PASS',JSON.stringify(all));
