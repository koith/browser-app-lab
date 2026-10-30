/* Group explicitly reviewed same-work editions under the largest saved photo set.
 * Never download or fabricate a picture; preserve byte-identical media URLs,
 * SHA and private storage positions. An AI-enhanced edition is NOT its
 * photographic original. All distinct stored preview variants remain viewable.
 */
'use strict';
(function(root){
 function isAI(album){
  return album.ai_enhanced===true||/\bAI\s*(?:Enhanced|보정)\b/i.test(album.title||'');
 }
 function combine(rows,aliases){
  const originalCount=rows.reduce((n,a)=>n+(a.images||[]).length,0);
  const combined=new Map(rows.map(a=>[a.id,{...a,images:(a.images||[]).map(p=>({...p}))}]));
  const verifiedMappings=[];
  for(const [from,to] of Object.entries(aliases||{})){
   if(from===to||typeof from!=='string'||typeof to!=='string')continue;
   const small=combined.get(from),large=combined.get(to);
   if(!small||!large||!Array.isArray(small.images)||!Array.isArray(large.images)
      ||large.images.length<30||large.images.length<small.images.length*2
      ||isAI(small)!==isAI(large))continue;
   const sha=new Set(large.images.map(p=>p.sha256));
   let next=Math.max(0,...large.images.map(p=>Number.isInteger(p.number)?p.number:0));
   let variantAdded=0,identicalDuplicates=0;
   for(const image of small.images){
    if(sha.has(image.sha256)){identicalDuplicates++;continue}
    sha.add(image.sha256);
    // UI routing uses a unique display number; API reads the original number.
    const row={...image,storageNumber:image.storageNumber??image.number,
               originalAlbumId:from,number:++next,isAlternatePreview:true};
    large.images.push(row);variantAdded++;
   }
   large.variantPreviewCount=(large.variantPreviewCount||0)+variantAdded;
   large.matchedSourceEditions=[...(large.matchedSourceEditions||[]),from];
   combined.delete(from);
   verifiedMappings.push({from,to,variantAdded,identicalDuplicates});
  }
  const albums=[...combined.values()];
  const afterCount=albums.reduce((n,a)=>n+(a.images||[]).length,0);
  // Cross-album exact SHA duplicates are removed only within a *verified same work*.
  if(afterCount>originalCount)throw Error('Alias grouping fabricated photographs');
  return {albums,beforeCount:originalCount,afterCount,verifiedMappings};
 }
 root.MimmiAlbumGrouping={combine};
 if(typeof module!=='undefined'&&module.exports)module.exports={combine};
})(typeof window==='undefined'?globalThis:window);
