'use strict';
/* BRD-04: every archived DMP route cell and every extant DMO/event
 * record, verified without silently guessing a missing 0170 event table.
 * This does NOT claim that the unavailable 2002 MVE mesh was decoded. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const s={window:{}};
for(const file of ['original/maps.js','original/tiles.js'])
 vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'),s,{filename:file});
const maps=s.window.ORIGINAL_LEAF_MAPS,info=s.window.ORIGINAL_LEAF_MAP_INFO;
const events=s.window.ORIGINAL_LEAF_TILES;
const ids=Object.keys(maps).sort();
assert.equal(ids.length,26,'original DMP has exactly 26 distinct route IDs');
assert.equal(Object.keys(info).length,25,'only 25 original map names are recovered');
assert.equal(Object.keys(events).length,25,'only 25 original event maps are recovered');
assert.deepEqual(Object.keys(maps).filter(x=>!events[x]),['0170'],
 'the sole source-absent DMO/event record must be 0170');
assert.equal(info['0170'],undefined,'do not invent 0170 historical name');
assert.equal(events['0170'],undefined,'do not fabricate 0170 event table');
const details=[];let cells=0,eventCells=0,warps=0;
for(const id of ids){
 const route=maps[id],tileEvents=events[id];
 assert.ok(route.length>9,'empty original path '+id);
 assert.equal(route[0].length,6,'DMP native cell record has six fields');
 assert.equal(route[0][2],13,'source DMP start marker '+id);
 let special=0,warpCells=0;
 for(const [index,cell] of route.entries()){
  assert.equal(cell.length,6,id+': row width '+index);
  for(const n of cell)assert.ok(Number.isSafeInteger(n),id+' non-source coordinate');
  assert.ok(cell[0]>=0&&cell[1]>=0,id+' invalid grid cell');
  if(cell[3]!==0){special++;if(cell[3]===12)warpCells++;}
 }
 if(id==='0170'){
  assert.equal(route.length,135,'original anonymous DMP 0170 135 cells');
  assert.ok(special>0,'0170 raw DMP path contains source geometry annotations');
 }else{
  assert.equal(tileEvents.length,route.length,
   'original event table/path length mismatch '+id);
  assert.equal(tileEvents[0]?.type,'start','source event starts here '+id);
  assert.equal(tileEvents.at(-1)?.type,'goal','source event ends here '+id);
  assert.ok(info[id]?.title,'original published title missing '+id);
  const groups=new Map();
  for(const [index,event] of tileEvents.entries()){
   assert.ok(event&&typeof event.type==='string'&&event.type,
    id+' source event record missing '+index);
   if(event.type==='warp'){
    assert.match(String(event.warpGroup||''),/^[0-9]+$/);
    groups.set(event.warpGroup,(groups.get(event.warpGroup)||0)+1);
    warps++;
   }
  }
  eventCells+=tileEvents.length;
 }
 cells+=route.length;
 details.push({id,n:route.length,sourceEventCells:tileEvents?.length||0,
  historicalName:info[id]?.title||null,specialRouteCells:special,warpRouteCells:warpCells});
}
assert.equal(cells,1920,'all source DMP path cells included');
assert.equal(eventCells,1785,'all 25 source event arrays included');
assert.ok(warps>0,'original map warps omitted from fixture');
const game=fs.readFileSync(path.join(root,'game.js'),'utf8');
assert.match(game,/0170/,'0170 must remain registered in playable game');
assert.match(game,/TITLE-UNVERIFIED/,'missing title must be visible as unverified');
const audit={source:'2002 DMP archive path+event JS as recovered',
 fullRouteMaps:ids.length,totalRouteCells:cells,verifiedEventMaps:25,
 verifiedEventCells:eventCells,sourceMissingEventMap:'0170',
 missingEventCellCount:135,sourceWarpEvents:warps,
 originalMeshView:'UNVERIFIED',
 maps:details};
if(process.env.LEAF_MAP_REPORT)
 fs.writeFileSync(process.env.LEAF_MAP_REPORT,JSON.stringify(audit,null,2)+'\n');
console.log('BRD04_26_ORIGINAL_DMP_25_DMO_SOURCE_PASS',JSON.stringify({
 routes:ids.length,cells,eventMaps:25,eventCells,missing:'0170',warps}));
