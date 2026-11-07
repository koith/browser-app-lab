'use strict';
/* R17 — independent actual source-data check. Data is original 2002 CHR
 * animation indexes/ticks, action labels (hurt/victory) are WEB INFERRED.
 * The historical executable did NOT name these animation slots.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const data=JSON.parse(fs.readFileSync(path.join(root,
 'docs/evidence/source-maps/actor-native-anim-runtime.json'),'utf8'));
const sourceJs=fs.readFileSync(path.join(root,'native-card-action-sequences.js'),'utf8');
const native=new Map();
for(const [id,entry] of Object.entries(data.cards)){
 const maximum=Math.max(0,...entry.animations.flatMap(a=>a.keys.map(k=>k[1])));
 native.set(id,{originalMember:entry.member,frames:Array.from({length:maximum+1},
  (_,index)=>({index,url:'./original-OBS-source-'+id+'-'+index+'.png'}))});
}
const window={
 __LEAF_CHR_BODY_MAP__:{resolve:card=>native.get(card)||null}
};
vm.runInNewContext(sourceJs,{window,console});
const api=window.__LEAF_NATIVE_CARD_ACTIONS__;
assert.ok(api,'native slot module missing');
assert.equal(api.getState().tableBodies,97);
assert.equal(api.getState().outcomeRole,'INFERRED/WEB-only');
let retained=0,presentExtra=0,outcomeSequences=0,emptyExtras=0;
for(const [id,c] of Object.entries(data.cards)){
 const table=api.table(id),body=native.get(id);
 assert.ok(table,'CHR source table missing '+id);
 assert.equal(table.anims.length,17,'do not truncate source slots at 12');
 const extras=api.sourceExtraSlots(id);
 assert.equal(extras.length,4);
 for(let slot=0;slot<17;slot++){
  const original=c.animations.find(a=>a.index===slot);
  const actual=table.anims[slot];
  if(original&&original.ticks!==0xffffffff){
   assert.ok(actual,'published source slot absent: '+id+'/'+slot);
   assert.equal(actual.ticks,original.ticks);
   assert.equal(JSON.stringify(actual.keys),JSON.stringify(original.keys),
    'SOURCE INDEX/TICK BYTES CHANGED '+id+'/'+slot);
   retained++;
  }else{
   assert.equal(actual,null,'source 0xFFFFFFFF must remain empty '+id+'/'+slot);
   if(slot>=13)emptyExtras++;
  }
 }
 for(let slot=13;slot<17;slot++){
  const record=extras.find(x=>x.slot===slot);
  assert.ok(record);
  assert.equal(record.role,'UNVERIFIED/NO_ORIGINAL_ACTION_NAME');
  const from=table.anims[slot];
  assert.equal(record.absent,!from);
  assert.equal(JSON.stringify(record.keys),JSON.stringify(from?.keys||[]));
  if(from)presentExtra++;
 }
 for(const [action,slot] of [['hurt',13],['victory',14]]){
  const original=table.anims[slot];
  const result=api.sequenceFor(body,id,action,'toward',
    {duel:true,side:'defender'});
  if(!original?.keys?.length)continue;
  assert.ok(result,'must show original own CHR animation '+id+'/'+slot);
  assert.equal(result.nativeSlot,String(slot));
  assert.equal(result.nativeDurationTicks,original.ticks);
  assert.equal(result.nativeDurationMs,original.ticks*40);
  assert.equal(result.intervalMs,40);
  assert.equal(result.loop,false);
  assert.match(result.nativeEvidence,/VERIFIED.*INFERRED/);
  const frames=[];
  original.keys.forEach(([tick,frame],i)=>{
   const end=i+1<original.keys.length?original.keys[i+1][0]:original.ticks;
   for(let t=tick;t<Math.max(tick+1,end);t++)frames.push(frame);
  });
  assert.equal(JSON.stringify(result.map(r=>r.index)),JSON.stringify(frames),
   'original key order or tick repetitions modified '+id+'/'+slot);
  assert.ok(result.every(x=>body.frames[x.index]===x),
   'an actor may NEVER borrow another body source frame');
  const foreign={...body,frames:body.frames.slice()};
  assert.equal(api.sequenceFor(foreign,id,action,'toward',
   {duel:true,side:'defender'}),null,'cross-card source substitution not rejected');
  outcomeSequences++;
 }
}
assert.equal(Object.keys(data.cards).length,97);
assert.equal(presentExtra,85*2+97*2,
 'source slots 15/16 must be present on exactly 85 original bodies');
assert.equal(emptyExtras,24,
 'preserve exactly twelve native bodies with empty 15/16 slots');
assert.equal(outcomeSequences,194);
assert.equal(api.table('0156'),null,'the missing body must not be fabricated');
assert.equal(api.sourceExtraSlots('0156'),null);
console.log('R17_ORIGINAL_17_SLOT_SOURCE_CONTRACT_PASS',JSON.stringify({
 cards:97,originalNonemptySlots:retained,extraSlotSources:presentExtra,
 unclassifiedSlotAbsences:emptyExtras,inferredOutcomeSourceSequences:outcomeSequences,
 semantic:'source-native-keys-and-ticks-VERIFIED/roles-and-WEB-ms-INFERRED'
}));
