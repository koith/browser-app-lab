'use strict';
/* Independently verify genuine 2002 Dice/IMG.pak ROLL source frame PNGs
 * against the sha256 preserved by the authenticated cabinet extraction.
 * Does NOT confuse eventRoll1 (UI button) with D4/D6 3D die meshes.
 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const folder=path.join(root,'original/SourceSPR');
const report=JSON.parse(fs.readFileSync(path.join(folder,'manifest.json'),'utf8'));
assert.equal(report.source,'Dice/IMG.pak');
assert.equal(report.videoStride,640);
const sourceNames=['roll.spr','eventRoll1.spr'];
const frameCounts=[4,16];
const expected={};
let checked=0,bytes=0;
for(let k=0;k<sourceNames.length;k++){
 const name=sourceNames[k],entry=report.spriteAnimations[name];
 assert.ok(entry,'missing original source SPR member '+name);
 assert.equal(entry.member,name);
 assert.equal(entry.frameCount,frameCounts[k]);
 assert.equal(entry.frames.length,frameCounts[k]);
 assert.match(entry.sourceSHA256,/^[a-f0-9]{64}$/);
 const seen=new Set();
 for(let i=0;i<frameCounts[k];i++){
  const frame=entry.frames[i];
  assert.equal(frame.index,i,'native sequential source frame index');
  assert.ok(!seen.has(frame.url),'repeated source animation URL');
  seen.add(frame.url);
  assert.match(frame.url,new RegExp('^\\./original/SourceSPR/'+
   (k===0?'roll':'eventRoll1')+'-[0-9]{2}\\.png$'));
  const asset=path.resolve(root,frame.url.replace(/^\.\//,''));
  assert.ok(asset.startsWith(folder+path.sep),'source frame path escape');
  assert.ok(fs.existsSync(asset),'original SPR asset missing: '+frame.url);
  const blob=fs.readFileSync(asset);
  assert.equal(blob.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(blob.readUInt32BE(16),frame.width,'original frame width');
  assert.equal(blob.readUInt32BE(20),frame.height,'original frame height');
  assert.equal(crypto.createHash('sha256').update(blob).digest('hex'),frame.sha256,
   'unverified replacement/changed pixel data at '+frame.url);
  assert.ok(Number.isInteger(frame.originX)&&Number.isInteger(frame.originY));
  assert.ok(frame.opaquePixels>100);
  if(k===0){assert.deepEqual([frame.width,frame.height],[158,100])}
  else{assert.ok(frame.width>=69&&frame.width<=91);assert.equal(frame.height,51)}
  checked++;bytes+=blob.length;
 }
 expected[name]=entry.frameCount;
}
assert.equal(checked,20);
const files=fs.readdirSync(folder).filter(x=>x.endsWith('.png'));
assert.equal(files.length,20,'never silently insert fabricated roll frames');
console.log('VERIFIED ORIGINAL IMG SPR SOURCE PNG INTEGRITY '+JSON.stringify({
 originals:sourceNames,sourceFrames:expected,totalFrames:checked,bytes,
 decoding:'2002-original-640-stride-paletted-RLE',roles:{
  'roll.spr':'historic 158x100 UI ROLL sprite (not 3D die)',
  'eventRoll1.spr':'historic 16-frame 69..91x51 ROLL button (not 3D die)'
 }}));
