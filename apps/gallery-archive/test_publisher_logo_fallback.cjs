'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const officialYuiRegistry=JSON.parse(fs.readFileSync(
 path.join(__dirname,'..','yui-gallery','publishers.json'),'utf8'));
const officialBrands=new Map(officialYuiRegistry.publishers.map(p=>[p.id,p]));
for(const model of ['mimmi','yui']){
 const root=path.resolve(__dirname,'..',model+'-gallery');
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 const registry=JSON.parse(fs.readFileSync(path.join(root,'publishers.json'),'utf8'));
 const publisher=require(path.join(root,'publishers.js'));
 let usable=0,unverified=0;
 for(const item of registry.publishers){
  const link=publisher.logo(item);
  if(!link){unverified++;continue;}
  usable++;
  assert.equal(item.logo.verified_official,true,model+' logo verification');
  assert.ok(['official_publisher_logo','official_site_logo','official_store_logo']
    .includes(item.logo.asset_role),'wrong logo role '+item.id);
  const candidate=path.resolve(root,link);
  const allow=path.resolve(__dirname,'..','yui-gallery','publisher-logos')+path.sep;
  const local=path.join(root,'publisher-logos')+path.sep;
  assert.ok(candidate.startsWith(allow)||candidate.startsWith(local),
    'reject logo escaping approved gallery folder: '+link);
  const buf=fs.readFileSync(candidate);
  assert.ok(buf.length>=100,'invalid empty published image '+link);
  // A valid PNG header is NOT sufficient evidence of the right publisher.
  // Bind each verified first-party brand identity to its exact committed bytes.
  const official=officialBrands.get(item.id);
  const expectedSHA=item.logo.sha256||official?.logo?.sha256;
  const expectedBytes=item.logo.bytes||official?.logo?.bytes;
  assert.match(expectedSHA||'',/^[a-f0-9]{64}$/,
    model+' '+item.id+' missing official logo SHA');
  assert.ok(Number.isSafeInteger(expectedBytes)&&expectedBytes>100,
    model+' '+item.id+' missing official file byte count');
  assert.equal(buf.length,expectedBytes,
    model+' '+item.id+' unexpected official logo size');
  const actualSHA=crypto.createHash('sha256').update(buf).digest('hex');
  assert.equal(actualSHA,expectedSHA,
    model+' '+item.id+' registered publisher logo has swapped bytes');
  if(model==='mimmi'){
    assert.ok(official?.logo?.verified_official,
      'cross-gallery brand must refer to same verified publisher '+item.id);
    assert.equal(path.resolve(root,link),
      path.resolve(__dirname,'..','yui-gallery',official.logo.path),
      'shared publisher logo points at the wrong branded image');
  }
  const ext=path.extname(candidate).toLowerCase();
  if(ext==='.png') assert.equal(buf.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  else if(['.jpg','.jpeg'].includes(ext)) assert.equal(buf.subarray(0,2).toString('hex'),'ffd8');
  else if(ext==='.svg') assert.match(buf.toString('utf8'),/<svg[\s>]/);
  else if(ext==='.ico') assert.equal(buf.subarray(0,4).toString('hex'),'00000100');
  else if(ext==='.webp') assert.equal(buf.subarray(0,4).toString(),'RIFF');
  else throw Error('unexpected format '+ext);
 }
 const start=html.indexOf('function publisherCard(group){');
 const end=html.indexOf('function openPublisher(',start);
 assert.ok(start>0 && end>start,'required publisherCard');
 const handlers=[];
 class Image{
  closest(selector){assert.equal(selector,'.publisher');return this.parent;}
  remove(){this.removed=true;}
 }
 const context={
  MimmiPublishers:{logo:()=> 'publisher-logos/djawa.png'},
  YuiPublishers:{logo:()=> 'publisher-logos/djawa.png'},
  esc:s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'),
  HTMLImageElement:Image,
  document:{addEventListener:(event,cb,capture)=>handlers.push({event,cb,capture})}
 };
 vm.createContext(context);
 vm.runInContext(html.slice(start,end)+';globalThis.card=publisherCard;',context);
 const input={id:'djawa',name:'DJAWA',logo:{theme:'light'},albums:[{}],viewable:1};
 const markup=context.card(input);
 assert.match(markup,/publisher-wordmark" hidden/,'fallback starts hidden');
 assert.match(markup,/publisher-logos\/djawa\.png/,'verified logo displayed normally');
 assert.equal(handlers.length,1);
 assert.equal(handlers[0].event,'error');
 assert.equal(handlers[0].capture,true);
 const fallback={hidden:true};
 const image=new Image();
 image.parent={querySelector:selector=>selector==='.publisher-wordmark'?fallback:null};
 handlers[0].cb({target:image});
 assert.equal(fallback.hidden,false,'broken logo replaced by name');
 assert.equal(image.removed,true);
 handlers[0].cb({target:{}});
 const htmlNoLogo=context.card({...input,name:'Unverified',id:'other'});
 assert.match(htmlNoLogo,/publisher-wordmark/);
 console.log('GALLERY_PUBLISHER_LOGO_BYTES_AND_ERROR_FALLBACK_PASS',model,
   {usable,unverified});
}
