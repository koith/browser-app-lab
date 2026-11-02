'use strict';
/* Unit QA for source-verified OBS 1040 keyframes and conservative 53-member intake. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const sandbox={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'native-obs-action-runtime.js'),'utf8'),sandbox);
const api=sandbox.window.__LEAF_NATIVE_OBS_ACTIONS__;
const member={originalMember:'1040.obs',
 sourceSHA256:'ac954b320e56b8c34ffbf1249a9905a4a53e9ac1e91c291cc398216cd8db0734',
 frames:Array.from({length:37},(_,i)=>({index:i,originX:-4,originY:-55,width:30,height:60,
 sha256:'a'.repeat(64),url:'./original/OBS/action-full/1040-'+String(i).padStart(2,'0')+'.png'}))};
const frames=(a,t='toward',c={})=>api.sequenceFor(member,a,'0040',t,c);
const indices=s=>Array.from(s||[],f=>f.index);
assert.deepEqual(indices(frames('walk','away')),[3,5,6,7,8]);
assert.deepEqual(indices(frames('walk','left')),[14,15,16,17,18,19]);
assert.deepEqual(indices(frames('walk','right')),[14,15,16,17,18,19]);
assert.equal(frames('walk','right').mirror,true);
assert.deepEqual(indices(frames('walk','toward')),[25,26,27,28,29,30]);
assert.deepEqual(indices(frames('idle','toward',{rest:'away'})),[0,1,2]);
assert.deepEqual(indices(frames('idle','toward',{rest:'left'})),[11,12,13]);
assert.deepEqual(indices(frames('idle','toward',{rest:'toward'})),[22,23,24]);
assert.deepEqual(indices(frames('attack','toward',{duel:true,side:'attacker'})),[33,34,35,36]);
assert.equal(frames('attack','toward',{duel:true,side:'attacker'}).mirror,true);
assert.equal(frames('attack','toward',{duel:true,side:'attacker'}).loop,false);
assert.equal(frames('attack'),null,'unproven ordinary attack keeps existing WEB fallback');
assert.equal(api.sequenceFor(member,'walk','0043','away'),null,'no automatic other-character guess');
assert.deepEqual(Array.from(frames('walk','away').nativeKeyTicks),[0,3,6,9,12]);
assert.match(frames('walk','away').nativeMilliseconds,/UNVERIFIED/);
assert.match(frames('walk','away').nativeEffectPlayback,/DISABLED/);
for(const bad of [
 {...member,sourceSHA256:'0'.repeat(64)},
 {...member,originalMember:'1041.obs'},
 {...member,frames:member.frames.slice(0,36)},
 {...member,frames:member.frames.map((f,i)=>i===4?{...f,url:'./wrong.png'}:f)},
 {...member,frames:member.frames.map((f,i)=>i===4?{...f,sha256:'bad'}:f)}
])assert.equal(api.sequenceFor(bad,'walk','0040','away'),null,'fail closed on source mismatch');
const raw={cards:{'0040':{animations:[{ticks:9,
 keys:[[0,3],[3,5],[6,6],[9,7]],events:[[3,2,1096,0,-10]]}]}}};
const stats=api.registerDecodedMap(raw);
assert.equal(stats.cardCount,1);assert.equal(stats.keys,4);assert.equal(stats.events,1);
assert.match(stats.evidence,/STRUCTURAL_ONLY/);
assert.equal(api.sequenceFor(member,'attack','0040','toward'),null,'raw unnamed actions cannot auto-play');
for(const bad of [
 {cards:{'0040':{animations:[{ticks:3,keys:[[3,1],[1,2]]}]}}},
 {cards:{'0040':{animations:[{ticks:3,keys:[[0,1]],events:[[0,2,1096,0]]}]}}},
 {cards:{'0040':{animations:[{ticks:3,keys:[[0,-1]]}]}}},
 {cards:{'0040':{animations:[{ticks:3,keys:[[4,1]]}]}}},
 {cards:{'0040':{animations:[]}}},
 {cards:{x:{animations:[{ticks:3,keys:[[0,1]]}]}}}
])assert.throws(()=>api.inspectDecodedMap(bad));
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.ok(html.indexOf('src="./native-obs-action-runtime.js"')>
 0&&html.indexOf('src="./native-obs-action-runtime.js"')<
 html.indexOf('src="./genesis-chessman-actors.js"'));
assert.ok(fs.readFileSync(path.join(root,'sw.js'),'utf8')
 .includes("'./native-obs-action-runtime.js'"));
console.log('NATIVE OBS 1040 ACTION KEYFRAME BRIDGE PASS',
 JSON.stringify({sourceFrames:37,rearWalk:[3,5,6,7,8],
 originalMillisKnown:false,otherCharactersAutoplayed:0,effectMembersAutoplayed:0}));
