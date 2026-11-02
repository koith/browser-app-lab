'use strict';
/* Authentic 2002 CHR body mapping, 78 published source frame families and
 * source-key-order checks. No assumptions about original tick milliseconds. */
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),sandbox={window:{}};
const load=p=>vm.runInNewContext(fs.readFileSync(path.join(root,p),'utf8'),sandbox,{filename:p});
load('original/OBS/action-full/manifest.js');
load('original/OBS/action-full-ext/manifest.js');
load('original/OBS/obs23-actors/manifest.js');
load('chr-body-source-map.js');
load('native-card-action-sequences.js');
const M=sandbox.window.__LEAF_CHR_BODY_MAP__,A=sandbox.window.__LEAF_NATIVE_CARD_ACTIONS__;
assert.equal(M.getState().cards,98);
assert.equal(M.getState().chrBodyMembers,97);
assert.equal(M.getState().resolvedSourceCards,78);
assert.equal(M.getState().knownUnpublishedCards.length,19);
const values=Object.values(M.cards);
assert.equal(new Set(values.filter(x=>!x.missing).map(x=>x.pak+'/'+x.member)).size,97);
assert.equal(M.lookup('0056').member,'1040');
assert.equal(M.lookup('0088').member,'1071');
assert.equal(M.lookup('0087').member,'1070');
assert.equal(M.lookup('0091').member,'1074');
assert.equal(M.lookup('0170').member,'1267');
assert.equal(M.lookup('0125').member,'1199');
assert.equal(M.resolve('0040'),null);
assert.equal(M.resolve('0156'),null);
assert.equal(M.resolve('0088').originalMember,'1071.obs');
assert.equal(M.resolve('0091').originalMember,'1074.obs');
assert.equal(M.resolve('0170').originalMember,'OBS3.pak/1267.obs');
assert.equal(M.resolve('0125').originalMember,'OBS2.pak/1199.obs');
const seq=(card,action,travel='toward',ctx={})=>A.sequenceFor(M.resolve(card),card,action,travel,ctx);
const ids=x=>Array.from(x||[],f=>f.index);
assert.deepEqual(ids(seq('0056','walk','away')),[3,5,6,7,8],
 '1040 decoded original ignores frame 4, now belongs to card 0056');
assert.deepEqual(ids(seq('0088','walk','away')),[3,5,6,7,8]);
assert.deepEqual(ids(seq('0088','walk','left')),[14,15,16,17,18,19]);
assert.deepEqual(ids(seq('0088','idle','toward')),[22,23,24]);
assert.deepEqual(ids(seq('0170','walk','toward')),[40,41,42,43,44,45]);
assert.deepEqual(ids(seq('0170','walk','away')),[0,1,2,3,4,5]);
assert.deepEqual(ids(seq('0125','idle','toward')),[25,26,27]);
assert.deepEqual(ids(seq('0135','idle','toward')).slice(0,3),[27,27,27]);
assert.deepEqual(ids(seq('0135','walk','toward')),[27],
 'empty native sequence uses same source frame rather than a fabricated walk');
assert.deepEqual(ids(seq('0171','walk','toward')),[38,39,40,41,42,43]);
assert.equal(seq('0040','walk','away'),null,'unpublished original body not replaced with unrelated 1040');
assert.equal(seq('0156','walk','away'),null,'missing original body not assigned');
assert.equal(seq('0088','attack','toward'),null,'attack roles not guessed from 18-byte table');
assert.equal(seq('0088','walk','right').mirror,true);
assert.equal(seq('0088','walk','left').mirror,false);
assert.deepEqual(Array.from(seq('0088','walk','away').nativeKeyTicks),[0,3,6,9,12]);
assert.match(seq('0088','walk','away').nativeMilliseconds,/UNVERIFIED/);
assert.match(seq('0088','walk','away').nativeEffects,/DISABLED/);
const temp=M.resolve('0088').frames;
assert.equal(A.sequenceFor({frames:temp},'0088','walk','away'),null,
 'unknown source objects may not impersonate original member');
assert.equal(A.getState().obs23Bodies,36);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8'),sw=fs.readFileSync(path.join(root,'sw.js'),'utf8');
assert.ok(html.indexOf('src="./original/OBS/obs23-actors/manifest.js"')<
 html.indexOf('src="./chr-body-source-map.js"'));
assert.ok(html.indexOf('src="./chr-body-source-map.js"')<
 html.indexOf('src="./native-card-action-sequences.js"'));
assert.ok(html.indexOf('src="./native-card-action-sequences.js"')<
 html.indexOf('src="./genesis-chessman-actors.js"'));
assert.ok(sw.includes("'./chr-body-source-map.js'"));
assert.ok(sw.includes("'./native-card-action-sequences.js'"));
assert.ok(sw.includes("'./original/OBS/obs23-actors/manifest.js'"));
const runtime=fs.readFileSync(path.join(root,'genesis-chessman-actors.js'),'utf8');
assert.ok(runtime.includes('window.__LEAF_CHR_BODY_MAP__?.resolve(id)'));
assert.ok(runtime.includes('window.__LEAF_NATIVE_CARD_ACTIONS__?.sequenceFor'));
assert.ok(!runtime.includes('const legacy=window.ORIGINAL_LEAF_OBS_FRAMES?.[id]'));
assert.ok(!runtime.includes('?window.ORIGINAL_LEAF_OBS_FRAMES?.[id]'));
console.log('4LEAF CHR 98 CARD-BODY NATIVE 78 SOURCE ACTIONS PASS',
 JSON.stringify({cards:98,bodies:97,published:78,unpublished:19,
  missing:'0156',correctedAssignments:['0056->1040','0087->1070','0088->1071','0091->1074','0170->1267'],
  sourceTicksVerified:true,originalMillisecondsKnown:false}));
