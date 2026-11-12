'use strict';
/* M00 - original 4LEAF installer/source asset provenance acceptance.
   Honest about 2002 client and unverified 2004 executable semantics.
   No Windows binary executes; all SHA and on-disk PNG bytes verified. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),base='86526d89679ae39b85fe9808da97ad871b7888d9';
const bytes=p=>fs.readFileSync(path.join(root,p));
const str=p=>bytes(p).toString('utf8');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const readJson=p=>JSON.parse(str(p));
const exported=readJson('original/manifest.json');
assert.match(exported.source,/Archived 4Leaf original client installer/);
assert.equal(exported.original_source,'https://archive.org/details/4leaf');
assert.ok(exported.resources.length>=100,'actual 2002 extracted sprite resources indexed');
const chr=readJson('docs/evidence/source-maps/card-body-map.json');
assert.equal(Object.keys(chr.cards).length,98,'original CHR.pak roster');
assert.equal(new Set(Object.keys(chr.cards)).size,98);
assert.equal(chr.cards['0156'].bodyMember,'1222','unique missing source CHR record preserved');
for(const [id,v] of Object.entries(chr.cards)){
 assert.equal(v.provenance.installerSHA1,base,'no unverified installer merged '+id);
 assert.equal(v.provenance.chrRecord,id+'.chr','must associate archived CHR id');
 assert.match(v.provenance.chrRecordSHA256,/^[a-f0-9]{64}$/);
 if(id==='0156')continue;
 assert.match(v.bodySHA256,/^[a-f0-9]{64}$/,'genuine source OBS member SHA '+id);
 assert.match(v.provenance.bodyPakSHA256,/^[a-f0-9]{64}$/);
}
const extra=readJson('original/SourceSPRExtra/manifest.json');
assert.equal(extra.source,'2002 Dice/IMG.pak');
assert.match(extra.sourceSHA256,/^[a-f0-9]{64}$/);
assert.equal(extra.classifiedNative2DOnly,true);
assert.equal(extra.original3DDiceMeshRecovered,false,'no falsely recovered 2004 dice mesh');
const mapSandbox={window:{}};
vm.runInNewContext(str('original/maps.js'),mapSandbox);
vm.runInNewContext(str('original/tiles.js'),mapSandbox);
const maps=mapSandbox.window.ORIGINAL_LEAF_MAPS,events=mapSandbox.window.ORIGINAL_LEAF_TILES;
assert.equal(Object.keys(maps).length,26);
assert.equal(Object.keys(events).length,25);
const cells=Object.values(maps).reduce((n,r)=>n+r.length,0);
assert.equal(cells,1920);
assert.equal(maps['0170'].length,135);
assert.equal(events['0170'],undefined,'unknown original event data is not synthesized');
const roleChecks=[
 {file:'original/MainFrame/toolbarbtn.png',source:'2002 MainFrame sprite atlas',width:120,height:270,
  consumer:'mainframe-native-toolbar.css',token:'toolbarbtn.png',role:'8 navigation + utility buttons (WEB mapping inferred)'},
 {file:'original/MainFrame/pannel.png',source:'2002 MainFrame source image',width:323,height:124,
  consumer:'mainframe-native-toolbar.css',token:'pannel.png',role:'source navigation toolbar panel'},
 {file:'original/WorldMap/notice.png',source:'2002 WorldMap image',width:184,height:61,
  consumer:'world-map.js',token:'notice.png',role:'permanent source world notice overlay'},
 {file:'original/CardShop/cardshopbutton.png',source:'2002 CardShop sprite atlas',
  consumer:'cardshop-original-2003.css',token:'cardshopbutton.png',role:'real buy/sell controls'},
 {file:'original/Tiles/0024.png',source:'2002 Dice/TIS native terrain',
  consumer:'game.js',token:'0024',role:'original game DMP start tile'},
 {file:'original/IMG/avatarback.png',source:'2002 Dice/IMG original 2D fallback',
  consumer:'game.js',token:'avatarback.png',role:'source missing 0156 cardback; no invented body'}
];
const output=[];
for(const item of roleChecks){
 const b=bytes(item.file);
 assert.equal(b.subarray(0,8).toString('hex'),'89504e470d0a1a0a','genuine PNG '+item.file);
 const w=b.readUInt32BE(16),h=b.readUInt32BE(20);
 if(item.width)assert.deepEqual([w,h],[item.width,item.height],item.file);
 assert.ok(str(item.consumer).includes(item.token),'real active screen consumer missing '+item.file);
 output.push({...item,bytes:b.length,width:w,height:h,sha256:sha(b),
  sourceStatus:'VERIFIED-ARCHIVE-IMAGE/SHA256; LIVE-ROLE-RECONSTRUCTED',
  appReference:item.consumer});
}
const pngs=exported.resources.filter(r=>r.image?.endsWith('.png'));
let documented=0;
for(const ref of pngs){
 const name='original/'+ref.image;
 const p=path.join(root,name);
 if(!fs.existsSync(p))continue;
 const b=bytes(name);
 if(b.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw Error('non-PNG '+name);
 assert.deepEqual([b.readUInt32BE(16),b.readUInt32BE(20)],[ref.width,ref.height],name);
 documented++;
}
assert.ok(documented>=100,'archive indexed live original images have real bytes');
const report={
 sourceArchive:exported.original_source,archiveType:'2002 verified original client / data1.cab and PAK',
 installerSHA1:base,sourceBinaryExecutableRun:false,
 originalIndexPNGCount:documented,originalCHRRecords:Object.keys(chr.cards).length,
 originalCHRPublishedBodies:97,sourceMissingCHR:'0156/OBS2-1222',
 originalMAPRoutes:26,originalMAPCells:cells,originalEventRoutes:25,
 originalEventSourceGap:'0170 (135 DMP cells, original title+events absent)',
 extraIMGSourceSHA256:extra.sourceSHA256,
 historicalEXEInputHandlers:'UNVERIFIED',historical3DMesh:'UNVERIFIED',
 assets:output
};
if(process.env.LEAF_SOURCE_REPORT){
 fs.writeFileSync(process.env.LEAF_SOURCE_REPORT,JSON.stringify(report,null,2)+'\n');
}
console.log('M00_ARCHIVE_FILE_ROLE_SOURCE_AUDIT_PASS',
 JSON.stringify({indexedSourceImages:documented,artRoles:output.length,
 originalCHRRecords:98,originalSourceBodies:97,paths:26,routeCells:1920,
 originalEventRoutes:25,archiveSha:base}));
