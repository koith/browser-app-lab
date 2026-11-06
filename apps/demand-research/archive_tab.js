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
let overview=null,overviewTime=0,overviewPending=null;
async function loadOverview(){
  if(!connected)return;
  if(!overview||Date.now()-overviewTime>180000){
    if(!overviewPending){
      overviewPending=(async()=>{
        const response=await fetch("/api/archive-overview",{
          credentials:"same-origin",cache:"no-store",
          headers:{Accept:"application/json"}});
        if(!response.ok)throw new Error("원격 보관본 점검 실패 (HTTP "+response.status+")");
        const result=await response.json();
        if(!result||typeof result!=="object")
          throw new Error("원격 보관본 점검 응답 형식 오류");
        overview=result;overviewTime=Date.now();
      })().finally(()=>{overviewPending=null;});
    }
    try{await overviewPending;}catch{
      if(connected)status.textContent+=" · 원격 보관본 목록 점검이 지연되고 있습니다.";
      return;
    }
  }
  if(!connected||!overview)return;
  if(selectedMode()==="auto"){
    if(overview.automated_posts_state==="ok"){
      status.textContent="테라박스 원격 보관 게시글 "+
        Number(overview.automated_posts||0).toLocaleString("ko-KR")+
        "건 확인. 아래에서 글·사진·영상을 조회할 수 있습니다.";
    }else{
      status.textContent="테라박스 원본 게시글 재읽기에 실패했습니다. 저장 성공으로 표시하지 않습니다.";
    }
  }else if(overview.account_bundles_state==="one_verified"){
    status.textContent="지정 계정 ZIP 후보 "+
      Number(overview.account_zip_candidates||0).toLocaleString("ko-KR")+
      "개 중 최신 1개 원격 무결성 확인. 아래에서 저장된 계정을 선택하세요.";
  }else if(overview.account_bundles_state==="empty"){
    status.textContent="현재 원격 목록에서 SHA 검증 가능한 계정 ZIP이 0개입니다. 저장 파일의 존재 여부는 별도 검증이 필요합니다.";
  }else{
    status.textContent="계정 ZIP 원격 읽기/검증이 완료되지 않았습니다. 저장 성공으로 표시하지 않습니다.";
  }
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
    "자동 보관 게시글을 조회 중입니다. 원격 검증 결과를 곧 표시합니다.":
    "저장된 계정 ZIP 목록을 조회 중입니다. 원격 검증 결과를 곧 표시합니다.";
  void loadOverview();
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