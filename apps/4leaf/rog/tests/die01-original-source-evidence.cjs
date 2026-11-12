'use strict';
/* DIE-01 acceptance: prove source D6=1171 and D4=1223 original
 * 2002 OBS.pak result-face art and extra animation blocks by SHA256.
 * Do not substitute this 2D source for unverified original 2004 MVE mesh. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const sandbox={window:{}};
const txt=p=>fs.readFileSync(path.join(root,p),'utf8');
for(const file of ['original/OBS/ui/manifest.js','original/OBS/dice-blocks/manifest.js'])
 vm.runInNewContext(txt(file),sandbox,{filename:file});
const UI=sandbox.window.ORIGINAL_LEAF_UI_FRAMES;
const BLOCK=sandbox.window.ORIGINAL_LEAF_DICE_BLOCKS;
const table=JSON.parse(txt('docs/evidence/obs-blocks/dice-tables.json'));
const extra=JSON.parse(txt('original/SourceSPRExtra/manifest.json'));
assert.equal(BLOCK.installerSHA1,'86526d89679ae39b85fe9808da97ad871b7888d9');
assert.equal(table.installerSHA1,BLOCK.installerSHA1);
assert.equal(extra.original3DDiceMeshRecovered,false,'2004 original 3D mesh must not be falsely recovered');
let total=0,faceCount=0;const output={};
for(const [member,sides,originalSha,expectedBlocks] of [
 ['1171',6,'d49a20290f5953f5e09d656686e2eb6305bd8c808d1974452381556261d497ff',[28,16,16,6]],
 ['1223',4,'f6f9792b1fdfa6185cfc89cb8e44be4bbdaf69b7d5cc3b792868354fc8a28f89',[22,9,16]]
]){
 const ui=UI[member],source=BLOCK.members[member],action=table.members[member];
 assert.ok(ui&&source&&action,'missing original source die '+member);
 assert.equal(ui.pak,'OBS.pak');
 assert.equal(ui.role,sides===6?'d6':'d4');
 assert.equal(ui.sourceSHA256,originalSha);
 assert.equal(ui.frames.length,ui.declaredFrames);
 assert.equal(ui.frames.length,expectedBlocks[0]);
 assert.equal(source.originalMember,'OBS.pak/'+member+'.obs');
 assert.equal(source.sides,sides);
 assert.deepEqual(Array.from(source.blockFrames),expectedBlocks);
 assert.deepEqual(Array.from(action.blockFrames),expectedBlocks);
 assert.equal(action.animations.length,27);
 const seen=new Set();
 function verifyFrame(f,expectedPrefix){
  assert.equal(typeof f.index,'number');
  assert.ok(f.url.startsWith(expectedPrefix));
  assert.match(f.sha256,/^[a-f0-9]{64}$/);
  const b=fs.readFileSync(path.join(root,f.url.slice(2)));
  assert.equal(b.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(b.readUInt32BE(16),f.width);
  assert.equal(b.readUInt32BE(20),f.height);
  assert.ok(Number.isFinite(f.originX)&&Number.isFinite(f.originY));
  assert.equal(crypto.createHash('sha256').update(b).digest('hex'),f.sha256,
   'original image changed '+f.url);
  assert.ok(!seen.has(f.url),'same source file reused for different frames');
  seen.add(f.url);total++;
 }
 ui.frames.forEach((f,i)=>{
  assert.equal(f.index,i);
  verifyFrame(f,'./original/OBS/ui/'+member+'-');
 });
 let n=0;
 for(const block of source.blocks){
  assert.equal(block.frameCount,block.frames.length);
  assert.ok(block.block>=1);
  block.frames.forEach((f,i)=>{
   assert.equal(f.index,i);
   verifyFrame(f,'./original/OBS/dice-blocks/obs-'+member+'-b'+block.block+'-');
   n++;
  });
 }
 assert.equal(n,expectedBlocks.slice(1).reduce((a,x)=>a+x,0));
 assert.ok(action.animations[12].keys.length>5);
 assert.ok(action.animations[20].keys.length>5);
 // Face indices 0..3/0..5 are SOURCE VERIFIED from decoded D4/D6 pip
 // silhouettes; no asserted original EXE keyframe action semantics.
 assert.deepEqual(ui.frames.slice(0,sides).map(f=>f.index),
  Array.from({length:sides},(_,i)=>i));
 faceCount+=sides;
 output[member]={sides,sourceSha:ui.sourceSHA256,
  sourcePixels:ui.frames.length+source.blocks.reduce((n,b)=>n+b.frames.length,0),
  originalBlocks:expectedBlocks,original2DResultFaces:sides,
  sourceVideoRole:'VERIFIED 2002 2D OBS source face/palette',
  original3D:'MVE native mesh and face normal UNVERIFIED'};
}
assert.equal(faceCount,10,'D4 has four and D6 six actual result faces');
assert.equal(total,113,'all 50 2D face/tumble and 63 extra native OBS blocks verified');
const runtime=txt('dice-fall.js');
assert.ok(runtime.includes('const ORIGINAL_D4_MEMBER_SHA'), 'no original source D4 identity guard');
assert.ok(runtime.includes("const D6_MEMBER='0171'"), 'D6 1171 source fallback identity missing');
assert.ok(runtime.includes('NOT original 2002 MVE geometry/keyframes'),
 'source 2D texture must never be passed off as authentic 3D');
console.log('DIE01_ORIGINAL_D4_D6_SOURCE_EVIDENCE_PASS',
 JSON.stringify({installerSHA1:BLOCK.installerSHA1,totalSourceFrameSHA256:total,sourceFaces:faceCount,
  original3DModel:'UNVERIFIED',dies:output}));
