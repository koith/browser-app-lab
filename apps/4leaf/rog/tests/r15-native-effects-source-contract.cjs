'use strict';
/* R15: real recovered 28/420 OBS effect source contract without a browser.
 * All source event bytes and image SHA are validated independently by
 * test_r15_effect_manifest_integrity.py. This test checks the actual live
 * module's source gating, per-card slot, timing scheduling and safe fallback.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {performance}=require('node:perf_hooks');
const root=path.resolve(__dirname,'..');
class MockImage{
 constructor(){this.naturalWidth=100}
 addEventListener(){}
 decode(){return Promise.resolve()}
 set src(v){this.source=v}
 get src(){return this.source}
}
class MockNode{
 constructor(tag){
  this.tagName=tag;this.style={};this.dataset={};
  this.isConnected=false;this.children=[];this.className='';
 }
 setAttribute(name,val){this[name]=val}
 append(node){this.children.push(node);node.isConnected=true}
 remove(){this.isConnected=false}
}
const sandbox={
 window:{matchMedia:()=>({matches:false})},
 document:{createElement:tag=>new MockNode(tag)},
 Image:MockImage,Promise,setTimeout,performance,console
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'original/OBS/duel-effects/manifest.js'),'utf8'),sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'native-duel-effects.js'),'utf8'),sandbox);
(async()=>{
 const api=sandbox.window.__LEAF_NATIVE_DUEL_FX__;
 const all=sandbox.window.ORIGINAL_LEAF_DUEL_EFFECTS;
 assert.ok(Object.keys(all).length>=28,'all first-round source effect members must remain available');
 assert.ok(Object.values(all).reduce((n,a)=>n+a.frames.length,0)>=420,'all first-round original effect frames retained');
 const a=api.eventsFor('0040'),b=api.eventsFor('0042'),c=api.eventsFor('0045');
 assert.ok(a.some(e=>e.numeric==='1096'),'0040 original slot12 effect 1096');
 assert.ok(b.some(e=>e.numeric==='1097'),'0042 original slot12 effect 1097');
 assert.ok(c.some(e=>e.numeric==='1101'),'0045 original slot12 effect 1101');
 assert.deepEqual(api.eventsFor('0156'),[],'unrecovered 0156 has no fabricated source effect');
 for(const e of [...a,...b,...c]){
  assert.equal(e.member,e.source.originalMember);
  assert.equal(e.source.status,'SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED');
  assert.ok(e.tick>=0&&e.source.frames.length>0);
 }
 const stage=new MockNode('section');stage.isConnected=true;
 stage.style.getPropertyValue=()=> '1';
 stage.getBoundingClientRect=()=>({left:0,top:0,right:800,bottom:600,width:800,height:600});
 const actor=new MockNode('div');actor.isConnected=true;
 actor.dataset={chessmanId:'c_0040',sourceMirror:'true'};
 actor.getBoundingClientRect=()=>({left:250,right:320,top:240,bottom:340,width:70,height:100});
 await api.warm('0040');
 const result=api.play(stage,actor,12);
 assert.ok(result.events>0,'native effect source events scheduled');
 await result.done;
 assert.equal(Number(stage.dataset.duelSourceEffects),result.events);
 assert.ok(Number(stage.dataset.duelSourceEffectFrames)>0,'actual native source keys rendered');
 assert.match(stage.dataset.duelSourceEffectEvidence,/VERIFIED/);
 const wrong=new MockNode('div');wrong.isConnected=true;
 wrong.dataset.chessmanId='c_0156';
 assert.equal(api.play(stage,wrong).events,0,'source-missing body never borrows effect art');
 console.log('R15_NATIVE_DUEL_EFFECT_SOURCE_CONTRACT_PASS',JSON.stringify({
  members:Object.keys(all).length,frames:Object.values(all).reduce((n,a)=>n+a.frames.length,0),
  sampleSlots:{card0040:a.length,card0042:b.length,card0045:c.length},
  rendered:Number(stage.dataset.duelSourceEffectFrames)
 }));
})().catch(e=>{console.error('R15_NATIVE_DUEL_EFFECT_SOURCE_CONTRACT_FAIL',e.stack||e);process.exit(1)});
