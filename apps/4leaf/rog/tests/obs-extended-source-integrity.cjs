'use strict';
// SHA1-gated 2002 source extraction: audit every quarantined frame in Git,
// rather than relying only on an Actions success status. No original EXE runs.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const summary=JSON.parse(read('docs/evidence/obs-trailers/summary.json'));
assert.equal(summary.installerSHA1,'86526d89679ae39b85fe9808da97ad871b7888d9');
assert.equal(summary.members,245);
assert.equal(summary.chrRecords,119);
assert.equal(summary.claims.actionTableDecoded,false);
const expect={ 'recovered-wide':{members:4,frames:68,key:'recoveredWide'},
 embedded:{members:66,frames:923,key:'embedded'},
 'obs23-actors':{members:45,frames:1792,key:'obs23Actors'} };
let total=0;
for(const [folder,expected] of Object.entries(expect)){
 const prefix='original/OBS/'+folder+'/';
 const script=read(prefix+'manifest.js').toString('utf8');
 const marker=script.indexOf('={');
 assert.ok(marker>0,'original manifest missing '+folder);
 const map=JSON.parse(script.slice(marker+1,script.lastIndexOf(';')));
 assert.equal(Object.keys(map).length,expected.members,folder+' original members');
 let n=0;
 const expectedNames=new Set();
 for(const [member,record] of Object.entries(map)){
  assert.ok(record.frames?.length,'no source frames '+member);
  if(folder!=='recovered-wide')assert.match(record.status||'QUARANTINED',/QUARANTINED/);
  for(const frame of record.frames){
   if(!frame.url)continue; // original empty record: no invented pixel data
   assert.ok(frame.url.startsWith('./'+prefix),member+' non-source frame path');
   const relative=frame.url.slice(2);
   const name=path.basename(relative);
   assert.ok(!expectedNames.has(name),'duplicate PNG filename '+name);
   expectedNames.add(name);
   const bytes=read(relative);
   assert.deepEqual([...bytes.subarray(0,8)],[137,80,78,71,13,10,26,10],
    member+' native PNG signature');
   assert.equal(bytes.readUInt32BE(16),frame.width,member+' native X');
   assert.equal(bytes.readUInt32BE(20),frame.height,member+' native Y');
   assert.equal(hash(bytes),frame.sha256,member+' original frame SHA256');
   n++;
  }
 }
 const disk=new Set(fs.readdirSync(path.join(root,prefix)).filter(f=>f.endsWith('.png')));
 assert.equal(disk.size,n,folder+' unexpected or missing source PNG');
 for(const name of disk)assert.ok(expectedNames.has(name),'untracked source PNG '+name);
 assert.equal(n,expected.frames,folder+' verified original frames');
 assert.equal(summary.exportedFrames[expected.key],n,folder+' cross-check source census');
 total+=n;
}
assert.equal(total,2783);
const chr=JSON.parse(read('docs/evidence/obs-trailers/chr.json'));
assert.equal(Object.keys(chr.records).length,119,'original CHR records');
const trailer=JSON.parse(read('docs/evidence/obs-trailers/trailers.json'));
assert.equal(Object.keys(trailer).length,245,'original member trailers');
console.log('4LEAF EXTENDED OBS PIXEL SHA256 PASS',JSON.stringify({
 sourceSHA1:summary.installerSHA1,pixels:total,wide:68,embedded:923,
 obs23:1792,chrRecords:119,actionTableDecoded:false}));
