'use strict';
/* PRESERVATION RESEARCH ONLY. Strictly read public Internet Archive METADATA,
 * not download, install or execute any historical Windows binaries.
 * Archive item link is documented in https://clientlover.tistory.com/12 .
 * Missing/unreachable source does not imply the file contains chessmen.
 * NEVER publish private data, redistribute executables or claim model found.
 */
const https=require('node:https');
const {writeFileSync}=require('node:fs');
const url='https://archive.org/metadata/4leaf';
const output=process.env.FOURLEAF_ORIGINAL_ARCHIVE_REPORT||'original-4leaf-client-metadata.json';
function probe(){
 return new Promise((resolve,reject)=>{
  const req=https.get(url,{
   headers:{'user-agent':'4LEAF-historical-preservation-research/1.0 (metadata only)','accept':'application/json'},
   timeout:18000
  },res=>{
   if(res.statusCode!==200){
    res.resume();reject(new Error('HTTP '+res.statusCode));return;
   }
   let length=0,text='';
   res.on('data',buf=>{
    length+=buf.length;
    if(length>1024*1024){req.destroy(new Error('metadata response too large'));return;}
    text+=buf.toString('utf8');
   });
   res.on('end',()=>resolve(JSON.parse(text)));
  });
  req.on('timeout',()=>req.destroy(new Error('archive metadata timeout')));
  req.on('error',reject);
 });
}
(async()=>{
 let report={checkedAt:new Date().toISOString(),
  source:url,provenance:'https://clientlover.tistory.com/12',
  status:'unavailable',historicalVersion:'claimed v0.96d (2002-07-16)',
  originalSpritesVerified:false,archiveExecuted:false,
  redistributesOriginalBinaries:false,files:[]};
 try{
  const data=await probe();
  const files=Array.isArray(data.files)?data.files:[];
  report={...report,status:'metadata-accessible',
   itemId:data.metadata?.identifier||'',
   title:data.metadata?.title||'',
   created:data.created||'',
   totalFiles:files.length,
   files:files.filter(f=>/\.(exe|zip|rar|7z|cab|bin|pak|dmp|tis|spr|ani|chr|mve|gif|bmp|png)$/i.test(f.name||''))
   .map(f=>({name:f.name,size:Number(f.size)||0,sha1:f.sha1||null,
    md5:f.md5||null,format:f.format||'',source:f.source||''}))};
  console.log('4LEAF archive metadata read: '+report.totalFiles+' entries; relevant '+report.files.length);
  for(const f of report.files)console.log('PRESERVATION_CANDIDATE '+JSON.stringify(f));
  console.log('NOT ORIGINAL SPRITE VERIFICATION — no binary downloaded or run');
 }catch(err){
  report.error=String(err?.message||err);
  console.log('4LEAF archive metadata unreachable: '+report.error);
  console.log('This is an UNVERIFIED historic client link, not a reason to invent frames');
 }
 writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 console.log('4LEAF_RESEARCH_RESULT '+JSON.stringify({
  status:report.status,files:report.files.length,
  originalSpritesVerified:false,reportPath:output
 }));
})().catch(error=>{console.error(error);process.exitCode=1});
