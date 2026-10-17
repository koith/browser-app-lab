'use strict';
/* Original 2002 4LEAF PAK INDEX parser (resource BYTES not included).
 * Observed direct from SHA1-verifiable original installer:
 * every byte in the index is bitwise inverted; the first UInt32LE is
 * resource count; each entry is a 24-byte zero-terminated filename followed
 * by UInt32LE CUMULATIVE END OFFSET MINUS ONE (the first resource offset is 0). This tool ONLY reads source INDEXES,
 * never runs original binaries or re-exports copyrighted content.
 * The 24/4 layout is experimentally validated against the first headers
 * of Dice/OBS.pak, Dice/CHR.pak, Dice/TIS.pak and Dice/DMP.pak.
 */
const fs=require('node:fs');
const HEADER_WIDTH=4,ENTRY_BYTES=28,NAME_BYTES=24,MAX_FILES=10000;
function invert32(data,offset){
 return (~data.readUInt32LE(offset))>>>0;
}
function parseOriginalPakIndex(data,rawSize=null){
 if(!Buffer.isBuffer(data)||data.length<4)throw Error('A source PAK header buffer is required');
 const count=invert32(data,0);
 if(!Number.isInteger(count)||count<1||count>MAX_FILES)
  throw Error('Not a plausible 4LEAF PAK index: '+count);
 const required=HEADER_WIDTH+count*ENTRY_BYTES;
 if(data.length<required)throw Error('Truncated source PAK index: '+data.length+' of '+required+' required');
 const entries=[],nameSet=new Set();let previousEnd=0;
 for(let i=0;i<count;i++){
  const at=HEADER_WIDTH+i*ENTRY_BYTES;
  const nameBytes=[];
  for(let j=0;j<NAME_BYTES;j++){
   const v=data[at+j]^255;
   if(!v)break;
   nameBytes.push(v);
  }
  const name=Buffer.from(nameBytes).toString('latin1');
  if(!name||name.length>NAME_BYTES||/[^\x20-\x7e]/.test(name))
   throw Error('Unrecognized source PAK member name at '+i);
  // All 56 original 2002 PAK files use inclusive last-byte offsets.
  // Add ONE before deriving the next byte span: source extract_original.py.
  const endOffset=invert32(data,at+NAME_BYTES)+1;
  if(endOffset<previousEnd)throw Error('Source member offsets must increase monotonically: '+name);
  const length=endOffset-previousEnd;
  if(nameSet.has(name))throw Error('Duplicate original file name '+name);
  nameSet.add(name);
  entries.push({name,length,startOffset:previousEnd,endOffset});
  previousEnd=endOffset;
 }
 const available=rawSize===null?null:rawSize-required;
 const gap=rawSize===null?null:rawSize-required-previousEnd;
 return {count,headerBytes:required,sumResourceBytes:previousEnd,
  rawSize,resourceRegionBytes:available,
  resourceSizeGap:gap,resourceBytesExact:gap===0,
  entries};
}
function loadPakIndex(path){
 const fd=fs.openSync(path,'r');
 try{
  const first=Buffer.alloc(4);
  if(fs.readSync(fd,first,0,4,0)!==4)throw Error('Empty PAK');
  const count=invert32(first,0);
  if(count<1||count>MAX_FILES)throw Error('Invalid source index count '+count);
  const buf=Buffer.alloc(4+count*ENTRY_BYTES);
  if(fs.readSync(fd,buf,0,buf.length,0)!==buf.length)throw Error('Truncated source header');
  const {size}=fs.fstatSync(fd);
  return parseOriginalPakIndex(buf,size);
 }finally{fs.closeSync(fd)}
}
module.exports={parseOriginalPakIndex,loadPakIndex};
if(require.main===module){
 const path=process.argv[2];
 if(!path)throw Error('Usage: node original-pak-index.cjs /path/to/your/legitimate/original/OBS.pak');
 const index=loadPakIndex(path);
 process.stdout.write(JSON.stringify(index,null,2)+'\n');
}
