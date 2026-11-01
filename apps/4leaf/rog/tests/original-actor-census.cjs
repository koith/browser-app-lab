'use strict';
// Source-only 4LEAF actor census verification: no invented animation labels.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'original/OBS/action-full');
const manifest=fs.readFileSync(path.join(dir,'manifest.js'),'utf8');
const marker='window.ORIGINAL_LEAF_FULL_ACTION_FRAMES=';
assert.ok(manifest.includes(marker),'complete original source manifest declaration');
const m=JSON.parse(manifest.split(marker)[1].trim().replace(/;\s*$/,''));
const report=JSON.parse(fs.readFileSync(path.join(dir,'provenance.json'),'utf8'));
const inventory=fs.readFileSync(path.join(root,'original/OBS/animation-extra.js'),'utf8');
const source=JSON.parse(inventory.slice(inventory.indexOf('\n{\n')+1,inventory.lastIndexOf('\n);')));
const verified=Object.entries(source)
 .filter(([,v])=>v.originalAnimationCount===37)
 .map(([id])=>id).sort();
const ids=Object.keys(m).sort();
assert.deepEqual(ids,verified,'source manifest exactly matches SHA-vetted 37-frame OBS actor inventory');
assert.equal(ids.length,45);
assert.equal(report.actorCount,45);
assert.equal(report.sourceInventoryMembers,45);
assert.equal(report.totalFrames,1665);
assert.equal(report.originalExeActionTableDecoded,false);
assert.deepEqual(report.failures,{},'no original source member was silently skipped');
const pngSig=Buffer.from('89504e470d0a1a0a','hex');
let frames=0,byteTotal=0;
for(const id of ids){
 const actor=m[id],sourceActor=source[id],member=actor.originalMember;
 assert.equal(actor.sourcePak,'OBS.pak');
 assert.equal(actor.originalAnimationCount,37);
 assert.equal(actor.sourceSHA256,sourceActor.sourceSHA256);
 assert.equal(actor.frames.length,37);
 assert.equal(report.members[id].sourceSHA256,actor.sourceSHA256);
 const stem=member.replace(/\.obs$/i,'');
 for(let i=0;i<37;i++){
  const f=actor.frames[i];
  assert.equal(f.index,i);
  assert.match(f.sha256,/^[0-9a-f]{64}$/);
  const filename=stem+'-'+String(i).padStart(2,'0')+'.png';
  assert.equal(f.url,'./original/OBS/action-full/'+filename);
  const buf=fs.readFileSync(path.join(dir,filename));
  assert.ok(buf.subarray(0,8).equals(pngSig),filename+' PNG signature');
  assert.equal(buf.readUInt32BE(16),f.width,filename+' native width');
  assert.equal(buf.readUInt32BE(20),f.height,filename+' native height');
  assert.equal(crypto.createHash('sha256').update(buf).digest('hex'),f.sha256,
    filename+' authentic archival pixels');
  assert.ok(Number.isInteger(f.originX)&&Number.isInteger(f.originY),
    filename+' signed original bitmap origin');
  frames++;byteTotal+=buf.length;
 }
}
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.ok(html.includes('src="./original/OBS/action-full/manifest.js"'),
 'load original 45-actor manifest before game render');
const engine=fs.readFileSync(path.join(root,'genesis-chessman-actors.js'),'utf8');
assert.ok(engine.includes('Object.hasOwn(AUDITED_FRONT_SOURCE,id)'),
 'unreviewed original frames cannot be promoted to unsupported action direction');
const sw=fs.readFileSync(path.join(root,'sw.js'),'utf8');
assert.ok(sw.includes('./original/OBS/action-full/manifest.js'),
 'source manifest must survive PWA offline');
console.log('4LEAF ORIGINAL 37-FRAME ACTOR CENSUS PASS',JSON.stringify({
 actors:ids.length,frames,bytes:byteTotal,reviewedDirectionActors:3,
 originalExeActionTableDecoded:false
}));
