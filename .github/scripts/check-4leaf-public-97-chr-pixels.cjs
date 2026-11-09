'use strict';
/* Original image byte integrity, public Pages:
 * Every source-assigned CHR body must retain its own source sprite pixels.
 * This audits three distant native frames per body against ORIGINAL manifest
 * SHA256 locally AND on the actual published GitHub Pages, without rendering
 * a fake frame or copying a different card's body. It does not infer the
 * historical EXE's action roles, timing or 3D camera. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../apps/4leaf/rog');
const base=process.env.FOURLEAF_TEST_URL||
 'https://koith.github.io/browser-app-lab/apps/4leaf/rog/';
const digest=data=>crypto.createHash('sha256').update(data).digest('hex');
const manifestPaths=[
 'original/OBS/action-full/manifest.js',
 'original/OBS/action-full-ext/manifest.js',
 'original/OBS/obs23-actors/manifest.js',
 'original/OBS/referenced/chr-bodies-manifest.js',
 'chr-body-source-map.js'
];
const context=vm.createContext({window:{}});
for(const filename of manifestPaths){
 vm.runInContext(fs.readFileSync(path.join(root,filename),'utf8'),
  context,{filename});
}
const api=context.window.__LEAF_CHR_BODY_MAP__;
assert.ok(api,'Actual source CHR resolver must be registered');
const cards=Object.keys(api.cards).sort();
assert.equal(cards.length,98,'Original CardData CHR inventory size');
assert.equal(api.resolve('0156'),null,'Never substitute absent OBS2/1222.obs');
const records=[],samples=[];
for(const card of cards){
 const original=api.lookup(card),body=api.resolve(card);
 if(card==='0156'){records.push({card,missing:true,member:'OBS2.pak/1222.obs'});continue}
 assert.ok(original&&!original.missing&&body,'Missing authentic source body: '+card);
 assert.ok(body.originalMember===original.originalMember||
  (original.pak==='OBS'&&body.originalMember===original.member+'.obs'),
  'Cross-body reuse: '+card+' got '+body.originalMember+
  ' expected '+original.originalMember);
 const frames=body.frames;
 assert.ok(Array.isArray(frames)&&frames.length>=3,'Missing source frame sequence: '+card);
 const targets=[frames[0],frames[Math.floor(frames.length/2)],frames.at(-1)];
 for(const frame of targets){
  assert.match(frame.sha256,/^[a-f0-9]{64}$/);
  assert.ok(frame.url.startsWith('./original/OBS/')&&frame.url.endsWith('.png'));
  const relative=frame.url.slice(2);
  const local=fs.readFileSync(path.join(root,relative));
  assert.equal(digest(local),frame.sha256,'Local source pixel mismatch '+card+' '+relative);
  assert.equal(local.subarray(0,8).toString('hex'),'89504e470d0a1a0a',
   'Invalid PNG signature: '+relative);
  samples.push({card,member:original.originalMember,relative,
   sha256:frame.sha256,width:frame.width,height:frame.height});
 }
 records.push({card,originalMember:body.originalMember,frames:frames.length,
  recoveredOriginal20261103:body.recoveredOriginal20261103===true});
}
assert.equal(records.filter(x=>!x.missing).length,97);
const report={source:'ARCHIVED_NATIVE_OBS_AND_2002_CHR_CARD_MAPPING',
 evidence:'ORIGINAL_PNG_BYTES_SHA256_PUBLIC_MATCH',
 version:JSON.parse(fs.readFileSync(path.join(root,'app-version.json'),'utf8')).version,
 testedCards:records.length,recoveredCards:97,missing:['0156=OBS2.pak/1222.obs'],
 frameSamples:samples.length,
 failures:[],data:[],historicalPoseRolesVerified:false,
 realIphoneHardwareVerified:false
};
const concurrency=10;
let pos=0;
async function verify(item){
 const url=new URL(item.relative,base).href+'?native_sha_audit='+Date.now();
 let last;
 for(let attempt=0;attempt<3;attempt++){
  try{
   const response=await fetch(url,{
    cache:'no-store',headers:{'Cache-Control':'no-cache'},
    signal:AbortSignal.timeout(25000)
   });
   assert.equal(response.status,200,item.relative+' returned '+response.status);
   const bytes=Buffer.from(await response.arrayBuffer());
   assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
   const actual=digest(bytes);
   assert.equal(actual,item.sha256,'Published PNG pixels differ: '+item.relative);
   return {card:item.card,member:item.member,originalFrame:item.relative,
    sha256:item.sha256,width:item.width,height:item.height};
  }catch(err){
   last=err;
   if(attempt<2)await new Promise(resolve=>setTimeout(resolve,700*(attempt+1)));
  }
 }
 throw last;
}
(async()=>{
 const jobs=Array.from({length:concurrency},async()=>{
  while(pos<samples.length){
   const sample=samples[pos++];
   try{report.data.push(await verify(sample))}
   catch(error){report.failures.push({card:sample.card,frame:sample.relative,
    message:String(error.message||error)})}
  }
 });
 await Promise.all(jobs);
 report.checkedFrames=report.data.length;
 report.checkedCards=new Set(report.data.map(x=>x.card)).size;
 report.data.sort((a,b)=>a.card.localeCompare(b.card)||a.originalFrame.localeCompare(b.originalFrame));
 fs.writeFileSync('4leaf-public-97-source-pixel-audit.json',
  JSON.stringify(report,null,2)+'\n');
 console.log('4LEAF_PUBLISHED_97_ORIGINAL_PNG_SOURCE_SHA_AUDIT',JSON.stringify({
  cards:report.checkedCards,frames:report.checkedFrames,failures:report.failures.slice(0,6),
  missing:report.missing,version:report.version}));
 assert.deepEqual(report.failures,[],'Every sampled displayed source must be byte-perfect');
 assert.equal(report.checkedCards,97);
 assert.equal(report.checkedFrames,samples.length);
 console.log('LIVE_PUBLIC_97_ORIGINAL_CHR_PNG_SHA256_PASS');
})().catch(error=>{
 console.error('LIVE_PUBLIC_97_ORIGINAL_CHR_PNG_SHA256_FAIL',error.stack||error);
 process.exitCode=1;
});
