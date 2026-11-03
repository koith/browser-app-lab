'use strict';
/* Round 11 — sequence rules of the generated original-table module for every
 * published CHR body (real manifests, no browser). Original-table derived:
 * frame indices/ticks are VERIFIED; roles and 40ms/tick are INFERRED/WEB. */
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),sandbox={window:{}};
const load=p=>vm.runInNewContext(fs.readFileSync(path.join(root,p),'utf8'),sandbox,{filename:p});
for(const p of ['original/OBS/action-full/manifest.js','original/OBS/action-full-ext/manifest.js',
 'original/OBS/obs23-actors/manifest.js','chr-body-source-map.js','native-card-action-sequences.js'])load(p);
const M=sandbox.window.__LEAF_CHR_BODY_MAP__,A=sandbox.window.__LEAF_NATIVE_CARD_ACTIONS__;
const ids=x=>Array.from(x||[],f=>f.index);
const cards=Object.keys(M.cards).filter(c=>M.resolve(c));
assert.equal(cards.length,78);
const tally={lunge:0,emptyHold:0};
for(const card of cards){
 const n=M.resolve(card),t=A.table(card),lunge=t.anims[6];
 const att=A.sequenceFor(n,card,'attack','toward',{duel:true,side:'attacker'});
 const def=A.sequenceFor(n,card,'attack','toward',{duel:true,side:'defender'});
 assert.ok(att&&def,card+' duel attack resolved from its own table');
 assert.equal(att.mirror,true);assert.equal(def.mirror,false);
 assert.equal(att.loop,false);
 if(lunge.keys.length){
  const expected=[];
  lunge.keys.forEach(([tick,frame],k)=>{
   const end=k+1<lunge.keys.length?lunge.keys[k+1][0]:lunge.ticks;
   for(let x=tick;x<Math.max(end,tick+1);x++)expected.push(frame);
  });
  assert.deepEqual(ids(att),expected,card+' lunge = anim-12 keys over exact ticks');
  assert.equal(att.intervalMs,40);assert.equal(att.nativeDurationMs,lunge.ticks*40);
  assert.equal(att.nativeSlot,'12');
  tally.lunge++;
 }else{
  assert.equal(att.length,1);assert.match(att.nativeEvidence,/anim12-has-no-keys/);
  tally.emptyHold++;
 }
 // No legacy [10,18]/[18,10]/[25,30,0] guesses for hurt/victory any more.
 for(const action of ['hurt','victory']){
  const s=A.sequenceFor(n,card,action,'toward',{duel:true,side:'defender'});
  assert.equal(s.length,1,card+' '+action+' holds one same-body stance');
  assert.equal(s[0].index,(t.anims[1].keys[0]||t.anims[4].keys[0]||t.anims[2].keys[0]||t.anims[5].keys[0])[1]);
  assert.match(s.nativeEvidence,/UNVERIFIED/);
 }
 const board=A.sequenceFor(n,card,'attack','toward',{duel:false});
 if(t.pak==='obs')assert.equal(board,null,'classic board attack stays on the structural 31/32 path');
 else assert.equal(board.length,1,card+' OBS2/3 board attack holds its own front stance');
}
assert.deepEqual(tally,{lunge:77,emptyHold:1});
assert.equal(A.sequenceFor(null,'0040','attack','toward',{duel:true}),null,'unpublished body never substituted');
assert.equal(A.sequenceFor(M.resolve('0088'),'0074','idle','toward',{}),null,'other body cannot impersonate 0074');
// Empty walk slots (0135) hold the side idle when walking sideways, not a front frame.
assert.deepEqual(ids(A.sequenceFor(M.resolve('0135'),'0135','walk','left',{})),[4]);
const s=A.getState();
assert.equal(s.tableBodies,97);assert.equal(s.classicBodies,42);assert.equal(s.obs23Bodies,36);
assert.equal(s.originalTickMilliseconds,'UNVERIFIED');assert.equal(s.sourceEffectPlayback,false);
console.log('CHR NATIVE DUEL SEQUENCES PASS',JSON.stringify({published:cards.length,...tally}));
