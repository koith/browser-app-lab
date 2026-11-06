/* INTERSECTION: one-click public-account backup on the private authenticated
 * gateway. Public Pages never sees GitHub/TeraBox tokens and ONLY navigates
 * to the dedicated operator gateway with the selected public account prefilled.
 * A cross-origin URL alone must never trigger an authenticated backup (CSRF).
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
  // The URL is public, never a secret. Change only after creating the
  // dedicated Free service in the separate Render Hobby workspace.
  const PRIVATE_GATEWAY="https://intersection-originals-free.onrender.com";
  const isPrivateGateway=location.origin===PRIVATE_GATEWAY;
  const viewer=document.createElement("a");
  viewer.href="?tab=archives";
  viewer.textContent="백업 보관함 열기";
  viewer.addEventListener("click",event=>{
    if(typeof window.INTERSECTION_openArchive==="function"){
      event.preventDefault();window.INTERSECTION_openArchive("");
    }
  });
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
  const libraryAll=document.createElement("a");
  libraryAll.href="?tab=archives";
  libraryAll.textContent="보관함 전체 보기";
  libraryAll.addEventListener("click",event=>{
    if(typeof window.INTERSECTION_openArchive==="function"){
      event.preventDefault();window.INTERSECTION_openArchive("");
    }
  });
  libraryAll.className="target-archive-view-link";
  const libraryRows=document.createElement("div");
  libraryRows.id="targetArchiveLibraryRows";
  library.append(libraryTitle,libraryAll,libraryRows);
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
    a.href="?tab=archives&account="+encodeURIComponent(accountKey);
    a.addEventListener("click",event=>{
      if(typeof window.INTERSECTION_openArchive==="function"){
        event.preventDefault();window.INTERSECTION_openArchive(accountKey);
      }
    });
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
    library.hidden=false;
    libraryRows.textContent="테라박스에서 저장된 계정을 확인 중…";
    try{
      const response=await fetch("/api/account-archives",{
        credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}});
      if(!response.ok)throw Error("archive library unavailable");
      const data=await response.json();
      const accounts=Array.isArray(data.accounts)?data.accounts:[];
      libraryRows.replaceChildren();
      for(const item of accounts.slice(0,8)){
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
      libraryRows.textContent="보관 목록을 확인하지 못했습니다. ‘보관함 전체 보기’로 다시 시도할 수 있습니다.";
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
  function normalizedAccount(){
    const raw=account.value.trim();
    if(raw.length<3||raw.length>260||/\s/.test(raw))return "";
    if(platform.value==="bluesky"){
      let handle=raw;
      if(raw.startsWith("https://")){
        let url;
        try{url=new URL(raw);}catch{return "";}
        if(url.hostname!=="bsky.app"||url.username||url.password||
          url.search||url.hash||url.port||
          !/^\/profile\/[^/]+\/?$/.test(url.pathname))return "";
        handle=url.pathname.slice("/profile/".length).replace(/\/$/,"");
        // Preserve valid profile URLs for the legacy verified bundle reader.
        if(handle.startsWith("did:plc:"))
          return /^did:plc:[a-z2-7]{24}$/.test(handle)?raw:"";
      }else{
        handle=handle.replace(/^@/,"");
      }
      if(handle.startsWith("did:plc:"))
        return /^did:plc:[a-z2-7]{24}$/.test(handle)?handle:"";
      if(!handle.includes(".")){
        if(!/^[A-Za-z0-9][A-Za-z0-9-]{1,61}[A-Za-z0-9]$/.test(handle))return "";
        // Bluesky default account names may be entered without .bsky.social.
        return handle.toLowerCase()+".bsky.social";
      }
      if(!publicHost(handle)||!handle.split(".").every(
        label=>/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label)))
        return "";
      return raw.startsWith("https://")?raw:handle.toLowerCase();
    }
    if(platform.value==="mastodon"){
      if(raw.startsWith("https://")){
        let url;
        try{url=new URL(raw);}catch{return "";}
        return publicHost(url.hostname)&&!url.username&&!url.password&&
          !url.port&&!url.search&&!url.hash&&
          /^\/@[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}\/?$/.test(url.pathname)?
          raw:"";
      }
      const parts=raw.replace(/^@/,"").split("@");
      return parts.length===2&&
        /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}$/.test(parts[0])&&
        publicHost(parts[1])?parts[0]+"@"+parts[1].toLowerCase():"";
    }
    return "";
  }
  function validSelection(){return normalizedAccount()!=="";}
  function refreshAccountHint(){
    if(platform.value==="bluesky"){
      account.placeholder="@example 또는 example.bsky.social";
      account.inputMode="text";
      const hint=$("targetArchiveInputHint");
      if(hint)hint.textContent="Bluesky: 이름 example, @example, @example.bsky.social 또는 프로필 URL 입력";
    }else{
      account.placeholder="@name@mastodon.social";
      account.inputMode="text";
      const hint=$("targetArchiveInputHint");
      if(hint)hint.textContent="Mastodon: @name@서버주소 또는 프로필 URL 입력 (서버 주소 필수)";
    }
  }
  function refreshButton(){
    // Never leave users with a dead button or a GitHub Actions detour.
    submit.disabled=submitting;
    submit.textContent=gatewayReady?"테라박스 백업 시작":
      (isPrivateGateway?"보관함 연결 필요":"교집합에서 계정 백업");
    workflow.hidden=true;
  }
  function openPrivateBackup(){
    if(isPrivateGateway){
      message.textContent="이 브라우저의 개인 보관함 접속 기록이 없습니다. 기존 개인 접속 링크를 한 번 열면 이후 자동으로 연결됩니다.";
      return;
    }
    // Pages supplies only public platform/account selection. The same
    // INTERSECTION app runs at the dedicated private Render origin; no
    // GitHub page, popup, credential or implicit POST occurs on navigation.
    const url=new URL(PRIVATE_GATEWAY+"/");
    url.searchParams.set("tab","accounts");
    url.searchParams.set("archive_platform",platform.value);
    url.searchParams.set("archive_account",normalizedAccount());
    message.textContent="계정 선택을 유지한 채 교집합 보관함을 엽니다. 백업 실행은 인증 후 확인합니다.";
    window.location.assign(url.href);
  }
  function restoreSelectedAccount(){
    if(!isPrivateGateway)return;
    const url=new URL(location.href);
    const chosenPlatform=url.searchParams.get("archive_platform");
    const chosenAccount=url.searchParams.get("archive_account");
    if(!chosenAccount)return;
    if(["bluesky","mastodon"].includes(chosenPlatform)){
      platform.value=chosenPlatform;
      account.value=chosenAccount;
    }
    url.searchParams.delete("archive_platform");
    url.searchParams.delete("archive_account");
    history.replaceState(null,"",url.pathname+url.search+url.hash);
    if(validSelection()){
      $("viewAccounts")?.click();
      // Give the account panel one frame to switch before scrolling.
      window.requestAnimationFrame(()=>{
        $("accountBackupSection")?.scrollIntoView({block:"start"});
      });
      message.textContent="선택한 계정이 입력됐습니다. 테라박스 백업 시작을 눌러 요청하세요.";
    }
  }
  async function check(){
    try{
      await (window.INTERSECTION_AUTH_READY||Promise.resolve());
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
      message.textContent=isPrivateGateway?
        "보관함 접속 상태를 확인하지 못했습니다. 개인 접속 링크로 한 번 열면 이후 자동으로 연결됩니다.":
        "계정을 지정하면 교집합 전용 보관함으로 이어집니다. GitHub Actions 화면으로 이동하지 않습니다. 보관함 인증 후 백업을 시작합니다.";
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
    refreshAccountHint();
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
    if(!gatewayReady){void openPrivateBackup();return;}
    const value=normalizedAccount();
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
        " · 계정을 유지한 채 다시 시도할 수 있습니다.";
      // A transient server error must not leave a permanently disabled
      // button: the account choice remains intact for another attempt.
    }finally{
      submitting=false;refreshButton();
    }
  });
  window.addEventListener("intersection:private-session-ready",()=>{
    void check();
  });
  restoreSelectedAccount();
  refreshAccountHint();
  refreshButton();
  void check();
})();
