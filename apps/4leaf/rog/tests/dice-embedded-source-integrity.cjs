'use strict';
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const sandbox={window:{}};vm.runInNewContext(read('original/OBS/embedded/manifest.js'),sandbox);
vm.runInNewContext(read('original/OBS/embedded/dice-selected.js'),sandbox);
const all=sandbox.window.ORIGINAL_LEAF_OBS_EMBEDDED,selected=sandbox.window.ORIGINAL_LEAF_EMBEDDED_DICE;
const expected=[['obs-1171-c0',16],['obs-1171-c1',16],['obs-1171-c2',6],
 ['obs-1223-c0',9],['obs-1223-c1',16]];
assert.deepEqual(Object.keys(selected),expected.map(x=>x[0]),'only 5 specific native dice records exposed');
let count=0;
for(const [id,n] of expected){
 const source=all[id],rec=selected[id];
 assert.equal(rec.originalMember,source.originalMember);
 assert.equal(rec.originalMember,'OBS.pak/'+id.slice(4,8)+'.obs');
 assert.equal(rec.status,'QUARANTINED/role-unknown');
 assert.equal(rec.trailerOffset,source.trailerOffset);
 assert.equal(rec.frames.length,n);
 for(let i=0;i<n;i++){
  const f=rec.frames[i],original=source.frames[i];
  for(const key of ['index','url','sha256','width','height','originX','originY'])
   assert.equal(f[key],original[key],id+' frame '+i+' '+key);
  const bytes=fs.readFileSync(path.join(root,f.url.slice(2)));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),f.sha256);
  count++;
 }
}
assert.equal(count,63);
const html=read('index.html');
const selectedScript='<script src="./original/OBS/embedded/dice-selected.js"></script>';
assert.equal(html.split(selectedScript).length,2,'selected manifest exactly once');
assert.ok(html.indexOf(selectedScript)<html.indexOf('<script src="./dice-fall.js"></script>'));
const sw=read('sw.js'),meta=JSON.parse(read('app-version.json'));
assert.ok(sw.includes("const EMBEDDED_DIE_OFFLINE=") &&
 sw.includes("concat(EMBEDDED_DIE_OFFLINE)"),'all die frames included in offline cache');
assert.ok(sw.includes("const REVISION='"+meta.pwaCache+"'"));
assert.match(meta.version,/^0\\.86\\.0-beta\\.\\d+$/,'source integrity test cannot pin a previous release');
const diceFall=read('dice-fall.js');
assert.ok(diceFall.includes('EMBEDDED_PALETTE_REVIEWED_SHA256=Object.freeze({})'),
 'incorrect per-block palettes must not be approved by default');
assert.ok(diceFall.includes('const embedded=playableEmbeddedDice(sides)'),
 'live roll must use exact SHA256 allowlisted corrected frames only');
console.log('4LEAF NATIVE EMBEDDED DICE SOURCE PROVENANCE PASS',
 JSON.stringify({sourcePixels:count,d6:38,d4:25,installerSHA1:'86526d89679ae39b85fe9808da97ad871b7888d9',
 role:'source-bytes-VERIFIED/sequencing-INFERRED',version:meta.version}));
