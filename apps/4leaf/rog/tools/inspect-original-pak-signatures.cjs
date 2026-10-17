'use strict';
/* 2002 4LEAF PAK forensic signature inventory. Executes ONLY vetted modern
 * static index utilities (unzip/unshield) against a publicly archived,
 * SHA1-verified 2002 Windows client; NEVER executes ANY original EXE/DLL.
 * Installer bytes and copyrighted PAK content remain in runner tmp and are
 * DELETED after inspection. Only hashes, sizes and 96 signature bytes are
 * recorded, not PAK contents or frames. No redistribution.
 */
const https=require('node:https');
const http=require('node:http');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {createHash}=require('node:crypto');
const {loadPakIndex}=require('./original-pak-index.cjs');
const {inspect:inspectOriginalMembers}=require('./inspect-original-member-signatures.cjs');
const source='https://archive.org/download/4leaf/4leaf.zip';
const expected='86526d89679ae39b85fe9808da97ad871b7888d9';
const reportPath='original-4leaf-pak-signatures.json';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'4leaf-original-static-'));
const zipPath=path.join(temp,'4leaf.zip');
const bytesMax=90*1024*1024;
async function download(url,hop=0){
 if(hop>6)throw Error('archive redirect limit');
 await new Promise((resolve,reject)=>{
  let finished=false;const fail=e=>{if(!finished){finished=true;reject(e)}};
  const req=(url.startsWith('https:')?https:http).get(url,{
   headers:{'user-agent':'4LEAF-original-file-signature-preservation/1.0'},timeout:65000
  },res=>{
   if([301,302,303,307,308].includes(res.statusCode)){
    const next=res.headers.location;
    res.resume();if(!next){fail(Error('redirect missing'));return}
    finished=true;
    download(new URL(next,url).href,hop+1).then(resolve,reject);return;
   }
   if(res.statusCode!==200){res.resume();fail(Error('download HTTP '+res.statusCode));return}
   let total=0;
   const stream=fs.createWriteStream(zipPath,{mode:0o600,flags:'w'});
   res.on('data',b=>{total+=b.length;if(total>bytesMax)res.destroy(Error('size cap'))});
   res.on('error',fail);stream.on('error',fail);
   stream.on('finish',()=>{if(!finished){finished=true;resolve()}});
   res.pipe(stream);
  });
  req.on('timeout',()=>req.destroy(Error('download timeout')));
  req.on('error',fail);
 });
}
function digest(filename,alg='sha256'){
 return new Promise(async resolve=>{
  const h=createHash(alg);
  for await(const part of fs.createReadStream(filename))h.update(part);
  resolve(h.digest('hex'));
 });
}
function exec(file,args,stdoutFile=null){
 let fd=null;
 if(stdoutFile)fd=fs.openSync(stdoutFile,'w',0o600);
 const result=spawnSync(file,args,{
  encoding:'utf8',timeout:85000,maxBuffer:2*1024*1024,
  stdio:fd===null?'pipe':['ignore',fd,'pipe']
 });
 if(fd!==null)fs.closeSync(fd);
 if(result.error||result.status!==0)throw Error(file+' exit '+result.status+' : '+
  String(result.error?.message||result.stderr||'').slice(0,280));
 return result.stdout||'';
}
function allFiles(directory){
 const found=[];const dirs=[directory];
 while(dirs.length){
  const dir=dirs.pop();
  for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
   const full=path.join(dir,entry.name);
   if(entry.isDirectory())dirs.push(full);
   else if(entry.isFile())found.push(full);
  }
 }
 return found;
}
(async()=>{
 const report={checkedAt:new Date().toISOString(),source,
  status:'unavailable',verified:false,executedClient:false,
  redistributedOriginalBinaries:false,pakSignatures:[],paksFound:0};
 try{
  let successful=false,lastError='';
  for(let attempt=1;attempt<=4;attempt++){
   try{
    await download(attempt%2===0?source+'?preservation='+attempt:source);
    successful=true;break;
   }catch(e){
    lastError=String(e.message||e);
    console.log('Source CDN retry '+attempt+'/4: '+lastError);
    try{fs.unlinkSync(zipPath)}catch{}
    await new Promise(resolve=>setTimeout(resolve,2500*attempt));
   }
  }
  if(!successful)throw Error('archive CDN unavailable after four attempts: '+lastError);
  report.archiveSHA1=await digest(zipPath,'sha1');
  if(report.archiveSHA1!==expected)throw Error('archive hash does not match');
  report.verified=true;
  const index=exec('unzip',['-Z','-1',zipPath]).split(/\r?\n/).filter(Boolean);
  const installer=path.join(temp,'installer');fs.mkdirSync(installer);
  for(const f of index.filter(x=>/\.(cab|hdr)$/i.test(x))){
   const name=path.basename(f);
   if(!/^[A-Za-z0-9_.-]+$/.test(name))continue;
   exec('unzip',['-p',zipPath,f],path.join(installer,name));
  }
  const cab=path.join(installer,'data1.cab');
  if(!fs.existsSync(cab))throw Error('InstallShield CAB not inside archive');
  const unpack=path.join(temp,'unpacked');fs.mkdirSync(unpack);
  // Reading/unpacking static resource data, NOT launching any .exe/.dll.
  exec('unshield',['-d',unpack,'x',cab]);
  const files=allFiles(unpack);
  const paks=files.filter(f=>f.toLowerCase().endsWith('.pak'));
  report.unshieldFiles=files.length;
  report.paksFound=paks.length;
  report.originalMemberHeaders=[];
  for(const file of paks){
   if(/\/Dice\/IMG\.pak$/i.test(file.split(path.sep).join('/'))){
    const images=spawnSync('python3',[path.join(__dirname,'emit-original-img-ui.py'),file],
      {encoding:'utf8',timeout:20000,maxBuffer:8*1024*1024});
    if(images.error||images.status!==0)
     console.log('ORIGINAL_IMG_IMAGE_CONVERSION_UNAVAILABLE '+String(images.error||images.stderr).slice(0,600));
    else console.log((images.stdout||'').slice(0,750000));
    const sprite=spawnSync('python3',[path.join(__dirname,'decode-original-img-spr.py'),file],
     {encoding:'utf8',timeout:50000,maxBuffer:8*1024*1024});
    if(sprite.error||sprite.status!==0)
     console.log('ORIGINAL_SPR_PIXEL_DECODE_ERROR '+String(sprite.error||sprite.stderr).slice(0,1200));
    else console.log((sprite.stdout||'').slice(0,600000));
    const probe=spawnSync('python3',[path.join(__dirname,'probe-original-spr.py'),file],{encoding:'utf8',timeout:18000,maxBuffer:3*1024*1024});
    if(probe.error)console.log('SOURCE_SPR_PROBE_FAILED '+probe.error.message);
    else console.log((probe.stdout||'').slice(0,80000));
   }
   if(/\/Dice\/OBS(?:2|3)?\.pak$/i.test(file.split(path.sep).join('/'))){
    const pixels=spawnSync('python3',[path.join(__dirname,'decode-original-obs-preview.py'),file],{
     encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024
    });
    if(pixels.error||pixels.status!==0)
     console.log('ORIGINAL_OBS_IMAGE_PROBE_ERROR '+String(pixels.error||pixels.stderr).slice(0,500));
    else console.log((pixels.stdout||'').slice(0,150000));
    const sourceActors=spawnSync('python3',[path.join(__dirname,'probe-original-obs.py'),file],{
     encoding:'utf8',timeout:15000,maxBuffer:3*1024*1024
    });
    if(sourceActors.error||sourceActors.status!==0)
     console.log('SOURCE_OBS_PROBE_ERROR '+String(sourceActors.error||sourceActors.stderr).slice(0,500));
    else console.log((sourceActors.stdout||'').slice(0,45000));
   }
   const sample=inspectOriginalMembers(file);
   for(const m of sample)console.log('ORIGINAL_MEMBER_HEADER '+JSON.stringify(m));
   report.originalMemberHeaders.push(...sample);
   const stat=fs.statSync(file);
   const fd=fs.openSync(file,'r');
   const head=Buffer.alloc(Math.min(96,stat.size));
   fs.readSync(fd,head,0,head.length,0);
   fs.closeSync(fd);
   const printable=[...head].map(x=>x>=32&&x<=126?String.fromCharCode(x):'.').join('');
   const firstU32LE=[];
   for(let offset=0;offset+4<=Math.min(head.length,48);offset+=4)
    firstU32LE.push(head.readUInt32LE(offset));
   const rel=path.relative(unpack,file).split(path.sep).join('/');
   let index=null;
   try{index=loadPakIndex(file)}catch(error){index={error:String(error.message||error)}}
   let payloadHeader=null;
   if(index&&!index.error&&index.entries.length){
    const fd=fs.openSync(file,'r');const data=Buffer.alloc(32);
    const count=fs.readSync(fd,data,0,data.length,index.headerBytes);
    fs.closeSync(fd);
    const view=data.subarray(0,count);
    payloadHeader={firstName:index.entries[0].name,
     encryptedHex:view.toString('hex'),
     invertedHex:Buffer.from(view.map(byte=>byte^255)).toString('hex')};
   }
   const item={path:rel,size:stat.size,sha256:await digest(file),
    magicHex:head.subarray(0,16).toString('hex'),
    headHex:head.toString('hex'),asciiPreview:printable,
    firstU32LE,payloadHeader,
    originalIndex:index?.error?index:{
     count:index.count,headerBytes:index.headerBytes,
     resourceBytesExact:index.resourceBytesExact,
     resourceSizeGap:index.resourceSizeGap,
     sampleNames:index.entries.slice(0,25),
     sourceSpriteNames:index.entries.filter(e=>/\.(obs|chr|spr|ani|dmp|tis|gif)$/i.test(e.name)).map(e=>e.name).slice(0,350)
    }};
   report.pakSignatures.push(item);
   if(/(^|\/)(OBS|OBS2|OBS3|CHR|DMP|TIS|IMG|CRD|MapData)\.pak$/i.test(rel)){
    console.log('ORIGINAL_SOURCE_PAK_SIGNATURE '+JSON.stringify(item));
    if(index&&!index.error)
     console.log('SOURCE_PAK_INDEX '+JSON.stringify({
      file:rel,count:index.count,
      exactPayloadLength:index.resourceBytesExact,sizeGap:index.resourceSizeGap,
      members:index.entries.slice(0,35)
     }));
   }
  }
  report.status='verified-original-packages-signature-inventory';
  console.log('STATIC_SOURCE_PAK_INVENTORY '+JSON.stringify({
   status:report.status,files:files.length,paks:paks.length,
   important:report.pakSignatures.filter(x=>/Dice\/(OBS|OBS2|OBS3|CHR|DMP|TIS)\.pak$/i.test(x.path))
    .map(x=>({file:x.path,bytes:x.size,magic:x.magicHex}))
  }));
 }catch(e){
  report.status='archive-inspection-failed';
  report.error=String(e?.message||e);
  console.log('Nonexecuting original PAK inventory blocked: '+report.error);
 }
 fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
 fs.rmSync(temp,{recursive:true,force:true});
 console.log('NO ORIGINAL BINARY FILE OR SOURCE IMAGE WAS EXECUTED, PUBLISHED OR PRESERVED');
})().catch(e=>{console.error('Static source inspector error',e);process.exitCode=1});
