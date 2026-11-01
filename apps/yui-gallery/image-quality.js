/* Gallery replacement order:
 * (1) PROVEN actual decoded-pixel visual quality for the SAME photograph;
 * (2) a watermark-free edition ONLY when visual quality is comparable;
 * (3) verified origin/storage as a non-visual fallback.
 *
 * Width, height, file size and file-type are NOT optical quality scores.
 * Missing evidence is unknown, not an invitation to replace a good file.
 * All versions remain in storage; this only decides which variant is shown.
 */
(function(root){
'use strict';
function watermarked(p){
 return p?.watermarked===true ||
  /pixibb|watermarked|watermark|third.party.public.watermarked/i.test(
   [p?.quality,p?.source_url,p?.original_source_url,p?.origin_url].filter(Boolean).join(' '));
}
function original(p){return p?.publisher_original_verified===true && p?.ai_enhanced!==true}
function pixels(p){return Math.max(0,Number(p?.width)||0)*Math.max(0,Number(p?.height)||0)}
function score(p){
 const q=p?.visual_quality;
 if(!q||q.method!=='decoded-pixel-v1'||q.confidence!=='measured'||
    typeof q.score!=='number'||!Number.isFinite(q.score)||q.score<0||q.score>100)return null;
 return q.score;
}
function paired(a,b){
 const qa=a?.visual_quality;
 if(qa?.method!=='paired-decoded-pixel-v1'||qa.compared_to_sha256!==b?.sha256||
    qa.same_photo_verified!==true||qa.confidence!=='measured')return null;
 return ['higher','lower','comparable'].includes(qa.relation)?qa.relation:null;
}
function preferred(previous,candidate){
 if(!previous)return candidate;
 if(!candidate)return previous;
 // A byte-identical file has exactly the same quality and watermark.
 if(previous.sha256&&previous.sha256===candidate.sha256)
  return (candidate.ownerAlbum||candidate.vaultAlbum)&&!(previous.ownerAlbum||previous.vaultAlbum)?candidate:previous;

 // Stronger evidence: two actual decoded files compared as the same scene.
 const change=paired(candidate,previous),reverse=paired(previous,candidate);
 if(change==='higher'||reverse==='lower')return candidate;
 if(change==='lower'||reverse==='higher')return previous;
 const verifiedTie=change==='comparable'||reverse==='comparable';

 // Absolute, calibrated decoded-pixel measurements are usable only in
 // matched methods. No megapixel, bytes or watermark scoring here.
 const a=score(previous),b=score(candidate);
 if(a!==null&&b!==null){
  if(b-a>=8)return candidate;
  if(a-b>=8)return previous;
 }
 const qualityTie=verifiedTie||(a!==null&&b!==null&&Math.abs(a-b)<8);
 // A clean blurry edit NEVER beats a visibly better watermarked edition.
 // When quality has not been evaluated, keep the known variant for review.
 if(qualityTie&&watermarked(previous)!==watermarked(candidate))
  return watermarked(previous)?candidate:previous;
 if(qualityTie&&original(previous)!==original(candidate))
  return original(candidate)?candidate:previous;
 // Inconclusive or unassessed: do not guess from dimensions, encoded bytes
 // or mere absence of watermark. Preserve the existing version.
 return previous;
}
const api={preferred,score,paired,watermarked,original,pixels};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.GalleryPhotoQuality=api;
})(typeof window==='undefined'?globalThis:window);
