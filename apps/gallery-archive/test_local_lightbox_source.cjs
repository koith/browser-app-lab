'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

async function exercise(model,withLocal) {
 const html=fs.readFileSync(path.join(__dirname,'..',model+'-gallery','index.html'),'utf8');
 const start=html.indexOf('function showViewer(){'),end=html.indexOf('function hideViewer(){',start);
 assert.ok(start>=0&&end>start,model+' viewer source missing');
 const photo={albumId:'safe',ownerAlbum:'safe',number:1,name:'Saved',
   url:'owner:safe:1',sha256:'a'.repeat(64),bytes:123000,width:800,height:1200,preview:true};
 const local={...photo,url:'stored-albums/safe/1.webp'};
 const requests=[];
 const original={href:null,removeAttribute(name){if(name==='href')this.href=null}};
 const frame={dataset:{},style:{}};
 const image={parentElement:frame,hidden:true,naturalWidth:800,
   removeAttribute(name){if(name==='src')this.src=null;},
   setAttribute(){}};
 const elements={
  full:image,'media-status':{textContent:''},original,
  position:{textContent:''}
 };
 const ctx={viewerList:[photo],viewerIndex:0,viewerGeneration:0,
   layoutViewer(){},
   exactSavedViewerCopy:()=>withLocal?local:null,
   $:id=>elements[id],
   registerImageHealth(){},
   imageFailureText:()=> 'Saved photo unavailable',
   requestAnimationFrame:cb=>cb(),
   MimmiPrivate:{asset:async (p,variant)=>{
     requests.push(variant);
     return 'https://owner.test/api/mimmi/'+variant;
   }},
   YuiPrivate:{asset:async (p,variant)=>{
     requests.push(variant);
     return 'https://owner.test/api/yui/'+variant;
   }},
   PhotoVault:{asset:async()=>{throw Error('not used')}}
 };
 vm.createContext(ctx);
 vm.runInContext(html.slice(start,end)+';globalThis.show=showViewer',ctx);
 ctx.show();
 const settle=async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();};
 if(withLocal){
  assert.equal(image.src,local.url,model+' uses committed saved local bytes first');
  assert.equal(original.href,local.url,model+' exposes same-byte local original');
  assert.deepEqual(requests,[],model+' does not wake remote for local image');
  image.onerror();
  await settle();
  assert.deepEqual(requests,['original'],
    model+' only uses remote original after local decode failure');
 }else{
  await settle();
  assert.deepEqual(requests,['original'],
    model+' still uses remote if exact local byte match absent');
 }
 assert.match(image.src||'',/\/original$/,
   model+' original is recovered after static copy error');
 image.onerror();
 await settle();
 assert.deepEqual(requests,['original','preview'],
   model+' remotely denied original falls back to preview once');
 assert.match(image.src||'',/\/preview$/,
   model+' preview URL must replace denied original');
 image.onerror();
 await settle();
 assert.deepEqual(requests,['original','preview'],
   model+' must not replay denied private original with referrer variants');
 console.log('GALLERY_EXACT_LOCAL_LIGHTBOX_REMOTE_FALLBACK_PASS',model,withLocal?'exact-SHA':'remote-only');
}
(async()=>{
 for(const model of ['mimmi','yui']){
  await exercise(model,true);
  await exercise(model,false);
 }
})().catch(error=>{console.error(error);process.exitCode=1});
