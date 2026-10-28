(function(root){
 'use strict';
 const collator=new Intl.Collator('ko',{numeric:true,sensitivity:'base'});
 function compareNames(a,b){return collator.compare(String(a??''),String(b??''))}
 const publicKinds=new Set(['creator_public_photographs','official_event_report','public_editorial_photos','public_board_photographs','public_photographer_portfolio']);
 function key(album,registry,describe){
  if(publicKinds.has(album.collection_kind))return 'public';
  const name=describe(album).publisher.toLocaleLowerCase();
  return registry.publishers.find(p=>p.aliases.some(a=>a.toLocaleLowerCase()===name))?.id||'unknown';
 }
 function groups(albums,registry,describe,images){
  const by=new Map(registry.publishers.map(p=>[p.id,{...p,albums:[]}]));
  by.set('unknown',{id:'unknown',name:'발행처 미확인',logo:null,albums:[]});
  by.set('public',{id:'public',name:'공개 자료',logo:null,albums:[]});
  for(const album of albums){const group=by.get(key(album,registry,describe));group.albums.push(album)}
  return [...by.values()].filter(g=>g.albums.length).map(g=>({...g,viewable:g.albums.filter(a=>images(a).length>0).length})).sort((a,b)=>compareNames(a.name,b.name)||compareNames(a.id,b.id));
 }
 function logo(publisher){
  const asset=publisher.logo;
  return asset?.verified_official===true&&/^publisher-logos\/[a-z0-9-]+\.(?:svg|png|jpe?g|webp|ico)$/.test(asset.path)?asset.path:null;
 }
 const api={key,groups,logo,compareNames};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.MimmiPublishers=api;
})(globalThis);
