/* Regression: independent decoded scores never establish same-photo identity. */
'use strict';
const assert=require('node:assert/strict');
for(const model of ['yui','mimmi']){
 const q=require('../'+model+'-gallery/image-quality.js');
 const sha=n=>n.repeat(64);
 const original={sha256:sha('a'),visual_quality:{method:'decoded-pixel-v1',confidence:'measured',photo_sha256:sha('a'),score:30}};
 const unrelated={sha256:sha('b'),visual_quality:{method:'decoded-pixel-v1',confidence:'measured',photo_sha256:sha('b'),score:98}};
 assert.equal(q.preferred(original,unrelated),original,'unrelated high score must not replace original');
 const paired={...unrelated,visual_quality:{...unrelated.visual_quality,method:'paired-decoded-pixel-v1',candidate_sha256:sha('b'),compared_to_sha256:sha('a'),same_photo_verified:true,confidence:'measured',relation:'higher'}};
 assert.equal(q.preferred(original,paired),paired,'verified higher-quality same-photo edition may replace');
 const comparable={...paired,watermark_status:'absent_verified',visual_quality:{...paired.visual_quality,relation:'comparable'}};
 const marked={...original,watermark_status:'present_verified'};
 assert.equal(q.preferred(marked,comparable),comparable,'verified comparable clean version wins');
 const wrongPair={...paired,visual_quality:{...paired.visual_quality,compared_to_sha256:sha('c')}};
 assert.equal(q.preferred(original,wrongPair),original,'wrong SHA pair cannot replace');
}
console.log('GALLERY_SAME_PHOTO_QUALITY_GUARD_PASS');
