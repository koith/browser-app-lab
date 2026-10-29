/* Connect only to the owner's Google account. Drive ZIP bytes are verified by PhotoVault before local storage. */
(function(root){
'use strict';
const $=id=>document.getElementById(id);
const model=document.body.dataset.model;
if(!['yui','mimmi'].includes(model)||!root.PhotoVault)throw Error('개인 저장소 초기화 오류');
const key='photo-vault-drive-settings-'+model;
let accessToken='',busy=false,cancelled=false;
const report=s=>{$('drive-status').textContent=s};
function folderId(input){
 const value=String(input||'').trim();
 const match=value.match(/(?:^|\/folders\/)([A-Za-z0-9_-]{15,100})(?:[/?#]|$)/);
 return match?match[1]:'';
}
function readSettings(){
 try{return JSON.parse(localStorage.getItem(key))||{}}catch{return {}}
}
const saved=readSettings();
$('drive-client-id').value=saved.clientId||'';
$('drive-folder').value=saved.folder||'';
function settings(){
 const clientId=$('drive-client-id').value.trim(),folder=$('drive-folder').value.trim();
 if(!/^[0-9]{8,}-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId))
  throw Error('Google 웹 OAuth 클라이언트 ID를 입력하세요.');
 const id=folderId(folder);
 if(!id)throw Error('비공개 Google Drive 보관 폴더 주소를 입력하세요.');
 // OAuth client IDs and folder identifiers are not credentials, but retain locally only.
 localStorage.setItem(key,JSON.stringify({clientId,folder}));
 return {clientId,folder:id};
}
async function drive(path,blob=false){
 const r=await fetch('https://www.googleapis.com/drive/v3/'+path,{
  headers:{Authorization:'Bearer '+accessToken},cache:'no-store'
 });
 if(!r.ok)throw Error('Google Drive API HTTP '+r.status+(r.status===401?' · 다시 로그인하세요':''));
 return blob?r.blob():r.json();
}
async function listFiles(id){
 let token='',files=[],pages=0;
 do{
  const params=new URLSearchParams({
   q:"'"+id+"' in parents and trashed = false",
   fields:'nextPageToken,incompleteSearch,files(id,name,size,mimeType,modifiedTime)',
   pageSize:'1000',supportsAllDrives:'true',includeItemsFromAllDrives:'true'
  });
  if(token)params.set('pageToken',token);
  const data=await drive('files?'+params.toString());
  if(!Array.isArray(data.files)||data.incompleteSearch)throw Error('Drive 파일 목록이 불완전합니다.');
  files.push(...data.files);
  token=data.nextPageToken||'';
  if(++pages>30)throw Error('파일 목록이 너무 큽니다.');
 }while(token);
 const prefix=model+'-';
 return files.filter(f=>f.mimeType==='application/zip'&&f.name?.startsWith(prefix)&&f.name.endsWith('.actions.zip')
  &&/^[A-Za-z0-9_-]{10,100}$/.test(f.id)&&Number(f.size)>0&&Number(f.size)<=2*1024**3)
  .sort((a,b)=>a.name.localeCompare(b.name));
}
async function sync(){
 const cfg=settings();
 busy=true;cancelled=false;
 $('drive-connect').disabled=true;$('drive-cancel').hidden=false;
 let imported=0,skipped=0,failed=0,photos=0,items=[];
 try{
  report('보관 폴더에서 실제 ZIP 목록 확인 중...');
  const files=await listFiles(cfg.folder);
  if(!files.length){report('해당 모델의 .actions.zip 보관본이 없습니다. 폴더와 접근 권한을 확인하세요.');return}
  for(const [i,f] of files.entries()){
   if(cancelled)break;
   const signature=f.size+':'+(f.modifiedTime||'');
   if(await PhotoVault.archiveSynced(model,f.id,signature)){skipped++;continue}
   report('Drive ZIP '+(i+1)+'/'+files.length+' 다운로드: '+f.name);
   try{
    // Downloads are authenticated, never exposed as public Drive links.
    const blob=await drive('files/'+encodeURIComponent(f.id)+'?alt=media&supportsAllDrives=true',true);
    if(blob.size!==Number(f.size))throw Error('클라우드 ZIP 파일 크기 불일치');
    if(cancelled)break;
    const file=new File([blob],f.name,{type:'application/zip'});
    const result=await PhotoVault.importZip(file,model,msg=>
      report('ZIP '+(i+1)+'/'+files.length+' · '+msg));
    // Mark only after the entire verified import succeeded in IndexedDB.
    await PhotoVault.markArchiveSynced(model,f.id,signature);
    imported++;photos+=result.images;
   }catch(error){failed++;items.push(f.name+': '+(error?.message||String(error)))}
  }
  const summary='보관 ZIP '+files.length+'개 · 신규 검증 '+imported+'개 · 이미 저장 '+skipped+
   '개 · 실패 '+failed+'개 · 처리 사진 '+photos+'항목'+(cancelled?' · 사용자 중단':'');
  report(summary+(items.length?' · '+items.slice(0,2).join(' / '):''));
  $('gallery-link').hidden=false;
 }finally{busy=false;$('drive-connect').disabled=false;$('drive-cancel').hidden=true}
}
function connect(){
 if(busy)return;
 let cfg;
 try{cfg=settings()}catch(error){report(error.message);return}
 if(!root.google?.accounts?.oauth2?.initTokenClient){
  report('Google 로그인 라이브러리를 불러오지 못했습니다. 인터넷 연결을 확인하세요.');return;
 }
 report('Google 계정 접근 동의를 확인하는 중...');
 // User gesture is required; no token is saved to localStorage, GitHub, or query strings.
 const client=root.google.accounts.oauth2.initTokenClient({
  client_id:cfg.clientId,scope:'https://www.googleapis.com/auth/drive.readonly',
  callback:async response=>{
   if(!response?.access_token){report('Google 인증 실패 · '+(response?.error||'로그인 취소'));return}
   accessToken=response.access_token;
   try{await sync()}catch(error){report('동기화 실패 · '+(error?.message||String(error)))}
   finally{accessToken=''}
  },
  error_callback:error=>report('Google 로그인 창 오류 · '+(error?.type||'다시 시도하세요'))
 });
 client.requestAccessToken();
}
$('drive-connect').onclick=connect;
$('drive-cancel').onclick=()=>{if(busy){cancelled=true;report('현재 작업 종료 후 동기화를 중단합니다.')}};
$('gallery-link').href='./';
if(saved.folder)report('설정 저장됨 · 로그인 후 실제 원본을 이 기기에 동기화할 수 있습니다.');
root.DriveArchiveSync={folderId};
})(globalThis);
