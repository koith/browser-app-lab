'use strict';
const assert=require('node:assert/strict');
const {parseOriginalPakIndex}=require('../tools/original-pak-index.cjs');
const values=[{name:'0074.obs',length:166},{name:'1025.obs',length:26044},
 {name:'0000.chr',length:471}];
const h=Buffer.alloc(4+28*values.length,255);
h.writeUInt32LE((~values.length)>>>0,0);
for(const [i,file] of values.entries()){
 const at=4+i*28;
 const name=Buffer.from(file.name,'ascii');
 for(let j=0;j<name.length;j++)h[at+j]=name[j]^255;
 h[at+name.length]=255;
 h.writeUInt32LE((~file.length)>>>0,at+24);
}
const data=parseOriginalPakIndex(h,h.length+values.reduce((a,b)=>a+b.length,0));
assert.equal(data.count,3);
assert.equal(data.resourceBytesExact,true,'sizes exactly partition container after source index');
assert.deepEqual(data.entries,values);
assert.equal(data.resourceSizeGap,0);
assert.throws(()=>parseOriginalPakIndex(Buffer.from([0,0,0,0])),/plausible/);
assert.throws(()=>parseOriginalPakIndex(h.subarray(0,20)),/Truncated/);
const broken=Buffer.from(h);broken[4]=255;
assert.throws(()=>parseOriginalPakIndex(broken),/Unrecognized/);
console.log('4LEAF BITWISE-INVERTED ORIGINAL PAK INDEX / FIXED 24 BYTE FILENAME / LENGTHS VERIFIED');
