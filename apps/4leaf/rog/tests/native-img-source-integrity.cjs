'use strict';
/* Immutable 2002 Dice/IMG.pak 2D source artifact integrity.
 * Every original UI PNG must byte-for-byte match the strict decoded SHA
 * registered from the SHA1-verified 4leaf original client installer.
 * Neither these source SPRs nor this audit recovers the original MVE 3D die.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const manifest=JSON.parse(fs.readFileSync(
 path.join(root,'original/SourceSPRExtra/manifest.json'),'utf8'));
assert.equal(manifest.original3DDiceMeshRecovered,false,
 '2D original GUI sprites are not the missing 2004 physical dice mesh');
assert.equal(manifest.classifiedNative2DOnly,true);
const entries=Object.entries(manifest.sprites);
assert.equal(entries.length,12,'12 additional genuine IMG.pak UI members');
let total=0;
for(const [member,sprite] of entries){
 assert.equal(sprite.nativeFrameCount,sprite.frames.length,
  'source frame count lost '+member);
 for(const frame of sprite.frames){
  const rel=frame.url.replace(/^\.\//,'');
  assert.ok(rel.startsWith('original/SourceSPRExtra/'),'no arbitrary assets in original source manifest');
  const data=fs.readFileSync(path.join(root,rel));
  assert.equal(data.subarray(0,8).toString('hex'),'89504e470d0a1a0a',
   'not a PNG recovered from original strict palette decoder: '+rel);
  assert.equal(data.readUInt32BE(16),frame.width,'native pixel width drift '+rel);
  assert.equal(data.readUInt32BE(20),frame.height,'native pixel height drift '+rel);
  assert.equal(crypto.createHash('sha256').update(data).digest('hex'),frame.sha256,
   'SHA mismatch: original Dice/IMG.pak sprite modified after recovery '+rel);
  assert.ok(frame.originalOpaquePixels>0,'original source must contain visible pixels '+rel);
  total++;
 }
}
assert.equal(total,100,'100 original GUI PNG frames recovered');
const battle=manifest.sprites['winBattle.spr'];
assert.deepEqual(battle.frames.map(f=>[f.width,f.height]),[[222,42],[355,113]],
 'actual original two-podium plus native BATTLE heading dimensions');
assert.deepEqual(manifest.sprites['winAbility.spr'].frames[0]&&
 [manifest.sprites['winAbility.spr'].frames[0].width,
  manifest.sprites['winAbility.spr'].frames[0].height],[330,284]);
console.log('ORIGINAL 2002 IMG SOURCE 100 PNG SHA256 AND DIMENSIONS PASS',
 JSON.stringify({members:entries.length,frames:total,
  original3DDiceMeshRecovered:false,sourceSHA256:manifest.sourceSHA256,
  battle: battle.frames.map(f=>[f.width,f.height])}));
