'use strict';
/* ACT-02: original 2002 source-native 640-stride scanline X and per-frame
 * signed OBS origin contract. This audits real recovered PNG bytes rather
 * than inferred centered sprite positions or synthetic pixel fixtures.
 * It does NOT certify the unavailable 3D MVE foot pivot or EXE action table.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const load=p=>fs.readFileSync(path.join(root,p),'utf8');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const sandbox={window:{}};
vm.runInNewContext(load('original/OBS/action-full/manifest.js'),sandbox);
const members=sandbox.window.ORIGINAL_LEAF_FULL_ACTION_FRAMES;
const provenance=JSON.parse(load('original/OBS/action-full/provenance.json'));
const archived=JSON.parse(load('docs/evidence/source-maps/actor-frame-audit.json'));
const actor=load('genesis-chessman-actors.js');
assert.equal(Object.keys(members).length,45,'exactly 45 native 37-frame source actors');
assert.equal(provenance.actorCount,45);
assert.equal(provenance.originalExeActionTableDecoded,false,
 'never invent original EXE frame action mapping');
const frameIndexes=[0,10,18,25];
let verified=0,nonCentered=0,minX=Infinity,maxX=-Infinity,opaquePngs=0;
const samples=[];
for(const [sourceKey,member] of Object.entries(members)){
 const original=provenance.members[sourceKey];
 assert.ok(original,'no raw source member for '+sourceKey);
 assert.equal(original.name,member.originalMember,'matching original member');
 assert.equal(original.sourceSHA256,member.sourceSHA256,'authentic PAK member SHA');
 assert.equal(original.sourceFrameCount,37);
 assert.equal(member.frames.length,37);
 const reference=Object.values(archived.cards).find(x=>
  x.obsPakMember===member.originalMember&&x.bodySource==='action-full');
 assert.ok(reference,'independently published actor-frame source audit missing '+sourceKey);
 assert.equal(reference.memberSHA256,member.sourceSHA256);
 for(const i of frameIndexes){
  const frame=member.frames[i];
  const audited=reference.frames.find(x=>x.index===i);
  assert.ok(audited,'source sampled frame '+sourceKey+'/'+i);
  assert.equal(frame.index,i);
  for(const field of ['sha256','width','height','originX','originY'])
   assert.equal(frame[field],audited[field],sourceKey+'/'+i+'/'+field);
  assert.equal(frame.url,audited.file);
  assert.match(frame.sha256,/^[a-f0-9]{64}$/);
  assert.ok(Number.isSafeInteger(frame.originX)&&Number.isSafeInteger(frame.originY));
  assert.ok(frame.width>0&&frame.height>0);
  const file=path.join(root,frame.url.slice(2));
  const bytes=fs.readFileSync(file);
  assert.deepEqual([...bytes.subarray(0,8)],[137,80,78,71,13,10,26,10],
   'source image is a real PNG, not an inferred wrapper');
  assert.equal(bytes.readUInt32BE(16),frame.width);
  assert.equal(bytes.readUInt32BE(20),frame.height);
  assert.equal(sha(bytes),frame.sha256,
   'actual source OBS pixels must match authenticated archive');
  opaquePngs++;
  // A centered WEB proxy sets X from half the PNG width. Genuine OBS
  // native signed X is not globally centered; audit that relationship.
  if(frame.originX!==-Math.round(frame.width/2))nonCentered++;
  minX=Math.min(minX,frame.originX);maxX=Math.max(maxX,frame.originX);
  verified++;
  if(samples.length<5)samples.push({sourceKey,index:i,
   x:frame.originX,y:frame.originY,dimensions:[frame.width,frame.height]});
 }
}
assert.equal(verified,180);
assert.equal(opaquePngs,180);
assert.ok(nonCentered>=130,'native source X must not be rewritten as WEB-centered art');
assert.ok(minX<0&&maxX>0,'source preserves negative and positive signed origins');
assert.match(actor,/pawn\.dataset\.sourceFrameNativeOrigin=frame\.originX\+'[,]'\+frame\.originY/,
 'live game exposes true original frame signed origins');
assert.ok(actor.includes("const sourceFoot=(frame.originY+frame.height)"),
 'original frame Y+height drives relative foot motion, not guessed center');
assert.ok(actor.includes("Number(frame.originX)||0"),
 'actual rendered OBS left anchor consumes source originX');
console.log('ACT-02 VERIFIED 45 ORIGINAL SOURCE OBS NATIVE XY PASS',JSON.stringify({
 sourceMembers:Object.keys(members).length,sampledFrames:verified,
 actualPngSha256Verified:opaquePngs,notCentered:nonCentered,
 minX,maxX,samples,
 historical3DAnchor:'UNVERIFIED (tracked separately in BRD-01/ACT-04)',
 actionTable:'UNVERIFIED (tracked separately in ACT-03)'
}));
