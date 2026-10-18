'use strict';
/* Original source-coordinate integrity gate, NOT a 2004 screenshot fidelity gate.
 * Uses every authentic DMP path coordinate and the same live WEB projection
 * constants; separates duplicate/colliding SOURCE CELLS from legitimate alpha
 * overlaps and the still-unrecovered original 3D projection.
 */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'original/maps.js'),'utf8');
const prefix='window.ORIGINAL_LEAF_MAPS=';
assert.ok(source.startsWith(prefix),'genuine original DMP map object expected');
const end=source.indexOf(';',prefix.length);
assert.ok(end>0,'source DMP mapping terminator');
const maps=JSON.parse(source.slice(prefix.length,end));
const camera=fs.readFileSync(path.join(root,'board-camera.js'),'utf8');
function constants(name,keys){
 const match=camera.match(new RegExp('const '+name+'=\\{([^}]*)\\};'));
 assert.ok(match,'camera '+name+' must be statically verifiable');
 const fields=Object.fromEntries([...match[1].matchAll(/(\\w+):(\\d+)/g)]
  .map(([,key,val])=>[key,Number(val)]));
 keys.forEach(key=>assert.ok(Number.isFinite(fields[key]),name+'.'+key));
 return fields;
}
const sourceGrid=constants('SOURCE_GRID',['width','height','pitchX','pitchY']);
const size=constants('SIZE',['width','height']);
const stepX=sourceGrid.pitchX*size.width/sourceGrid.width;
const stepY=sourceGrid.pitchY*size.height/sourceGrid.height;
const tileW=145,tileH=97;
const results=[];
for(const [id,cells] of Object.entries(maps)){
 assert.ok(Array.isArray(cells)&&cells.length>8,'invalid DMP map: '+id);
 const seen=new Map();
 let duplicate=0,severe=0,maxBoundingOverlap=0,adjacent=0;
 for(let i=0;i<cells.length;i++){
  const a=cells[i];
  assert.ok(Array.isArray(a)&&a.length>=3&&a.slice(0,3).every(Number.isInteger),
   'bad original cell: '+id+'/'+i);
  const key=a[0]+','+a[1];
  if(seen.has(key))duplicate++;else seen.set(key,i);
  for(let j=0;j<i;j++){
   const b=cells[j],dx=Math.abs(a[0]-b[0])*stepX,dy=Math.abs(a[1]-b[1])*stepY;
   if((Math.abs(a[0]-b[0])===1&&a[1]===b[1])||
      (Math.abs(a[1]-b[1])===1&&a[0]===b[0]))adjacent++;
   // Conservative full rectangular bounding boxes, NOT source-alpha pixel
   // collision. Actual 2002 art has transparent corners; a small overlap
   // is expected. 40%+ is abnormal in the current WEB projection.
   const ratio=Math.max(0,tileW-dx)*Math.max(0,tileH-dy)/(tileW*tileH);
   maxBoundingOverlap=Math.max(maxBoundingOverlap,ratio);
   if(ratio>.40)severe++;
  }
 }
 results.push({map:id,tiles:cells.length,duplicate,severeBoundingCollisions:severe,
  adjacent,maxRectangularOverlapPercent:+(maxBoundingOverlap*100).toFixed(2)});
}
assert.equal(results.length,26,'all original DMP paths remain registered');
assert.equal(results.reduce((n,x)=>n+x.tiles,0),1920,'original source path count changed');
assert.ok(results.every(x=>x.duplicate===0),'DMP cell duplicate means fully stacked boards');
assert.ok(results.every(x=>x.severeBoundingCollisions===0),
 'WEB renderer now puts unrelated source TIS platforms on top of each other');
assert.ok(results.some(x=>x.adjacent>10),'source grid connectivity was audited');
const report={
 checkedMaps:results.length,checkedCells:results.reduce((n,x)=>n+x.tiles,0),
 duplicateCoordinates:0,severeBoundingCollisions:0,
 maximumRectangularOverlapPercent:Math.max(...results.map(x=>x.maxRectangularOverlapPercent)),
 sourceGrid,projectedPitch:{x:stepX,y:stepY},
 scope:'VERIFIED-DMP-DATA-AND-WEB-RECTANGLE-GEOMETRY; ORIGINAL-MESH/ALPHA/PIXEL-FIDELITY STILL UNVERIFIED',
 maps:results
};
const output=path.resolve(process.env.LEAF_AUDIT_OUTPUT||'rog-dmp-overlap-audit.json');
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n','utf8');
console.log('DMP NATIVE SOURCE GRID AUDIT PASS '+JSON.stringify({
 maps:report.checkedMaps,cells:report.checkedCells,duplicates:report.duplicateCoordinates,
 severe:report.severeBoundingCollisions,maxRectangularOverlapPercent:report.maximumRectangularOverlapPercent,
 output
}));
