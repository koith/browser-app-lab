'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'..','mimmi-gallery','index.html'),'utf8');
const begin=html.indexOf("document.addEventListener('error',e=>{");
const end=html.indexOf('\nlet catalog=',begin);
assert.ok(begin>=0&&end>begin,'Mimmi stored image error handler not found');
const handlers={};
const marked=[];
let replayCount=0;
class Image {
 constructor(){
  this.dataset={owner:'owner:work:1',ownerVariant:'original'};
  this.src='https://gateway.example/api/media/work/1/original';
  this.hidden=false;
  this.isConnected=true;
 }
 closest(){return this.container;}
 getAttribute(name){return name==='src'?this.src:null;}
 removeAttribute(){throw Error('denied cover must not replay same URL');}
}
const container={classList:{add:x=>marked.push(x)}};
const img=new Image();img.container=container;
const ctx={
 document:{addEventListener:(name,cb)=>handlers[name]=cb},
 HTMLImageElement:Image,ownerPhotoIndex:new Map(),
 recoverSavedCover:()=>false,
 registerImageHealth:(url,ok)=>{if(ok)throw Error('denial marked successful');marked.push(url)},
 requestAnimationFrame:()=>{replayCount++},
 MimmiPrivate:{asset:()=>{throw Error('already attempted owner original')}}
};
vm.createContext(ctx);
vm.runInContext(html.slice(begin,end),ctx);
assert.equal(typeof handlers.error,'function');
handlers.error({target:img});
assert.equal(replayCount,0,'no second/third remote request via changed referrer');
assert.equal(img.hidden,true);
assert.ok(marked.includes('broken-source'));
assert.ok(marked.includes(img.src));
assert.ok(!Object.hasOwn(img.dataset,'sourceRetry'));
console.log('GALLERY_MIMMI_DENIED_COVER_NO_REFERRER_REPLAY_PASS');
