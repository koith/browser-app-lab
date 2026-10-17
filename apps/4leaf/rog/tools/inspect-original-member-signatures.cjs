'use strict';
/* Extract ONLY metadata from selected original 2002 PAK members. All content
 * bytes are ephemeral runner-private, never executed, shipped or uploaded.
 * PAK index uses inclusive inverted end offsets (source-verified).
 * SPR uses FAST.PAL.COLORKEY indexed animation; OBS format unknown.
 */
const fs=require('node:fs'),path=require('node:path');
const {loadPakIndex}=require('./original-pak-index.cjs');
const targets={
 'IMG.pak':['roll.spr','eventRoll1.spr','avatar.spr','winBattle.spr','minipanel.spr'],
 'OBS.pak':['0074.obs','1025.obs','1030.obs','1045.obs'],
 'OBS2.pak':['1199.obs','1200.obs'],
 'OBS3.pak':['1133.obs','1254.obs'],
 'CHR.pak':['0040.chr','0042.chr','0045.chr'],
 'DMP.pak':['0149.mve','0149.dmp'],
 'TIS.pak':['0000.tis','0015.tis']
};
function inspect(pak){
 const group=path.basename(pak);
 const wanted=targets[group];if(!wanted)return [];
 const index=loadPakIndex(pak),fd=fs.openSync(pak,'r');
 const rows=[];
 try{
  for(const file of wanted){
   const entry=index.entries.find(x=>x.name.toLowerCase()===file.toLowerCase());
   if(!entry)continue;
   const start=index.headerBytes+entry.startOffset;
   const bytes=Buffer.alloc(Math.min(entry.length,1024));
   const got=fs.readSync(fd,bytes,0,bytes.length,start);
   const head=bytes.subarray(0,got);
   const ascii=head.toString('latin1');
   const signature='FAST.PAL.COLORKEY';
   const sig=ascii.indexOf(signature);
   const read=(p,n)=>{
    if(p+n>head.length)return null;
    if(n===4)return head.readUInt32LE(p);
    if(n===2)return head.readUInt16LE(p);
    return head[p];
   };
   const offsets32=[];
   for(let p=0;p+4<=Math.min(128,head.length);p+=4)
    offsets32.push(read(p,4));
   const row={
    pak:group,name:file,bytes:entry.length,firstHex:head.subarray(0,192).toString('hex'),
    ascii64:[...head.subarray(0,64)].map(x=>x>=32&&x<=126?String.fromCharCode(x):'.').join(''),
    fastPalOffset:sig,
    fastPalHeader:sig<0?null:{
     frameCountU16at66:read(sig+66,2),
     widthU16at132:read(sig+132,2),
     heightU16at134:read(sig+134,2),
     firstRecordBytes:read(sig+128,4)
    },
    firstU32:offsets32
   };
   rows.push(row);
  }
 }finally{fs.closeSync(fd)}
 return rows;
}
module.exports={inspect};
