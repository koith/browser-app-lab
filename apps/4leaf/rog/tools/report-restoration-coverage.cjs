'use strict';
/* 4LEAF preservation coverage report. Every count is read from real archive
 * manifests and local files; this is NOT a subjective visual similarity %
 * or a claim that an approximate game mesh is source-authentic.
 * Run: node apps/4leaf/rog/tools/report-restoration-coverage.cjs
 */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..');
const source=(p)=>fs.readFileSync(path.join(ROOT,p),'utf8');
const loadJSON=(p)=>JSON.parse(source(p));
const window={};
for(const file of [
 'original/maps.js','original/tiles.js','original/Tiles/art.js',
 'original/OBS/animation-manifest.js','original/OBS/animation-extra.js'
])vm.runInNewContext(source(file),{window},{filename:file,timeout:1200});
const cards=loadJSON('original/chessmen.json');
const chars=Object.entries(window.ORIGINAL_LEAF_OBS_FRAMES||{});
const tiles=Object.keys(window.ORIGINAL_LEAF_TILE_ART?.tiles||{});
const maps=Object.entries(window.ORIGINAL_LEAF_MAPS||{});
const rules=window.ORIGINAL_LEAF_TILES||{};
const sprites=loadJSON('original/SourceSPR/manifest.json').spriteAnimations;
const originalPhotos=['../assets/board.jpg','../assets/battle.jpg',
 '../assets/chat.jpg','../assets/chat_ref.jpg'];
const rel=(str)=>str.replace(/^\.\//,'');
const missing=[];
for(const [id,ch] of chars){
 const card=cards.find(c=>c.id===id);
 assert.ok(card,'unknown restored OBS chessman card '+id);
 assert.equal(Number(ch.originalMember.slice(1,4)),Number(id),
  'wrong Genesis ID mapped to original OBS frame '+id);
 for(const frame of ch.frames){
  if(!fs.existsSync(path.join(ROOT,rel(frame.url))))missing.push(frame.url);
 }
}
for(const [name,sprite] of Object.entries(sprites))
 for(const frame of sprite.frames||[])
  if(!fs.existsSync(path.join(ROOT,rel(frame.url))))missing.push(frame.url);
for(const id of tiles)
 if(!fs.existsSync(path.join(ROOT,'original/Tiles/'+id+'.png')))
  missing.push('original/Tiles/'+id+'.png');
for(const file of originalPhotos)
 if(!fs.existsSync(path.join(ROOT,file)))missing.push(file);
assert.deepEqual(missing,[],'Missing source art in deployed tree');
// The archived 26 movement routes and 25 decoded event rows are NOT an
// identical dataset. The missing member stays on the restoration backlog;
// never reject genuine archived route data or fabricate a replacement map.
const pathIds=new Set(maps.map(([id])=>id));
const eventIds=new Set(Object.keys(rules));
assert.ok([...eventIds].every(id=>pathIds.has(id)),
 'event map references a route absent from recovered original DMP/MVE');
const routesWithoutEventData=[...pathIds].filter(id=>!eventIds.has(id)).sort();
const originals=new Set(chars.map(([id])=>id));
const frames=chars.reduce((sum,[,c])=>sum+c.frames.length,0);
const single=chars.filter(([,c])=>c.frames.length===1).length;
const withFrameZero=chars.filter(([,c])=>c.frames.some(f=>f.index===0)).length;
const output={
 verified:{
  sourceChessmanCards:cards.length,
  originalOBSMembersConnected:originals.size,
  originalOBSFramePNGs:frames,
  originalSingleFrameStillCharacters:single,
  originalMembersWithDecodedFrameZero:withFrameZero,
  originalMembersWithNoDecodedBody:cards.filter(c=>!originals.has(c.id)).length,
  sourceDMPMaps:maps.length,
  sourceDMPEventMaps:eventIds.size,
  sourceRoutesWithoutFullEventData:routesWithoutEventData,
  sourceTISHexArt:tiles.length,
  sourceRollFrames:Object.fromEntries(Object.entries(sprites)
   .map(([k,v])=>[k,v.frames.length])),
  original2004PhotoReferences:originalPhotos.length,
  missingAssetReferences:missing.length
 },
 unverified:[
  'OBS original animation action/direction table',
  '2002 OBS action-specific foot-contact frame groups and client direction/FPS lookup tables',
  'original MVE three-dimensional height/camera mesh',
  'original 3D falling/bouncing result-specific dice assets and physics',
  'original battle podium polygon mesh/light',
  'historical public ChatTown room-name and occupancy database'
 ],
 warnings:[
  'Counts prove availability and identity, not original-playback fidelity.',
  'Recovered static OBS frames are source originals but cannot claim animation.',
  'SourceSPR roll.spr is a different four-frame member from eventRoll1.spr.'
 ]
};
console.log('4LEAF_RESTORATION_COVERAGE '+JSON.stringify(output));
if(process.argv.includes('--json'))process.stdout.write(JSON.stringify(output,null,2)+'\n');
