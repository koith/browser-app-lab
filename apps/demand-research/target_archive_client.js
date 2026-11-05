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
  const panel=$("targetArchivePanel");
  const jobStatus=document.createElement("div");
  jobStatus.id="targetArchiveJobStatus";
  jobStatus.className="target-archive-job-status";
  jobStatus.hidden=true;jobStatus.setAttribute("role","status");
  jobStatus.setAttribute("aria-live","polite");
  const library=document.createElement("section");
  library.id="targetArchiveLibrary";
  library.className="target-archive-library";
  library.hidden=true;
  const libraryTitle=document.createElement("h4");
  libraryTitle.textContent="저장된 계정";
  const libraryRows=document.createElement("div");
  libraryRows.id="targetArchiveLibraryRows";
  library.append(libraryTitle,libraryRows);
  panel.append(jobStatus,library);
  let gatewayReady=false;
  let submitting=false;
  let currentRun=null;
  let pollTimer=null;

  const JOB_KEY="intersection:private-archive-job:v1";
  function resumeReceipt(){
    try{
      const value=JSON.parse(sessionStorage.getItem(JOB_KEY)||"null");
      if(value&&Number.isSafeInteger(value.run_id)&&value.run_id>0&&
         typeof value.receipt==="string"&&value.receipt.length<900)
        return value;
    }catch{/* Expired or tampered browser-only job receipt. */}
    return null;
  }
  function saveReceipt(value){
    try{
      if(value)sessionStorage.setItem(JOB_KEY,JSON.stringify(value));
      else sessionStorage.removeItem(JOB_KEY);
    }catch{/* Private browsing may disable sessionStorage. */}
  }
  function clearPoll(){
    if(pollTimer!==null){window.clearTimeout(pollTimer);pollTimer=null;}
  }
  function appendViewerLink(container,accountKey,text){
    if(!/^(bluesky|mastodon)-[a-f0-9]{40}$/.test(accountKey))return;
    const a=document.createElement("a");
    a.href="/account-archive?account="+encodeURIComponent(accountKey);
    a.textContent=text||"게시글 보기";
    a.className="target-archive-view-link";
    container.append(a);
  }
  function showJob(text,kind,accountKey){
    jobStatus.replaceChildren();
    const label=document.createElement("span");
    label.textContent=text;jobStatus.append(label);
    jobStatus.dataset.state=kind||"running";
    jobStatus.hidden=false;
    if(accountKey)appendViewerLink(jobStatus,accountKey,"저장된 자료 열기");
  }
  async function loadLibrary(){
    if(!gatewayReady)return;
    try{
      const response=await fetch("/api/account-archives",{
        credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}});
      if(!response.ok)throw Error("archive library unavailable");
      const data=await response.json();
      const accounts=Array.isArray(data.accounts)?data.accounts:[];
      libraryRows.replaceChildren();
      for(const item of accounts.slice(0,40)){
        if(!/^(bluesky|mastodon)-[a-f0-9]{40}$/.test(String(item.key||"")))continue;
        const row=document.createElement("div");
        row.className="target-archive-library-row";
        const label=document.createElement("span");
        const source=item.platform==="bluesky"?"Bluesky":"Mastodon";
        // Only the provider's validated HTTPS public profile URL is shown.
        let profile="";
        try{
          const url=new URL(String(item.profile_url||""));
          if(url.protocol==="https:"&&!url.username&&!url.password)
            profile=url.hostname+url.pathname;
        }catch{}
        label.textContent=source+" · "+(profile||"공개 계정")+
          (item.backup_kind==="terabox_zip_sha_verified"
             ?" · 보관 글 "+Number(item.posts_verified_in_bundle||0)+"건":"");
        row.append(label);
        appendViewerLink(row,item.key,"보기");
        libraryRows.append(row);
      }
      if(!libraryRows.children.length){
        const empty=document.createElement("p");
        empty.textContent="아직 저장·검증된 계정이 없습니다.";
        libraryRows.append(empty);
      }
      library.hidden=false;
    }catch{
      library.hidden=true; // Do not pretend an unverified archive is readable.
    }
  }
  async function pollJob(){
    clearPoll();
    if(!gatewayReady||!currentRun)return;
    const job=currentRun;
    try{
      const response=await fetch("/api/target-archive/jobs/"+
        encodeURIComponent(String(job.run_id))+"?receipt="+
        encodeURIComponent(job.receipt),{
          credentials:"same-origin",cache:"no-store",
          headers:{Accept:"application/json"}
        });
      if(!response.ok)throw Error("진행 상태를 읽지 못했습니다 (HTTP "+response.status+")");
      const result=await response.json();
      if(currentRun!==job)return;
      const count=Number(result.posts||0);
      switch(result.state){
        case "QUEUED":
          showJob("백업 작업 접수 완료 · 실행 대기 중","queued");break;
        case "RUNNING":
          showJob("백업 진행 중 · 공개 자료를 수집하고 테라박스에 저장하고 있습니다.","running");break;
        case "VERIFYING_STORAGE":
          showJob("파일 전송 완료 여부를 확인 중 · 테라박스에서 원본을 다시 읽고 있습니다.","verifying");break;
        case "REMOTE_VERIFIED":
        case "PARTIAL_BACKUP":
          showJob((result.state==="REMOTE_VERIFIED"
            ?"테라박스 백업 완료 · 게시글 "+count+"건 · 원본 "+
               Number(result.objects||0)+"개 검증"
            :"백업된 자료 일부 검증됨 · 게시글 "+count+
              "건 · 수집되지 않은 구간이 남아 있습니다."),"verified",
            String(result.account_key||""));
          saveReceipt(null);currentRun=null;
          await loadLibrary();
          return;
        case "FAILED":
          showJob("백업 실패 · 기존 보관 자료는 유지됩니다. 다시 실행할 수 있습니다.","failed");
          saveReceipt(null);currentRun=null;
          return;
        default:
          showJob("백업 진행 상태를 확인 중입니다.","running");
      }
    }catch{
      if(currentRun!==job)return;
      showJob("진행 상태 확인에 실패했습니다. 잠시 뒤 자동으로 다시 확인합니다.","verifying");
    }
    if(currentRun===job)pollTimer=window.setTimeout(pollJob,6000);
  }

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
    // Keep the button operable so an empty/invalid account explains what is
    // missing instead of looking broken on touch devices.
    submit.disabled=submitting;
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
    // In-app iPhone WebViews commonly block window.open(). Same-tab
    // navigation is a real user-gesture route and works without popups.
    // The chosen public account is also copied when the browser permits it;
    // the Back action retains this form for manual retry.
    window.location.assign(workflow.href);
  }
  async function check(){
    try{
      const response=await fetch("/api/target-archive/status",{
        credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("private gateway unavailable");
      const result=await response.json();
      viewer.hidden=false; // signed private session can read the archive viewer
      gatewayReady=Boolean(result.enabled);
      message.textContent=gatewayReady
        ?"연결됨 · 계정 주소를 입력하고 백업을 누르면 이 화면에서 진행 상태를 확인할 수 있습니다."
        :"비공개 보관함은 열 수 있지만 새 백업 요청 권한이 설정되지 않았습니다.";
      if(gatewayReady){
        void loadLibrary();
        const remembered=resumeReceipt();
        if(remembered){
          currentRun=remembered;
          showJob("이전에 요청한 백업의 진행 상태를 확인 중…","running");
          void pollJob();
        }
      }
    }catch{
      viewer.hidden=true;
      gatewayReady=false;
      message.textContent="공개 페이지에서는 비밀키 없이 직접 백업을 실행할 수 없습니다. 계정 입력 후 GitHub에서 백업 실행을 누르면 작업 실행 화면이 열립니다.";
    }finally{
      refreshButton();
    }
  }
  account.addEventListener("input",()=>{
    account.removeAttribute("aria-invalid");
    refreshButton();
  });
  platform.addEventListener("change",()=>{
    account.removeAttribute("aria-invalid");
    refreshButton();
  });
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    if(submitting)return;
    if(!validSelection()){
      account.setAttribute("aria-invalid","true");
      message.textContent="먼저 공개 SNS 계정 주소 또는 핸들을 입력하세요. "+
        "예: https://bsky.app/profile/example.bsky.social / @user@example.social";
      account.focus();
      return;
    }
    account.removeAttribute("aria-invalid");
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
      if(result.state!=="QUEUED_NOT_VERIFIED"||result.accepted!==true||
         !Number.isSafeInteger(result.run_id)||typeof result.receipt!=="string")
        throw new Error("백업 작업 번호를 확인하지 못했습니다.");
      currentRun={run_id:result.run_id,receipt:result.receipt,
                  platform:platform.value,account:value};
      saveReceipt(currentRun);
      message.textContent="백업 작업이 접수됐습니다. 완료되면 이 화면에서 저장된 자료를 열 수 있습니다.";
      showJob("백업 요청 접수 · 실행 순서를 확인 중…","queued");
      void pollJob();
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
