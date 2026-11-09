/* INTERSECTION backup library: one private viewer for keyword captures and
 * one for selected public accounts. Never retrieve private bytes on Pages.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const panel=$("archivesView"),frame=$("archiveHubFrame"),status=$("archiveHubStatus");
const frameBox=$("archiveHubFrameBox"),actions=$("archiveHubActions");
const auto=$("archiveModeAuto"),accounts=$("archiveModeAccounts");
const quickBox=$("archiveAccountPicker"),quick=$("archiveQuickSelect"),
      quickSearch=$("archiveQuickSearch"),quickCount=$("archiveQuickCount"),
      quickStatus=$("archiveQuickStatus");
if(!panel||!frame||!status||!frameBox||!actions||!auto||!accounts)return;
let loading=false,connected=false,lastSrc="",retryCount=0;
let choices=[],choicesTime=0,choicesPending=null;
const ACCOUNT=/^(?:bluesky|mastodon)-[a-f0-9]{40}$/;
const PRIVATE_APP="https://intersection-originals-free.onrender.com/";
const query=()=>new URLSearchParams(location.search);
const chosenAccount=()=>{const selected=query().get("account")||"";return ACCOUNT.test(selected)?selected:"";};
function selectedMode(){
  const explicit=query().get("mode");
  if(explicit==="accounts"||explicit==="auto")return explicit;
  // In the signed private app, archived accounts are the quickest entry.
  // Automatic keyword backups remain one tap away.
  if(location.hostname!=="koith.github.io")return "accounts";
  return chosenAccount()?"accounts":"auto";
}
function accountLabel(item){
  const name=typeof item?.display_name==="string"
    ?item.display_name.trim().replace(/\s+/g," ").slice(0,100):"";
  const handle=typeof item?.handle==="string"
    ?item.handle.trim().replace(/^@+/,"").slice(0,200):"";
  if(name&&handle)return name+"(@"+handle+")";
  if(name)return name+"(아이디 미보관)";
  if(handle)return "닉네임 미보관(@"+handle+")";
  return "이름 미보관 ("+(item?.platform==="mastodon"?"Mastodon":"Bluesky")+" 계정)";
}
function storeSelectedKey(key){
  if(!ACCOUNT.test(key))return;
  const u=new URL(location.href);
  if(u.searchParams.get("account")===key)return;
  u.searchParams.set("account",key);
  history.replaceState(null,"",u.pathname+u.search+u.hash);
}
function renderChoices(){
  if(!quick)return;
  const matching=choices.filter(item=>{
    const needle=(quickSearch?.value||"").trim().toLocaleLowerCase("ko-KR");
    return !needle||accountLabel(item).toLocaleLowerCase("ko-KR").includes(needle);
  });
  const current=chosenAccount();
  quick.replaceChildren();
  if(!matching.length){
    const empty=document.createElement("option");
    empty.value="";empty.textContent=choices.length?"일치하는 계정 없음":"보관된 계정 없음";
    quick.append(empty);
  }else{
    for(const item of matching){
      const option=document.createElement("option");
      option.value=item.key;option.textContent=accountLabel(item);
      quick.append(option);
    }
  }
  quick.disabled=!matching.length;
  if(matching.some(item=>item.key===current))quick.value=current;
  else quick.value=matching.length?"":quick.options[0].value;
  if(quickSearch)quickSearch.hidden=choices.length<5;
  if(quickCount)quickCount.textContent=choices.length+"개 보관";
  if(quickStatus)quickStatus.textContent=choices.length
    ?"목록은 자동으로 불러왔습니다. 계정을 선택하면 아래 내용이 바로 바뀝니다."
    :"보관된 계정이 없습니다. 계정 분석에서 공개 계정을 백업하세요.";
}
async function preloadChoices(force=false){
  if(location.hostname==="koith.github.io")return choices;
  if(choicesPending)return choicesPending;
  if(!force&&choicesTime&&Date.now()-choicesTime<180000)return choices;
  choicesPending=(async()=>{
    await (window.INTERSECTION_AUTH_READY||Promise.resolve());
    const response=await fetch("/api/account-archives",{
      credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)throw Error("보관된 계정 목록 연결 실패");
    const data=await response.json();
    choices=(Array.isArray(data?.accounts)?data.accounts:[]).filter(
      item=>ACCOUNT.test(item.key));
    choices.sort((a,b)=>accountLabel(a).localeCompare(accountLabel(b),"ko-KR"));
    choicesTime=Date.now();
    renderChoices();
    if(selectedMode()==="accounts"&&connected){
      if(!chosenAccount()&&choices.length)storeSelectedKey(choices[0].key);
      showArchiveFrame();
    }
    return choices;
  })().catch(()=>{
    if(quickStatus)quickStatus.textContent="보관 계정을 자동으로 가져오지 못했습니다. 새로고침하면 재시도합니다.";
    if(quickCount)quickCount.textContent="조회 지연";
    return [];
  }).finally(()=>{choicesPending=null;});
  return choicesPending;
}
function setButtons(mode){
  auto.setAttribute("aria-selected",String(mode==="auto"));
  accounts.setAttribute("aria-selected",String(mode==="accounts"));
  if(quickBox)quickBox.hidden=mode!=="accounts";
}
function frameUrl(){
  return selectedMode()==="auto"?"/auto-archive":"/account-archive?embedded=1"+
      (chosenAccount()?"&account="+encodeURIComponent(chosenAccount()):"");
}
function fullViewUrl(){
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
    if(["ok","cached_verified"].includes(overview.automated_posts_state)){
      status.textContent="원격에서 확인한 게시글 "+
        Number(overview.automated_posts||0).toLocaleString("ko-KR")+
        "건. 아래에서 저장된 글·사진·영상을 조회하세요.";
    }else if(overview.post_journal_state==="candidates_unverified"){
      status.textContent="자동 수집 저널 파일 후보 "+
        Number(overview.post_journal_candidates||0).toLocaleString("ko-KR")+
        "개 발견. 아직 게시글 내용·첨부의 원격 무결성이 검증된 개수는 아닙니다.";
    }else{
      status.textContent="테라박스 게시글 목록의 원격 읽기 상태가 확인되지 않았습니다.";
    }
  }else if(overview.account_bundles_state==="one_verified"){
    status.textContent="지정 계정 ZIP 후보 "+
      Number(overview.account_zip_candidates||0).toLocaleString("ko-KR")+
      "개 중 최신 1개 원격 무결성 확인. 아래에서 저장된 계정을 선택하세요.";
  }else if(overview.account_bundles_state==="candidates_unverified"){
    status.textContent="지정 계정 ZIP 파일 후보 "+
      Number(overview.account_zip_candidates||0).toLocaleString("ko-KR")+
      "개 발견. 실제 무결성 검증은 아래 계정 보관함에서 진행합니다.";
  }else if(["empty","zero_candidates_unverified"].includes(overview.account_bundles_state)){
    status.textContent="현재 원격 목록에서 계정 ZIP 후보 0개. 저장 파일이 전혀 없다고 단정할 수는 없습니다.";
  }else{
    status.textContent="계정 ZIP 원격 목록 확인이 완료되지 않았습니다. 저장 성공으로 표시하지 않습니다.";
  }
}
function showArchiveFrame(force=false){
  const mode=selectedMode();
  setButtons(mode);
  actions.hidden=false;
  $("archiveHubFullView").href=fullViewUrl();
  if(mode==="accounts"&&!chosenAccount()){
    frameBox.hidden=true;
    status.textContent=choicesTime
      ?"보관된 계정이 없습니다. 계정 분석에서 백업한 뒤 다시 확인하세요."
      :"보관된 계정 목록을 자동으로 불러오는 중입니다.";
    void preloadChoices();
    return;
  }
  const url=frameUrl();
  if(force||url!==lastSrc){frame.src=url;lastSrc=url;}
  frame.title=mode==="auto"?"자동으로 보관한 게시글과 원본 미디어":
    "지정 계정의 게시글·댓글·원본 미디어·프로필 보관본";
  frameBox.hidden=false;
  if(mode==="accounts"){
    if(quick&&quick.options.length)quick.value=chosenAccount();
    status.textContent="선택한 계정의 보관된 프로필·글·미디어를 아래에 바로 표시합니다.";
    void preloadChoices();
  }else{
    status.textContent="자동 보관 게시글을 확인하고 있습니다.";
    void loadOverview();
  }
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
  if(connected){showArchiveFrame();if(selectedMode()==="accounts")void preloadChoices();return;}
  loading=true;status.textContent="테라박스 보관 서버에 연결 중…";
  try{
    await (window.INTERSECTION_AUTH_READY||Promise.resolve());
    const response=await fetch("/api/session",{
      credentials:"same-origin",cache:"no-store",
      headers:{Accept:"application/json"}});
    if(!response.ok)throw Error(response.status===401?"PRIVATE_LOGIN_REQUIRED":"PRIVATE_GATEWAY_UNAVAILABLE");
    const data=await response.json();
    if(data.connected!==true)throw Error("PRIVATE_LOGIN_REQUIRED");
    connected=true;retryCount=0;
    if(selectedMode()==="accounts"&&!chosenAccount()&&choices.length)
      storeSelectedKey(choices[0].key);
    showArchiveFrame();
    if(selectedMode()==="accounts")void preloadChoices();
  }catch(error){
    connected=false;hidePrivate();
    status.textContent="저장소와 다시 연결 중입니다. 원본은 변경되지 않았습니다.";
    if(retryCount<6){
      retryCount+=1;
      window.setTimeout(()=>{
        if(!panel.classList.contains("hidden")&&!connected)void loadArchive();
      },Math.min(2500*retryCount,10000));
    }else{
      status.textContent="보관 서버의 연결을 복구하지 못했습니다. 새로고침으로 재시도할 수 있습니다.";
    }
  }finally{loading=false;}
}
function changeMode(mode,account=""){
  if(!["auto","accounts"].includes(mode)||account&&!ACCOUNT.test(account))return false;
  const url=new URL(location.href);
  url.searchParams.set("tab","archives");
  url.searchParams.set("mode",mode);
  const selected=account||chosenAccount()||(
    mode==="accounts"&&choices.length?choices[0].key:"");
  // Keep the chosen account even while looking at automatic backups.
  if(selected)url.searchParams.set("account",selected);
  else url.searchParams.delete("account");
  history.replaceState(null,"",url.pathname+url.search+url.hash);
  setButtons(mode);
  renderChoices();
  $("viewArchives")?.click();
  if(connected)showArchiveFrame();
  else if(location.hostname==="koith.github.io")void loadArchive();
  if(mode==="accounts")void preloadChoices();
  return true;
}
// Called by successful backup receipt or a saved-account card.
window.INTERSECTION_openArchive=(account,mode)=>
  changeMode(mode==="auto"?"auto":"accounts",account||"");
auto.addEventListener("click",()=>changeMode("auto"));
accounts.addEventListener("click",()=>changeMode("accounts"));
quick?.addEventListener("change",()=>{
  if(ACCOUNT.test(quick.value))changeMode("accounts",quick.value);
});
quickSearch?.addEventListener("input",renderChoices);
window.addEventListener("message",event=>{
  if(event.origin!==location.origin||event.source!==frame.contentWindow
      ||event.data?.type!=="intersection:archive-selected"
      ||!ACCOUNT.test(event.data.account))return;
  storeSelectedKey(event.data.account);
  renderChoices();
  $("archiveHubFullView").href=fullViewUrl();
});
window.addEventListener("intersection:tab-change",event=>{
  if(event.detail?.view==="archives")void loadArchive();
});
window.addEventListener("intersection:private-session-ready",()=>{
  connected=false;
  void preloadChoices(true);
  if(!panel.classList.contains("hidden"))void loadArchive();
});
$("archiveHubReload").addEventListener("click",()=>{
  connected=false;hidePrivate();choicesTime=0;
  void preloadChoices(true);void loadArchive();
});
setButtons(selectedMode());
if(location.hostname!=="koith.github.io"){
  // Warm the private picker when the page opens, not when the user clicks it.
  void preloadChoices();
}
if(query().get("tab")==="archives")void loadArchive();
})();