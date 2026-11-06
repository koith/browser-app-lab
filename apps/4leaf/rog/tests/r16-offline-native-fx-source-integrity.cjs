'use strict';
/* R16: independent provenance and PWA-cache audit for recovered 2002 OBS
 * effects. Source bytes VERIFIED; original camera/event timing UNVERIFIED.
 * This does NOT treat a source PNG as evidence of an authentic 3D mesh.
 */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const load=name=>fs.readFileSync(path.join(root,name),'utf8');
const meta=JSON.parse(load('app-version.json'));
assert.equal(meta.version,'0.86.0-beta.69');
assert.equal(meta.pwaCache,'4leaf-revival-pwa-v156');
assert.match(load('index.html'),/name="leaf-revival-version" content="0\.86\.0-beta\.69"/);
const manifestText=load('original/OBS/duel-effects/manifest.js');
const prefix='window.ORIGINAL_LEAF_DUEL_EFFECTS=';
assert.ok(manifestText.includes(prefix),'missing source archive manifest');
const manifest=JSON.parse(manifestText.split(prefix)[1].trim().replace(/;\s*$/,''));
const worker=load('sw.js');
const install=worker.indexOf("self.addEventListener('install'");
assert.ok(install>0,'no service worker install');
const realm={};
vm.runInNewContext(worker.slice(0,install)+'\nthis.__CORE=CORE;this.__REVISION=REVISION;',realm);
assert.equal(realm.__REVISION,meta.pwaCache);
const cached=new Set(realm.__CORE);
const reviewed=[
 ['1096',3],['1097',5],['1098',7],['1099',12],
 ['1101',5],['1102',5],['1112',31],['1114',29],['1118',32]
];
const actual=[];
for(const [id,count] of reviewed){
 const key='obs.pak/'+id+'.obs';
 const source=manifest[key];
 assert.ok(source,'original member missing: '+key);
 assert.equal(source.status,'SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED');
 assert.equal(source.frames.length,count,'source frame table changed: '+id);
 for(const [index,row] of source.frames.entries()){
  const expected='./original/OBS/duel-effects/obs-'+id+'-'+String(index).padStart(3,'0')+'.png';
  assert.equal(row.url,expected,'source frame path not canonical');
  assert.ok(cached.has(expected),'not precached for first offline duel: '+expected);
  const bytes=fs.readFileSync(path.join(root,expected.slice(2)));
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a','not original PNG');
  assert.equal(bytes.readUInt32BE(16),row.width);
  assert.equal(bytes.readUInt32BE(20),row.height);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),row.sha256,
   'cached art is NOT the independently verified original source frame');
  actual.push(expected);
 }
}
assert.equal(actual.length,129);
assert.equal(new Set(actual).size,129);
for(const file of [
 './original/OBS/duel-effects/manifest.js',
 './native-duel-effects.js',
 './native-duel-effects.css'
])assert.ok(cached.has(file),'offline native renderer missing '+file);
const smoke=load('tests/native-offline-cache.cjs');
assert.ok(smoke.includes('NATIVE_DUEL_FX')||smoke.includes('nativeOfflineFx'),
 'offline browser test must decode original native effect images without network');
console.log('R16_NATIVE_FX_COLD_OFFLINE_MANIFEST_PASS',JSON.stringify({
 version:meta.version,cache:meta.pwaCache,members:reviewed.length,
 png:actual.length,immutableSourceHashes:actual.length,archiveMembers:Object.keys(manifest).length,
 cachedSourceEffectFrames:reviewed.map(([id,frames])=>({id,frames}))
}));
