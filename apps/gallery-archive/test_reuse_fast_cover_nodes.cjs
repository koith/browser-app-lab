'use strict';
/* Execute each gallery's real first-paint DOM handoff with fake image nodes.
 * The same SHA and same stored URL must preserve the in-flight HTML <img>.
 * Every uncertain identity/URL must refuse reuse, never show the wrong photo.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

function element(attrs) {
 const pairs=new Map(Object.entries(attrs));
 return {
  get attributes(){return [...pairs.entries()].map(([name,value])=>({name,value}));},
  dataset:{},
  getAttribute:name=>pairs.get(name)||null,
  setAttribute:(name,value)=>pairs.set(name,value),
  removeAttribute:name=>pairs.delete(name)
 };
}
for(const model of ['mimmi','yui']){
 const html=fs.readFileSync(path.join(__dirname,'..',model+'-gallery','index.html'),'utf8');
 const start=html.indexOf('function adoptFastCoverImages(grid,oldCards){');
 const end=html.indexOf('\nfunction render(){',start);
 assert.ok(start>0&&end>start,model+' must preserve HTML first-paint image elements');
 const source=html.slice(start,end);
 function check({sha='a'.repeat(64),newSha='a'.repeat(64),url='stored-albums/safe/image.jpg',
                 oldUrl='stored-albums/safe/image.jpg'}={}){
  const original=element({src:oldUrl,width:'900',height:'1200',loading:'eager'});
  const replacement=element({src:url,alt:'saved cover',loading:'lazy','data-owner':'owner:safe:1'});
  let swapped=null;
  replacement.replaceWith=img=>{swapped=img};
  const card={dataset:{id:'safe',coverSha:newSha},querySelector:()=>replacement};
  const grid={querySelectorAll:()=>[card]};
  const context={stored:[{id:'safe',images:[{sha256:newSha}]}],
                 validImages:a=>a.images,albumCovers:{}};
  vm.createContext(context);
  vm.runInContext(source+';globalThis.adopt=adoptFastCoverImages',context);
  context.adopt(grid,new Map([['safe',{sha,image:original}]]));
  return {swapped,original};
 }
 const valid=check();
 assert.equal(valid.swapped,valid.original,model+' exact image node must survive');
 assert.equal(valid.original.dataset.fastPreserved,'1');
 assert.equal(valid.original.getAttribute('src'),'stored-albums/safe/image.jpg');
 assert.equal(valid.original.getAttribute('data-owner'),'owner:safe:1','owner original route must survive');
 const after503=check({oldUrl:'stored-albums/safe/image.jpg?gtry=2'});
 assert.equal(after503.swapped,after503.original,model+' must retain same pinned photo after Pages 503 retry');
 assert.equal(after503.original.getAttribute('src'),'stored-albums/safe/image.jpg?gtry=2');
 assert.equal(check({oldUrl:'stored-albums/safe/image.jpg?gtry=5'}).swapped,null,
   'unbounded retry parameter must never qualify for SHA reuse');
 assert.equal(check({oldUrl:'stored-albums/safe/image.jpg?gtry=2&other=1'}).swapped,null,
   'unknown retry parameters must never qualify for SHA reuse');
 assert.equal(check({oldUrl:'stored-albums/other/image.jpg?gtry=2'}).swapped,null,
   'different saved path must not qualify for SHA reuse');
 assert.equal(check({oldUrl:'https://other.example/api/v1/media/a?gtry=2'}).swapped,null,
   'signed or external media must never be normalized into a different photo');
 assert.equal(check({sha:'b'.repeat(64)}).swapped,null,'different selected SHA must not preserve');
 assert.equal(check({url:'stored-albums/safe/another.jpg'}).swapped,null,'different URL must not preserve');
 assert.ok(html.includes('data-cover-sha="'),model+' must disclose actual selected cover SHA on the rendered card');
 assert.ok(html.includes("data-owner-variant=\"local\""),model+' must keep local saved owner cover path');
 assert.ok(!/\n\s*render\(\);\s*\n\s*const raw=location\.hash\.slice/.test(html),
   model+' must not discard prepaint covers with a redundant startup render');
 assert.ok(html.includes("adoptFastCoverImages(grid,fastCovers)"),model+' must use handoff in real render');
 console.log('GALLERY_FAST_COVER_DOM_NODE_IDENTITY_AND_SHA_HANDOFF_PASS',model);
}
