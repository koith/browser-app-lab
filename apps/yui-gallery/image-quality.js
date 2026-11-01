/* Compare alternative saved versions of the SAME album position.
 * Dimensions are not proof of optical resolution; bytes are evidence, not an
 * oracle. Explicit watermarked source and verified original status take
 * precedence, and suspicious upscale ratios are penalized conservatively.
 * Never rename, drop, or alter SHA-verified physical archive bytes here.
 */
(function(root){
'use strict';
const pixels=p=>Math.max(0,Number(p?.width)||0)*Math.max(0,Number(p?.height)||0);
const bytes=p=>Math.max(0,Number(p?.bytes)||0);
function format(p){const s=String(p?.source_url||p?.url||p?.extension||p?.key||'').split('?')[0].toLowerCase();return /\.webp$/.test(s)?'webp':/\.png$/.test(s)?'png':'jpeg'}
function watermarked(p){return /pixibb|watermarked|watermark|third.party.public.watermarked/i.test([p?.quality,p?.source_url,p?.original_source_url,p?.origin_url].filter(Boolean).join(' '))}
function original(p){return p?.publisher_original_verified===true&&p?.ai_enhanced!==true}
function ai(p){return p?.ai_enhanced===true||/ai.enhanced|ai.보정/i.test(String(p?.quality||''))}
function detail(p){
 const px=pixels(p),size=bytes(p);
 const floor=format(p)==='webp'?0.055:format(p)==='png'?0.12:0.085;
 return Math.min(px,size/floor);
}
function preferred(previous,candidate){
 if(!previous)return candidate;
 if(!candidate)return previous;
 if(previous.sha256&&previous.sha256===candidate.sha256)
  return (candidate.ownerAlbum||candidate.vaultAlbum)&&!(previous.ownerAlbum||previous.vaultAlbum)?candidate:previous;
 const prevPx=pixels(previous),candPx=pixels(candidate);
 if(!prevPx||!candPx)return candPx>prevPx?candidate:previous;
 const prevWater=watermarked(previous),candWater=watermarked(candidate);
 const usable=p=>Math.min(Number(p.width)||0,Number(p.height)||0)>=650;
 // The annotated PixiBB website preview is never the 'original' of a
 // similarly usable unwatermarked saved photo, even when upscaled to 4K.
 if(prevWater!==candWater){
  if(prevWater&&usable(candidate))return candidate;
  if(candWater&&usable(previous))return previous;
 }
 if(original(previous)!==original(candidate)){
  if(original(candidate)&&usable(candidate))return candidate;
  if(original(previous)&&usable(previous))return previous;
 }
 if(ai(previous)!==ai(candidate)){
  if(!ai(candidate)&&usable(candidate))return candidate;
  if(!ai(previous)&&usable(previous))return previous;
 }
 const prevDetail=detail(previous),candDetail=detail(candidate);
 // A >= 70% pixel jump without a comparable byte/detail increase is a
 // probable resample, not guaranteed extra optical information.
 if(candPx>=prevPx*1.7&&bytes(candidate)<=bytes(previous)*1.10&&!original(candidate))return previous;
 if(prevPx>=candPx*1.7&&bytes(previous)<=bytes(candidate)*1.10&&!original(previous))return candidate;
 if(candDetail>prevDetail*1.15)return candidate;
 if(prevDetail>candDetail*1.15)return previous;
 // Comparable effective detail: retain better evidence of source bits,
 // without assuming PNG and JPEG file sizes are directly comparable.
 if(format(previous)===format(candidate)){
  if(bytes(candidate)>bytes(previous)*1.25)return candidate;
  if(bytes(previous)>bytes(candidate)*1.25)return previous;
 }
 if(candPx>prevPx*1.12)return candidate;
 if(prevPx>candPx*1.12)return previous;
 return (candidate.ownerAlbum||candidate.vaultAlbum)&&!(previous.ownerAlbum||previous.vaultAlbum)?candidate:previous;
}
const api={preferred,detail,watermarked,original,pixels};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.GalleryPhotoQuality=api;
})(typeof window==='undefined'?globalThis:window);
