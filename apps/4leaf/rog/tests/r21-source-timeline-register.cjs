'use strict';
/* SRC-02 PROVENANCE GATE. Build native 2002 frame tick timeline from actual
 * source with no 2004 FPS/3D/video fabrication. Explicit UNVERIFIED states
 * are the accepted archival output when historical motion is missing. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=JSON.parse(fs.readFileSync(path.join(root,'docs/evidence/source-maps/original-motion-timeline-register.json'),'utf8'));
assert.equal(source.schema,'4leaf-original-motion-source-timeline-v1');
assert.equal(source.sourceInstallerSHA1,'86526d89679ae39b85fe9808da97ad871b7888d9');
assert.equal(source.originalNative3DAssetsRecovered,false);
assert.equal(source.original2004TimedVideoRecovered,false);
assert.deepEqual(source.states.map(x=>x.id),['idle','movement','D4','D6','battle','room-entry']);
assert.ok(source.missingEvidence.length>=4);
const script=fs.readFileSync(path.join(root,'original/OBS/dice-blocks/manifest.js'),'utf8');
const dice=JSON.parse(script.slice(script.indexOf('window.ORIGINAL_LEAF_DICE_BLOCKS=')+'window.ORIGINAL_LEAF_DICE_BLOCKS='.length).replace(/;\s*$/,''));
const nativeSandbox={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'native-card-action-sequences.js'),'utf8'),nativeSandbox);
const api=nativeSandbox.window.__LEAF_NATIVE_CARD_ACTIONS__;
assert.equal(api.table('0040').anims.length,17,'actual 17 original OBS action slots available');
const frames=[];
for(const [id,slotSet] of [['idle',[0,1,2]],['movement',[3,4,5]],['battle',[12]]]){
 const task=source.states.find(x=>x.id===id);
 assert.ok(task.recordedKeys.startsWith('VERIFIED-2002'));
 assert.match(task.original2004Timecode,/UNVERIFIED/);
 for(const slot of slotSet){
  const anim=api.table('0040').anims[slot];
  assert.ok(anim&&anim.keys?.length>0,'actual source OBS keys for '+id+' slot'+slot);
  assert.ok(Number.isInteger(anim.ticks)&&anim.ticks>0);
  const offsets=anim.keys.map(x=>x[0]);
  assert.deepEqual(offsets,offsets.slice().sort((a,b)=>a-b));
  frames.push({state:id,slot,keys:anim.keys.length,nativeTicks:anim.ticks});
 }
}
let verifiedPngs=0;
for(const [id,sides] of [['1223',4],['1171',6]]){
 const record=dice.members[id],task=source.states.find(x=>x.id==='D'+sides);
 assert.equal(record.sides,sides);
 assert.equal(task.sourceMember,'OBS/'+id);
 assert.equal(record.animations['20'].ticks,30);
 assert.ok(record.animations['20'].keys.length>=12);
 assert.ok(record.animations['12'].keys.length>=16);
 assert.equal(record.animations['12'].sounds[0][1],2125);
 assert.equal(task.original2004MotionVideo,null);
 for(const block of record.blocks){
  for(const frame of block.frames){
   assert.match(frame.url,/^\.\/original\/OBS\/dice-blocks\//);
   const p=path.join(root,frame.url.slice(2));
   assert.ok(fs.existsSync(p),'genuine original frame '+p);
   verifiedPngs++;
  }
 }
 assert.ok(record.blockFrames.length>=3);
}
const refFiles=new Set(source.states.map(x=>x.historicalShot));
for(const name of refFiles){const p=path.resolve(root,'docs/evidence/source-maps',name);
 // Historical photos are actually stored two levels above our evidence directory.
 const asset=path.resolve(root,'../assets',path.basename(name));
 assert.ok(fs.existsSync(asset),'historic screenshot ref missing: '+asset);
 const bytes=fs.readFileSync(asset);
 assert.ok(bytes.length>1000);
}
for(const st of source.states){
 assert.equal(st.original2004MotionVideo,null,'never fabricate historic video '+st.id);
 assert.match(st.original2004Timecode,/UNVERIFIED/);
 assert.ok(st.sourceRecords.length>=2,'source file/time evidence for '+st.id);
}
console.log('SRC02_ORIGINAL_SOURCE_MOTION_TIMELINE_PASS',JSON.stringify({
 originalSourceStates:source.states.map(x=>x.id),verifiedKeySets:frames.length,sourceFrameFiles:verifiedPngs,
 missingOriginal2004MotionVideo:true,
 originalNative3D:false,actionRoleFps:'UNVERIFIED',nativeTickOffset:'VERIFIED'}));
