'use strict';
/* End-to-end source inventory gate: CHR +260 98 cards, no card-index aliases.
 * Manifest SHA256 and member filename are checked before any actor loads.
 */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const sandbox={window:{}};
const load=p=>vm.runInNewContext(fs.readFileSync(path.join(root,p),'utf8'),sandbox,{filename:p});
load('original/OBS/action-full/manifest.js');
load('original/OBS/action-full-ext/manifest.js');
load('original/OBS/obs23-actors/manifest.js');
// #579: the 19 bodies recovered 2026-11-03 with their own palettes.
load('original/OBS/referenced/chr-bodies-manifest.js');
load('chr-body-source-map.js');
const api=sandbox.window.__LEAF_CHR_BODY_MAP__,all=Object.values(api.cards);
assert.equal(all.length,98,'all 98 known original CHR card records');
assert.equal(new Set(all.map(c=>c.card)).size,98);
const actual=all.filter(c=>!c.missing),unique=new Set(actual.map(c=>c.pak+'/'+c.member));
assert.equal(actual.length,97);
assert.equal(unique.size,97,'the original 97 body members must not alias');
assert.equal(all.filter(x=>x.missing).map(x=>x.card).join(','),'0156');
assert.equal(api.lookup('0088').member,'1071','Scheherazade is 1071 (not golem 1088)');
assert.equal(api.lookup('0087').member,'1070','Saladin is 1070 (not skeleton 1087)');
assert.equal(api.lookup('0091').member,'1074','Ironmask is 1074');
assert.equal(api.lookup('0056').member,'1040','native 1040 belongs to Ishutal 0056');
assert.equal(api.lookup('0170').member,'1267','Black Prince is OBS3 1267');
assert.equal(api.lookup('0125').member,'1199','CHR proves OBS2 link');
const available=actual.filter(c=>api.resolve(c.card));
assert.equal(available.length,97,'78 archived + 19 recovered original full-body image sets');
assert.equal(actual.length-available.length,0,'every CHR body member now has its own source frames');
assert.equal(api.resolve('0040').originalMember,'OBS.pak/1025.obs','0040 shows its OWN recovered body 1025, never 1040');
assert.ok(api.resolve('0040').frames.every(f=>f.url.startsWith('./original/OBS/referenced/obs-1025-')));
assert.equal(api.resolve('0156'),null,'original 1222 missing, no fake body');
assert.equal(api.resolve('0088').originalMember,'1071.obs');
assert.equal(api.resolve('0091').originalMember,'1074.obs');
assert.equal(api.resolve('0170').originalMember,'OBS3.pak/1267.obs');
assert.equal(api.resolve('0125').originalMember,'OBS2.pak/1199.obs');
assert.equal(api.assetKey('0088'),'0071');
assert.equal(api.assetKey('0170'),'obs3/1267');
assert.equal(api.assetKey('0125'),'obs2/1199');
const wrong=sandbox.window.ORIGINAL_LEAF_FULL_ACTION_FRAMES['0088'];
assert.ok(wrong&&wrong.originalMember==='1088.obs','known old misassigned golem PNG exists');
assert.notEqual(api.resolve('0088'),wrong,'do not show the 1088 golem for Scheherazade');
const head=fs.readFileSync(path.join(root,'index.html'),'utf8');
const a=head.indexOf('src="./original/OBS/obs23-actors/manifest.js"'),
 b=head.indexOf('src="./chr-body-source-map.js"'),
 c=head.indexOf('src="./genesis-chessman-actors.js"');
assert.ok(a>0&&b>a&&c>b,'source manifests and CHR map must load before live renderer');
const actor=fs.readFileSync(path.join(root,'genesis-chessman-actors.js'),'utf8');
assert.ok(actor.includes('window.__LEAF_CHR_BODY_MAP__?.resolve(id)'),
 'live game must use true CHR body identity');
assert.ok(!actor.includes('const originalFor=id=>{'),
 'legacy card-number fallback must not remain');
assert.ok(!actor.includes('const legacy=window.ORIGINAL_LEAF_OBS_FRAMES?.[id]'),
 'failed PNG must not fall back to a different OBS actor');
const sw=fs.readFileSync(path.join(root,'sw.js'),'utf8');
assert.ok(sw.includes("'./chr-body-source-map.js'"));
assert.ok(sw.includes("'./original/OBS/obs23-actors/manifest.js'"));
const summary=api.getState();
assert.equal(summary.resolvedSourceCards,97);
assert.equal(summary.knownUnpublishedCards.length,0);
assert.equal(summary.recovered20261103Cards.length,19);
assert.equal(summary.missingOriginalMembers[0],'0156');
console.log('4LEAF CHR +260 ORIGINAL CARD-TO-BODY SOURCE QA PASS',
 JSON.stringify({cards:98,assigned:97,published:97,recovered:19,missing:'0156',
  scheherazade:'0088->1071',ironmask:'0091->1074',blackPrince:'0170->1267',
  noCardIndexedFallback:true,originalAssetDigestsChecked:true}));
