'use strict';
/* Strict inventory of recovered ORIGINAL Dice/OBS source PNGs.
 * Every cached chessman frame must have the ID, filename, 2002 OBS member,
 * original 8-bit palette-derived RGBA frame dimensions and byte hash that
 * the authenticated extraction manifest declares. No palette re-draw, chat
 * avatar stand-ins, missing frames or silent broken-URL fallback accepted.
 * Pose labels and scanline X remain provisional until original client decode.
 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const shared={window:{}};
for(const name of ['animation-manifest.js','animation-extra.js']){
 const file=path.join(root,'original/OBS',name);
 if(!fs.existsSync(file))throw new Error('Missing source manifest '+file);
 vm.runInNewContext(fs.readFileSync(file,'utf8'),shared,{filename:file,timeout:1500});
}
const manifest=shared.window.ORIGINAL_LEAF_OBS_FRAMES||{};
const sourceIds=Object.keys(manifest),used=new Set();
let frames=0,total=0;const entries=[];
assert.ok(sourceIds.length>=2,'At least both recovered 0042/0045 source actors should exist');
for(const cid of sourceIds){
 const item=manifest[cid];
 assert.match(cid,/^\d{4}$/,'recover original four-digit source character ID');
 assert.equal(item.sourcePak,'OBS.pak','must not substitute other asset archives');
 const match=/^1(\d{3})\.obs$/i.exec(item.originalMember);
 assert.ok(match,'source pack member should use 1NNN.obs identity');
 assert.equal(Number(match[1]),Number(cid),'never map source actor frames to another chessman');
 assert.ok(Array.isArray(item.frames)&&item.frames.length>=2,'native source actor has multiple actual frames');
 const ids=new Set();
 for(const frame of item.frames){
  assert.ok(Number.isInteger(frame.index)&&frame.index>=0);
  assert.ok(!ids.has(frame.index),'same source animation index cannot appear twice');
  ids.add(frame.index);
  assert.match(frame.url,/^\.\/original\/OBS\/(?:bulk\/)?[\w-]+\.png$/);
  const rel=frame.url.replace(/^\.\//,'');
  const full=path.resolve(root,rel);
  assert.ok(full.startsWith(path.join(root,'original/OBS')+path.sep),'source path must remain inside OBS');
  assert.ok(fs.existsSync(full),'missing recovered source frame '+frame.url);
  assert.ok(!used.has(rel),'source frame re-used under another chessman');
  used.add(rel);
  const bytes=fs.readFileSync(full);
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  const width=bytes.readUInt32BE(16),height=bytes.readUInt32BE(20);
  assert.equal(width,frame.width,'native OBS width must not be stretched/re-encoded');
  assert.equal(height,frame.height,'native OBS height must not be stretched/re-encoded');
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),frame.sha256,
   'frame PNG bytes differ from extracted original source recording');
  assert.ok(Number.isInteger(frame.originX)&&Number.isInteger(frame.originY),
   'pixel placement uses actual native OBS frame origin metadata');
  frames++;total+=bytes.length;
 }
 entries.push({id:cid,member:item.originalMember,frames:item.frames.length});
}
console.log('VERIFIED SOURCE OBS FILE INTEGRITY '+JSON.stringify({
 chessmen:sourceIds.length,frames,bytes:total,examples:entries.slice(0,10),
 rule:'image bytes, indexed original source metadata; pose grouping remains inferred'
}));
