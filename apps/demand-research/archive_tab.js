/* INTERSECTION backup library: one private viewer for keyword captures and
 * one for selected public accounts. Never retrieve private bytes on Pages.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const panel=$("archivesView"),frame=$("archiveHubFrame"),status=$("archiveHubStatus");
const frameBox=$("archiveHubFrameBox"),actions=$("archiveHubActions");
const auto=$("archiveModeAuto"),accounts=$("archiveModeAccounts");
if(!panel||!frame||!status||!frameBox||!actions||!auto||!accounts)return;
let loading=false,connected=false,lastSrc="";
const ACCOUNT=/^(?:bluesky|mastodon)-[a-f0-9]{40}$/;
const PRIVATE_APP="https://intersection-originals-free.onrender.com/";
const query=()=>new URLSearchParams(location.search);
const chosenAccount=()=>{const selected=query().get("account")||"";return ACCOUNT.test(selected)?selected:"";};
function selectedMode(){
  const explicit=query().get("mode");
  return explicit==="accounts"||(!explicit&&Boolean(chosenAccount()))?"accounts":"auto";
}
function setButtons(mode){
  auto.setAttribute("aria-selected",String(mode==="auto"));
  accounts.setAttribute("aria-selected",String(mode==="accounts"));
}
function frameUrl(){
  return selectedMode()==="auto"?"/auto-archive":"/account-archive"+
      (chosenAccount()?"?account="+encodeURIComponent(chosenAccount()):"");
}
function hidePrivate(){
  frameBox.hidden=true;actions.hidden=true;
  frame.removeAttribute("src");lastSrc="";
}
function showArchiveFrame(force=false){
  const mode=selectedMode(),url=frameUrl();
  setButtons(mode);
  if(force||url!==lastSrc){frame.src=url;lastSrc=url;}
  frame.title=mode==="auto"?"자동으로 보관한 게시글과 원본 미디어":
    "지정 계정의 게시글·댓글·원본 미디어·프로필 보관본";
  $("archiveHubFullView").href=url;
  frameBox.hidden=false;actions.hidden=false;
  status.textContent=mode==="auto"?
    "자동 저장된 공개 글의 원본을 조회합니다. 실제로 검증된 파일만 표시됩니다.":
    "지정 계정의 검증된 보관본을 조회합니다. 보관되지 않은 이력은 표시하지 않습니다.";
}
async function loadArchive(){
  if(loading)return;
  setButtons(selectedMode());
  if(location.hostname==="koith.github.io"){
    connected=false;hidePrivate();
    const url=new URL(PRIVATE_APP);
    url.searchParams.set("tab","archives");
    url.searchParams.set("mode",selectedMode());
    if(chosenAccount())url.searchParams.set("account",chosenAccount());
    const link=$("archiveHubFullView");
    link.href=url.href;
    link.textContent="교집합 보관함에서 열기";
    $("archiveHubReload").hidden=true;
    actions.hidden=false;
    status.textContent="자동 저장 게시글과 지정 계정 백업 모두 교집합 전용 웹앱에서 조회합니다. 외부 GitHub 실행 화면으로 이동하지 않습니다.";
    return;
  }
  $("archiveHubReload").hidden=false;
  $("archiveHubFullView").textContent="보관함 크게 보기";
  if(connected){showArchiveFrame();return;}
  loading=true;status.textContent="테라박스 보관 서버에 연결 중…";
  try{
    await (window.INTERSECTION_AUTH_READY||Promise.resolve());
    const response=await fetch("/api/session",{
      credentials:"same-origin",cache:"no-store",
      headers:{Accept:"application/json"}});
    if(!response.ok)throw Error(response.status===401?"PRIVATE_LOGIN_REQUIRED":"PRIVATE_GATEWAY_UNAVAILABLE");
    const data=await response.json();
    if(data.connected!==true)throw Error("PRIVATE_LOGIN_REQUIRED");
    connected=true;showArchiveFrame();
  }catch(error){
    connected=false;hidePrivate();
    status.textContent=String(error.message||"")==="PRIVATE_LOGIN_REQUIRED"?
      "이 브라우저에 개인 보관함 접속 기록이 없습니다. 개인 접속 링크로 한 번 들어오면 이후 자동으로 열립니다.":
      "보관 서버와 통신하지 못했습니다. 저장본은 변경되지 않았습니다.";
  }finally{loading=false;}
}
function changeMode(mode,account=""){
  if(!["auto","accounts"].includes(mode)||account&&!ACCOUNT.test(account))return false;
  const url=new URL(location.href);
  url.searchParams.set("tab","archives");
  url.searchParams.set("mode",mode);
  if(mode==="accounts"&&account)url.searchParams.set("account",account);
  else url.searchParams.delete("account");
  history.replaceState(null,"",url.pathname+url.search+url.hash);
  setButtons(mode);
  $("viewArchives")?.click();
  if(connected)showArchiveFrame();
  else if(location.hostname==="koith.github.io")void loadArchive();
  return true;
}
// Called by successful backup receipt or a saved-account card.
window.INTERSECTION_openArchive=(account,mode)=>
  changeMode(mode==="auto"?"auto":"accounts",account||"");
auto.addEventListener("click",()=>changeMode("auto"));
accounts.addEventListener("click",()=>changeMode("accounts"));
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
setButtons(selectedMode());
if(query().get("tab")==="archives")void loadArchive();
})();