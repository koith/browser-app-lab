/* Merge actually saved photo records by file SHA, not by reused display number.
 * Preserve the real original/vault number when assigning a distinct display
 * number, so a recovered photo never points to another physical file.
 * Source-only and unverified URLs are excluded by each gallery's validImages().
 */
'use strict';
window.SavedGalleryPhotoUnion=(()=>{
 function join(sources){
  const albums=new Map();
  const shaPositionByAlbum=new Map();
  for(const group of sources){
   if(!Array.isArray(group))throw new TypeError('Expected saved album records');
   for(const album of group){
    if(!album||typeof album.id!=='string'||!Array.isArray(album.images))
     throw new TypeError('Malformed saved album');
    if(!albums.has(album.id)){
     albums.set(album.id,{...album,images:[],expected:album.expected??null});
     shaPositionByAlbum.set(album.id,new Map());
    }
    const result=albums.get(album.id);
    const count=Number(album.expected)||0;
    if(count>(Number(result.expected)||0))result.expected=count;
    for(const photo of album.images){
     if(!photo||!/^[a-f0-9]{64}$/.test(photo.sha256||''))continue;
     const known=shaPositionByAlbum.get(album.id).get(photo.sha256);
     if(known!==undefined){
      const previous=result.images[known];
      // Byte-identical replicas do not add a photo. Keep the server-verified
      // original route over a static lower-quality/unaudited route for QA.
      if(photo.ownerAlbum&&!previous.ownerAlbum){
       result.images[known]={...previous,...photo,
        storageNumber:photo.storageNumber??photo.number};
      }
      continue;
     }
     const copy={...photo};
     if(copy.ownerAlbum||copy.vaultAlbum)
      copy.storageNumber=copy.storageNumber??copy.number;
     shaPositionByAlbum.get(album.id).set(copy.sha256,result.images.length);
     result.images.push(copy);
    }
   }
  }
  for(const result of albums.values()){
   const photos=result.images;
   let next=Math.max(0,...photos.map(p=>Number.isSafeInteger(p.number)&&p.number>0?p.number:0));
   const seenNumbers=new Set();
   for(const photo of photos){
    if(!Number.isSafeInteger(photo.number)||photo.number<=0||seenNumbers.has(photo.number))
     photo.number=++next;
    seenNumbers.add(photo.number);
   }
   photos.sort((a,b)=>a.number-b.number);
  }
  return [...albums.values()];
 }
 return Object.freeze({join});
})();
