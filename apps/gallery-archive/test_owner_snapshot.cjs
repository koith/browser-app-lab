'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 for(const model of ['yui','mimmi']){
  const ctx={window:{},location:{hostname:'koith.github.io',pathname:'/'},URL};vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..',model+'-gallery','owner-media.js'),'utf8'),ctx);
  const api=ctx.window[model==='yui'?'YuiPrivate':'MimmiPrivate'];
  const row=(number,width,sha)=>({number,width,height:width,sha256:sha.repeat(64),bytes:5000,ownerAlbum:'sample'});
  const current=[{id:'sample',images:[row(1,3008,'a'),row(2,1800,'b')]}];
  const incoming=[{id:'sample',images:[row(1,800,'c'),row(3,2000,'d')]}];
  const combined=api.reconcile(current,incoming);
  assert.equal(combined[0].images.length,3);assert.equal(combined[0].images[0].width,3008);
  // On public GitHub Pages a missing/unavailable Cloudflare config must
  // fail closed. It must NOT silently return the retired Render URL.
  await assert.rejects(api.asset(combined[0].images[0]),
    /GALLERY_REPLICA_TEMPORARILY_UNAVAILABLE/);
  await assert.rejects(api.renew(combined[0].images[0]),
    /GALLERY_REPLICA_TEMPORARILY_UNAVAILABLE/);
  assert.equal(api.importZip,undefined);
 }
 console.log('OWNER_SNAPSHOT_NO_PHOTO_LOSS_OR_RESOLUTION_REGRESSION_PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
