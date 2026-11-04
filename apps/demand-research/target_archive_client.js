/* INTERSECTION: selected public-account backup request.
 * The private authenticated gateway can dispatch real Actions jobs. Static
 * Pages must NEVER contain a GitHub token or claim that a click queued work:
 * its usable fallback opens the existing authenticated GitHub workflow.
 */
(function(){
  "use strict";
  const form=document.getElementById("targetArchiveForm");
  if(!form)return;
  const $=id=>document.getElementById(id);
  const message=$("targetArchiveStatus");
  const platform=$("targetArchivePlatform");
  const account=$("targetArchiveAccount");
  const submit=$("targetArchiveSubmit");
  const workflow=$("targetArchiveWorkflow");
  const viewer=document.createElement("a");
  viewer.href="/account-archive";
  viewer.textContent="저장된 계정 아카이브 보기";
  viewer.style.marginLeft="14px";
  viewer.hidden=true;
  workflow.after(viewer);
  let gatewayReady=false;
  let submitting=false;

  function publicHost(host){
    return /^[A-Za-z0-9.-]{3,253}$/.test(host)&&!host.includes("..")&&
      host!=="localhost"&&!host.endsWith(".local")&&
      !host.endsWith(".internal")&&!/^(?:\d+\.){3}\d+$/.test(host);
  }
  function validSelection(){
    const raw=account.value.trim();
    if(raw.length<3||raw.length>260||/\s/.test(raw))return false;
    if(platform.value==="bluesky"){
      let value=raw;
      if(raw.startsWith("https://")){
        let url;
        try{url=new URL(raw);}catch{return false;}
        if(url.hostname!=="bsky.app"||url.username||url.password||
          url.search||url.hash||url.port||
          !/^\/profile\/[^/]+\/?$/.test(url.pathname))return false;
        value=url.pathname.slice("/profile/".length).replace(/\/$/,"");
      }
      value=value.replace(/^@/,"");
      if(value.startsWith("did:plc:"))return /^did:plc:[a-z2-7]{24}$/.test(value);
      return /^[A-Za-z0-9_.-]{3,260}$/.test(value);
    }
    if(platform.value==="mastodon"){
      if(raw.startsWith("https://")){
        let url;
        try{url=new URL(raw);}catch{return false;}
        return publicHost(url.hostname)&&!url.username&&!url.password&&
          !url.port&&!url.search&&!url.hash&&
          /^\/@[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}\/?$/.test(url.pathname);
      }
      const parts=raw.replace(/^@/,"").split("@");
      return parts.length===2&&
        /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}$/.test(parts[0])&&
        publicHost(parts[1]);
    }
    return false;
  }
  function refreshButton(){
    submit.disabled=submitting||!validSelection();
    submit.textContent=gatewayReady?"테라박스 백업 시작":"GitHub에서 백업 실행";
    workflow.hidden=gatewayReady;
  }
  function manualInstructions(copied){
    const name=account.value.trim();
    message.textContent=(copied?"계정 주소가 복사되었습니다. ":"계정 주소를 복사해 주세요. ")+
      "열린 GitHub Actions에서 Run workflow → "+
      (platform.value==="bluesky"?"Bluesky":"Mastodon")+
      " 선택 → account에 '"+name+"' 입력 → Run workflow를 눌러야 백업을 요청합니다. "+
      "이 버튼만으로 테라박스 저장이 시작되거나 완료된 것은 아닙니다.";
  }
  function openManualWorkflow(){
    // Both actions run directly in a user gesture; no credentials on Pages.
    // Failure to copy or a blocked popup is harmless: the workflow link and
    // selected account remain visible for a second attempt.
    manualInstructions(false);
    try{
      const copy=window.navigator.clipboard?.writeText(account.value.trim());
      if(copy&&typeof copy.then==="function")
        copy.then(()=>manualInstructions(true)).catch(()=>manualInstructions(false));
    }catch{/* Manual paste remains available. */}
    window.open(workflow.href,"_blank","noopener,noreferrer");
  }
  async function check(){
    try{
      const response=await fetch("/api/target-archive/status",{
        credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("private gateway unavailable");
      const result=await response.json();
      viewer.hidden=false; // authenticated read-only viewer needs no write token
      gatewayReady=Boolean(result.enabled);
      message.textContent=gatewayReady
        ?"개인용 보관 서버 연결됨 · 백업 요청 시 GitHub Actions 작업을 접수합니다. 원격 저장 완료는 별도 확인됩니다."
        :"보관 서버의 작업 실행 권한이 없습니다. GitHub Actions에서 직접 실행할 수 있습니다.";
    }catch{
      viewer.hidden=true;
      gatewayReady=false;
      message.textContent="공개 페이지에서는 비밀키 없이 직접 백업을 실행할 수 없습니다. 계정 입력 후 GitHub에서 백업 실행을 누르면 작업 실행 화면이 열립니다.";
    }finally{
      refreshButton();
    }
  }
  account.addEventListener("input",refreshButton);
  platform.addEventListener("change",refreshButton);
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    if(submitting||!validSelection())return;
    if(!gatewayReady){openManualWorkflow();return;}
    const value=account.value.trim();
    submitting=true;
    refreshButton();
    message.textContent="비공개 아카이브 작업 요청 중…";
    try{
      const response=await fetch("/api/target-archive/start",{
        method:"POST",credentials:"same-origin",cache:"no-store",
        headers:{"Content-Type":"application/json",
                 "X-Archive-Intent":"selected-public-account-v1"},
        body:JSON.stringify({platform:platform.value,account:value})
      });
      if(!response.ok){
        if(response.status===429)throw new Error("짧은 시간에 여러 번 요청했습니다. 잠시 후 재시도하세요.");
        if(response.status===503)throw new Error("비공개 아카이브 서버 실행 권한이 설정되지 않았습니다.");
        throw new Error("백업 작업 요청 실패 (HTTP "+response.status+")");
      }
      const result=await response.json();
      if(result.state!=="QUEUED_NOT_VERIFIED"||result.accepted!==true)
        throw new Error("서버 작업 응답을 확인하지 못했습니다.");
      message.textContent="백업 작업 접수됨(대기 중). 테라박스 원격 저장 성공은 아직 확인되지 않았습니다. 기존 계정 데이터는 유지됩니다.";
      account.value="";
    }catch(error){
      message.textContent=String(error.message||"아카이브 요청 실패")+
        " · 필요한 경우 GitHub Actions 직접 실행 링크를 이용하세요.";
      // A transient server error must not leave a permanently disabled
      // button: the account choice remains intact for another attempt.
    }finally{
      submitting=false;refreshButton();
    }
  });
  refreshButton();
  void check();
})();
