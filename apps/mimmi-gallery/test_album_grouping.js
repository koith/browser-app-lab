'use strict';
const assert=require('node:assert/strict');
const {combine}=require('./album-grouping.js');
function media(id,n,sha,privateMedia=true){
 return {number:n,sha256:sha.repeat(64),bytes:10000,width:800,height:1200,
         ...(privateMedia?{ownerAlbum:id,url:'owner:'+id+':'+n}:{url:'stored-albums/'+id+'/'+n+'.jpg'})};
}
const full={id:'djawa-full',title:'Mimmi Original Photobook',
 images:Array.from({length:91},(_,i)=>media('djawa-full',i+1,(i%10).toString()))};
const preview={id:'v2ph-short',title:'Mimmi Original Photobook',
 images:Array.from({length:10},(_,i)=>media('v2ph-short',i+1,String.fromCharCode(97+i)))};
const other={id:'not-the-same-work',title:'[AI Enhanced] Mimmi Original Photobook',
 images:[media('not-the-same-work',1,'e')]};
{
 const result=combine([full,preview,other],{'v2ph-short':'djawa-full'});
 assert.equal(result.albums.length,2);
 assert.equal(result.beforeCount,102);
 assert.equal(result.afterCount,102);
 const joined=result.albums.find(a=>a.id==='djawa-full');
 assert.equal(joined.images.length,101);
 assert.equal(joined.variantPreviewCount,10);
 const alias=joined.images.filter(p=>p.isAlternatePreview);
 assert.equal(alias.length,10);
 assert.deepEqual(alias.map(p=>p.number),[92,93,94,95,96,97,98,99,100,101]);
 assert.deepEqual(alias.map(p=>p.storageNumber),[1,2,3,4,5,6,7,8,9,10]);
 assert.equal(alias[0].url,'owner:v2ph-short:1');
 assert.equal(alias[0].originalAlbumId,'v2ph-short');
}
{
 const duplicate={...preview,images:[{...preview.images[0],sha256:full.images[0].sha256}]};
 const result=combine([full,duplicate],{'v2ph-short':'djawa-full'});
 assert.equal(result.afterCount,full.images.length);
 assert.equal(result.verifiedMappings[0].identicalDuplicates,1);
}
{
 const result=combine([preview,other],{'v2ph-short':'not-the-same-work'});
 assert.equal(result.albums.length,2); // AI vs non-AI cannot merge.
}
{
 const result=combine([preview],{'v2ph-short':'djawa-full'});
 assert.equal(result.albums.length,1); // no full saved album: retain small preview.
}
console.log('MIMMI_FULL_ALBUM_GROUPING_NO_LOST_IMAGE_BYTES_AND_ORIGINAL_MEDIA_NUMBERS_PASS');
