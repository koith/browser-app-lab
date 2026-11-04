'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
for(const model of ['mimmi','yui']){
 const source=fs.readFileSync(path.join(__dirname,'..',model+'-gallery','index.html'),'utf8');
 // A fresh deep link must be represented in the base replaceState, not
 // followed by a second pushState to the same photo.
 const base="const state={"+model+":true,depth:0,mode:q.get('view')||'albums',publisher:q.get('publisher'),album:id,photo:q.get('photo'),fromPhotos:q.get('from')==='photos',scroll:0};";
 assert.ok(source.includes(base),model+' initial deep-link route preserves photo');
 assert.ok(source.includes("history.replaceState(state,'',routeURL(state));applyRoute(state);"),
   model+' direct deep-link must use only one history entry');
 assert.ok(!source.includes("applyRoute(state);if(q.get('photo'))"),
   model+' old duplicate navigation call remains');
 assert.match(source,/function closeViewer\(\)\{if\(history\.state\?\./);
 assert.match(source,/function goBack\(\)\{if\(history\.state\?\./);
 const start=source.indexOf('function routeFromLocation(){');
 const stop=source.indexOf("window.addEventListener('popstate'",start);
 assert.ok(start>=0&&stop>start,model+' fallback router missing');
 const saved={};
 const context={
  location:{hash:'#album=album-1&photo=7&view=photos&from=photos&publisher=custom'},
  URLSearchParams,canonicalId:x=>x,
  window:{addEventListener:(name,fn)=>{saved[name]=fn}},
  history:{state:null},
  catalog:[{id:'album-1'}],
  applyRoute:state=>{saved.last=state}
 };
 vm.createContext(context);
 vm.runInContext(source.slice(start,source.indexOf("$('prev').onclick",stop)),context);
 assert.equal(typeof saved.popstate,'function');
 assert.equal(typeof saved.pageshow,'function');
 saved.popstate();
 assert.equal(saved.last.album,'album-1');
 assert.equal(saved.last.photo,'7');
 assert.equal(saved.last.mode,'photos');
 assert.equal(saved.last.fromPhotos,true);
 saved.last=null;saved.pageshow({persisted:true});
 assert.equal(saved.last.photo,'7');
 saved.last=null;saved.pageshow({persisted:false});
 assert.equal(saved.last,null,'non-restored pageshow should not remount gallery');
 context.history.state={[model]:true,album:'other',photo:2,mode:'albums'};
 saved.popstate();
 assert.equal(saved.last.album,'other','typed in-memory state wins over URL fallback');
 console.log('GALLERY_DEEP_LINK_NO_DUPLICATE_BACK_STACK_AND_SAFARI_RESTORE_PASS',model);
}
