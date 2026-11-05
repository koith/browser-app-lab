/* INTERSECTION built-in archive tab.
 * Private ZIP objects never leave the signed, same-origin gateway.
 * The static GitHub Pages view cannot fetch TeraBox credentials or originals.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const panel=$("archivesView"),frame=$("archiveHubFrame"),status=$("archiveHubStatus");
const frameBox=$("archiveHubFrameBox"),actions=$("archiveHubActions");
if(!panel||!frame||!status||!frameBox||!actions)return;
let loading=false,connected=false,lastSrc="";
const ACCOUNT=/^(?:bluesky|mastodon)-[a-f0-9]{40}$/;
function chosenAccount(){
  const selected=new URLSearchParams(location.search).get("account")||"";
  return ACCOUNT.test(selected)?selected:"";
}
function frameUrl(){
  const account=chosenAccount();
  return "/account-archive"+(account?"?account="+encodeURIComponent(account):"");
}
function hidePrivate(){
  frameBox.hidden=true;actions.hidden=true;
  frame.removeAttribute("src");lastSrc="";
}
function showArchiveFrame(force=false){
  const url=frameUrl();
  if(force||url!==lastSrc){
    // Do not pass any private token in the frame URL or browser history.
    frame.src=url;lastSrc=url;
  }
  frameBox.hidden=false;actions.hidden=false;
  status.textContent="비공개 테라박스 보관함 연결됨 · 저장된 계정을 선택하면 글·사진·동영상을 볼 수 있습니다.";
}
async function loadArchive(){
  if(loading)return;
  if(connected){showArchiveFrame();return;}
  loading=true;
  status.textContent="저장된 자료를 열 수 있는지 확인하고 있습니다…";
  try{
    const response=await fetch("/api/session",{credentials:"same-origin",
      cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)throw Error(response.status===401?"PRIVATE_LOGIN_REQUIRED":"PRIVATE_GATEWAY_UNAVAILABLE");
    const data=await response.json();
    if(data.connected!==true)throw Error("PRIVATE_LOGIN_REQUIRED");
    connected=true;
    showArchiveFrame();
  }catch(error){
    connected=false;hidePrivate();
    status.textContent=String(error.message||"")==="PRIVATE_LOGIN_REQUIRED"
      ?"보관함 인증이 필요합니다. 개인용 보관 서버의 전용 주소로 접속하면 이 탭에서 원본을 열 수 있습니다."
      :"공개 사이트에는 테라박스 비공개 원본이 공개되지 않습니다. 보관 서버가 연결되면 이 탭에서 저장된 계정을 바로 볼 수 있습니다.";
  }finally{loading=false;}
}
function openArchive(account){
  if(account&&!ACCOUNT.test(account))return false;
  const url=new URL(location.href);
  url.searchParams.set("tab","archives");
  if(account)url.searchParams.set("account",account);
  else url.searchParams.delete("account");
  history.replaceState(null,"",url.pathname+url.search+url.hash);
  $("viewArchives")?.click();
  if(connected)showArchiveFrame();
  return true;
}
window.INTERSECTION_openArchive=openArchive;
window.addEventListener("intersection:tab-change",event=>{
  if(event.detail?.view==="archives")void loadArchive();
});
window.addEventListener("intersection:private-session-ready",()=>{
  connected=false;
  if(!panel.classList.contains("hidden"))void loadArchive();
});
$("archiveHubReload").addEventListener("click",()=>{
  connected=false;hidePrivate();void loadArchive();
});
if(new URLSearchParams(location.search).get("tab")==="archives")
  void loadArchive();
})();