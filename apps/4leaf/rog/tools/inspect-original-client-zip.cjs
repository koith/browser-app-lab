'use strict';
/* Public archival ZIP static inspection ONLY. Download the single listed
 * Internet Archive 4LEAF original client, verify its published SHA1, and
 * list ZIP central directory entries using unzip -Z (NO EXTRACT, NO RUN).
 * Never commit or upload executable bytes: artifact contains JSON ONLY.
 */
const https=require('node:https');
const http=require('node:http');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {createHash}=require('node:crypto');
const {spawnSync}=require('node:child_process');
const EXPECTED_SHA1='86526d89679ae39b85fe9808da97ad871b7888d9';
const MAX_BYTES=90*1024*1024;
const out='original-4leaf-zip-listing.json';
const dest=path.join(os.tmpdir(),'4leaf-2002-preservation-'+process.pid+'.zip');
const link='https://archive.org/download/4leaf/4leaf.zip';
function fetchArchive(url,redirects=0){
 if(redirects>5)return Promise.reject(new Error('archive redirect chain too long'));
 return new Promise((resolve,reject)=>{
  let done=false;const fail=e=>{if(!done){done=true;reject(e)}};
  const mod=url.startsWith('https:')?https:http;
  const req=mod.get(url,{
   headers:{'user-agent':'4LEAF-nonexecuting-preservation-inspector/1.0',
    'accept':'application/zip','accept-encoding':'identity'},
   timeout:65000
  },res=>{
   if([301,302,303,307,308].includes(res.statusCode)){
    const location=res.headers.location;
    res.resume();
    if(!location)return fail(new Error('missing redirect target'));
    try{
     fetchArchive(new URL(location,url).href,redirects+1).then(resolve,fail);
     done=true;
    }catch(e){fail(e)}
    return;
   }
   if(res.statusCode!==200){res.resume();return fail(new Error('HTTP '+res.statusCode))}
   const length=Number(res.headers['content-length']||0);
   if(length>MAX_BYTES){res.resume();return fail(new Error('archive too large'))}
   const output=fs.createWriteStream(dest,{flags:'w',mode:0o600});
   let bytes=0;
   res.on('data',chunk=>{
    bytes+=chunk.length;
    if(bytes>MAX_BYTES)res.destroy(new Error('stream exceeded safety cap'));
   });
   res.on('error',fail);output.on('error',fail);
   output.on('finish',()=>{if(!done){done=true;resolve(bytes)}});
   res.pipe(output);
  });
  req.on('timeout',()=>req.destroy(new Error('original ZIP download timeout')));
  req.on('error',fail);
 });
}
async function sha1(file){
 const hash=createHash('sha1');
 for await(const chunk of fs.createReadStream(file))hash.update(chunk);
 return hash.digest('hex');
}
(async()=>{
 const result={source:link,checkedAt:new Date().toISOString(),
  verified:false,originalModelFound:false,archiveOpenedForListing:false,
  executedOriginalBinary:false,redistributedOriginalBinary:false,
  sha1Expected:EXPECTED_SHA1,status:'unavailable',types:{},entries:[]};
 try{
  result.size=await fetchArchive(link);
  result.sha1Actual=await sha1(dest);
  if(result.sha1Actual!==EXPECTED_SHA1)
   throw Error('Archive hash mismatch; refuse to inspect an unverified file');
  result.verified=true;
  const proc=spawnSync('unzip',['-Z','-1',dest],{
   encoding:'utf8',timeout:14000,maxBuffer:4*1024*1024
  });
  if(proc.error||proc.status!==0)
   throw Error('zip central directory unavailable: '+String(proc.error||proc.stderr).slice(0,220));
  const paths=proc.stdout.trim().split(/\r?\n/).filter(Boolean);
  result.archiveOpenedForListing=true;
  result.total=paths.length;
  result.entries=paths.slice(0,3000).map(name=>({
   name,extension:(name.match(/\.([^.\/]+)$/)?.[1]||'dir').toLowerCase()}));
  for(const entry of result.entries)
   result.types[entry.extension]=(result.types[entry.extension]||0)+1;
  result.potentialAnimationResources=result.entries.filter(f=>/\.(pak|mve|spr|ani|chr|act|bmp|gif|shp|sff|dat)$/i.test(f.name)).slice(0,180);
  result.status='archive-sha1-verified-list-only';
  console.log('Verified 2002 public archive bytes='+result.size+' SHA1='+result.sha1Actual);
  console.log('Static ZIP index entries='+result.total);
  console.log('All archive file EXTENSIONS '+JSON.stringify(result.types));
  for(const item of result.potentialAnimationResources)
   console.log('POTENTIAL_ORIGINAL_BINARY '+item.name);
  console.log('No installation, extraction, sprite claim or redistribution performed.');
 }catch(e){
  result.status='unavailable-or-unverified';
  result.error=String(e?.message||e);
  console.log('Source archive inspection blocked: '+result.error);
 }
 fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');
 try{fs.unlinkSync(dest)}catch{}
 console.log('4LEAF_STATIC_ZIP_INSPECTION '+JSON.stringify({
  status:result.status,entries:result.total||0,verified:result.verified,
  candidateCount:result.potentialAnimationResources?.length||0
 }));
})().catch(e=>{console.error('Research script error',e);process.exitCode=1});
