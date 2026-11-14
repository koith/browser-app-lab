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
  let pendingJobs=[];
  const pollTimers=new Map(),polling=new Set();
  let submitSequence=Promise.resolve();
  let connectionAttempting=false;
  let inlineStatus=null;
  function notifyInline(text,state){
    if(typeof inlineStatus==="function"){
      try{inlineStatus(text,state);}catch{/* Modal may have been closed. */}
    }
  }

  const JOB_KEY="intersection:private-archive-job:v1";
  const JOBS_KEY="intersection:private-archive-jobs:v2";
  function safeJob(job){
    return job&&Number.isSafeInteger(job.run_id)&&job.run_id>0&&
      typeof job.receipt==="string"&&job.receipt.length<900&&
      ["bluesky","mastodon"].includes(job.platform)&&
      typeof job.account==="string"&&job.account.length<400;
  }
  function resumeReceipts(){
    try{
      const stored=JSON.parse(sessionStorage.getItem(JOBS_KEY)||"[]");
      if(Array.isArray(stored)){
        const unique=new Map();
        for(const row of stored.slice(-64))if(safeJob(row))
          unique.set(row.run_id,row);
        if(unique.size)return [...unique.values()];
      }
    }catch{}
    try{
      const old=JSON.parse(sessionStorage.getItem(JOB_KEY)||"null");
      if(safeJob(old))return [old];
    }catch{}
    return [];
  }
  function saveReceipt(value,finished=null){
    if(value&&safeJob(value)){
      if(!pendingJobs.some(job=>job.run_id===value.run_id))
        pendingJobs.push(value);
      pendingJobs=pendingJobs.slice(-64);
    }
    if(finished){
      const id=finished.run_id;
      pendingJobs=pendingJobs.filter(job=>job.run_id!==id);
    }
    try{
      if(pendingJobs.length){
        sessionStorage.setItem(JOBS_KEY,JSON.stringify(pendingJobs));
        sessionStorage.setItem(JOB_KEY,JSON.stringify(pendingJobs[pendingJobs.length-1]));
      }else{
        sessionStorage.removeItem(JOBS_KEY);
        sessionStorage.removeItem(JOB_KEY);
      }
    }catch{/* Session storage can be disabled; server receipts remain authoritative. */}
    renderQueueInfo();
  }
  const queueInfo=document.createElement("p");
  queueInfo.className="target-archive-queue-count";
  queueInfo.setAttribute("role","status");
  queueInfo.hidden=true;
  jobStatus.after(queueInfo);
  function renderQueueInfo(){
    queueInfo.hidden=!pendingJobs.length;
    queueInfo.textContent=pendingJobs.length?
      "접수된 미완료 백업 "+pendingJobs.length+"건 · 이전 작업도 유지하고 순서대로 진행 상태를 확인합니다.":"";
  }
  function clearPoll(job){
    if(!job)return;
    const timer=pollTimers.get(job.run_id);
    if(timer!==undefined){window.clearTimeout(timer);pollTimers.delete(job.run_id)}
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
    notifyInline(text,kind||"running");
    if(accountKey)appendViewerLink(jobStatus,accountKey,"저장된 자료 열기");
  }
  async function loadLibrary(){
    if(!gatewayReady)return;
    library.hidden=false;
    libraryRows.textContent="검증된 계정 보관본을 확인 중…";
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
          (["terabox_zip_sha_verified","github_temp_sha_verified"].includes(item.backup_kind)
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
  // Each accepted public account has its OWN signed receipt and poll timer.
  // A later selected account never cancels or replaces an earlier job.
  async function pollJob(job=currentRun){
    if(!gatewayReady||!job||!pendingJobs.includes(job)||polling.has(job.run_id))return;
    clearPoll(job);polling.add(job.run_id);
    const visible=(text,kind,accountKey)=>{
      job.state=kind;
      if(currentRun===job)showJob(text,kind,accountKey);
      renderQueueInfo();
    };
    try{
      const response=await fetch("/api/target-archive/jobs/"+
        encodeURIComponent(String(job.run_id))+"?receipt="+
        encodeURIComponent(job.receipt),{
          credentials:"same-origin",cache:"no-store",
          headers:{Accept:"application/json"}
        });
      if(!response.ok)throw Error("Job status HTTP "+response.status);
      const result=await response.json();
      if(!pendingJobs.includes(job))return;
      const count=Number(result.posts||0);
      switch(result.state){
        case "QUEUED":
          visible("백업 접수 완료 · 작업 실행 대기 중 · 기존 요청도 계속 진행됩니다.","queued");
          break;
        case "RUNNING":
          visible("백업 진행 중 · 공개 자료를 수집해 암호화 저장합니다.","running");break;
        case "VERIFYING_STORAGE":
          visible("저장된 원본을 다시 읽어 무결성을 검증 중입니다.","verifying");break;
        case "REMOTE_VERIFIED":
        case "PARTIAL_BACKUP":
          visible((result.state==="REMOTE_VERIFIED"
            ?"검증된 백업 · 게시글 "+count+"건 · 원본 "+Number(result.objects||0)+"개"
            :"일부 백업 완료 · 게시글 "+count+"건 · 미수집 구간 남음"),
            "verified",String(result.account_key||""));
          saveReceipt(null,job);
          if(currentRun===job)currentRun=pendingJobs[pendingJobs.length-1]||null;
          void loadLibrary();
          return;
        case "NEEDS_RETRY":
        case "FAILED":
          visible(result.state==="NEEDS_RETRY"?
            "기존 작업 대기 기록이 만료됐습니다. 보관함에서 저장 결과를 확인해 주세요.":
            "백업 실패 · 다른 접수 작업은 유지되며 이 작업은 재시도할 수 있습니다.","failed");
          saveReceipt(null,job);
          if(currentRun===job)currentRun=pendingJobs[pendingJobs.length-1]||null;
          return;
        default:
          visible("백업 상태 확인 중입니다.","running");
      }
    }catch{
      if(pendingJobs.includes(job))
        visible("접수된 백업의 진행 상태를 다시 확인 중입니다.","verifying");
    }finally{
      polling.delete(job.run_id);
      if(pendingJobs.includes(job)){
        const timer=window.setTimeout(()=>{pollTimers.delete(job.run_id);void pollJob(job)},12000);
        pollTimers.set(job.run_id,timer);
      }else clearPoll(job);
    }
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
    submit.disabled=submitting||connectionAttempting;
    submit.textContent=isPrivateGateway?"백업 시작":"교집합에서 계정 백업";
    workflow.hidden=true;
  }
  function openPrivateBackup(){
    if(isPrivateGateway){
      message.textContent="저장소 연결을 다시 확인 중입니다. 계정 입력은 유지됩니다.";
      void check();return;
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
      message.textContent="선택한 계정이 입력됐습니다. 백업 시작을 눌러 요청하세요.";
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
        ?"계정 이름 또는 주소를 입력하고 백업 시작을 누르세요. 이 화면에서 진행 상태를 표시합니다."
        :"비공개 보관함은 열 수 있지만 새 백업 요청 권한이 설정되지 않았습니다.";
      if(gatewayReady){
        void loadLibrary();
        const remembered=resumeReceipts();
        if(remembered.length){
          for(const job of remembered)
            if(!pendingJobs.some(j=>j.run_id===job.run_id))pendingJobs.push(job);
          currentRun=pendingJobs[pendingJobs.length-1];
          showJob("기존 백업 "+pendingJobs.length+"건의 접수·진행 상태를 확인 중…","running");
          renderQueueInfo();
          for(const job of pendingJobs)void pollJob(job);
        }
      }
    }catch{
      viewer.hidden=true;
      gatewayReady=false;
      message.textContent=isPrivateGateway?
        "원격 저장소 연결 확인 중입니다. 준비되면 이 화면에서 바로 백업을 실행합니다.":
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
  async function submitCurrentSelection(fromPost=false){
    if(submitting||connectionAttempting){
      notifyInline("이미 백업 요청을 처리 중입니다. 중복 요청하지 않습니다.","running");
      return {accepted:false,reason:"submitting"};
    }
    if(!validSelection()){
      account.setAttribute("aria-invalid","true");
      message.textContent="먼저 공개 SNS 계정 주소 또는 핸들을 입력하세요. "+
        "예: https://bsky.app/profile/example.bsky.social / @user@example.social";
      if(!fromPost)account.focus();
      notifyInline(message.textContent,"failed");
      return {accepted:false,reason:"invalid_account"};
    }
    account.removeAttribute("aria-invalid");
    if(!gatewayReady){
      if(!isPrivateGateway){
        if(fromPost){
          const text="현재 공개 미러에서는 직접 저장할 수 없습니다. 교집합 전용 보관앱에서 이 게시글을 열어 백업하세요.";
          message.textContent=text;notifyInline(text,"failed");
          return {accepted:false,reason:"public_mirror"};
        }
        openPrivateBackup();return {accepted:false,reason:"public_mirror"};
      }
      message.textContent="저장소를 연결 중입니다. 백업 요청을 자동으로 다시 시도합니다.";
      connectionAttempting=true;
      refreshButton();
      try{
        for(let attempt=0;attempt<4&&!gatewayReady;attempt++){
          await check();
          if(!gatewayReady)await new Promise(resolve=>setTimeout(resolve,2500));
        }
      }finally{
        connectionAttempting=false;
        refreshButton();
      }
      if(!gatewayReady){
        message.textContent="테라박스 서버가 아직 복구되지 않았습니다. 계정은 유지됩니다. 백업을 접수하지 않았습니다.";
        notifyInline(message.textContent,"failed");
        return {accepted:false,reason:"gateway_unavailable"};
      }
    }
    const value=normalizedAccount();
    submitting=true;
    refreshButton();
    message.textContent="비공개 아카이브 작업 요청 중…";
    notifyInline(message.textContent,"running");
    try{
      const response=await fetch("/api/target-archive/start",{
        method:"POST",credentials:"same-origin",cache:"no-store",
        headers:{"Content-Type":"application/json",
                 "X-Archive-Intent":"selected-public-account-v1"},
        body:JSON.stringify({platform:platform.value,account:value})
      });
      if(!response.ok){
        if(response.status===429)throw new Error("짧은 시간에 여러 번 요청했습니다. 잠시 후 재시도하세요.");
        if(response.status===503){
          const failure=await response.json().catch(()=>({}));
          if(failure.code==="storage_read_denied")throw new Error("TeraBox가 백업 요청의 원격 읽기를 거부했습니다. 접수·무결성을 확인하지 못했습니다. 저장소 인증과 다운로드 권한을 확인해야 합니다.");
          throw new Error("백업 서버가 준비되지 않았습니다. 잠시 후 다시 시도하세요.");
        }
        throw new Error("백업 작업 요청 실패 (HTTP "+response.status+")");
      }
      const result=await response.json();
      if(result.state!=="QUEUED_NOT_VERIFIED"||result.accepted!==true||
         !Number.isSafeInteger(result.run_id)||typeof result.receipt!=="string")
        throw new Error("백업 작업 번호를 확인하지 못했습니다.");
      currentRun={run_id:result.run_id,receipt:result.receipt,
                  platform:platform.value,account:value};
      saveReceipt(currentRun);
      message.textContent="새 계정 백업을 접수했습니다. 기존 백업도 계속 진행됩니다.";
      showJob("백업 접수 완료 · 현재 미완료 요청 "+pendingJobs.length+
        "건 · 저장 완료 여부는 별도 검증이 필요합니다.","queued");
      void pollJob(currentRun);
      return {accepted:true,state:"QUEUED_NOT_VERIFIED",run_id:result.run_id};
    }catch(error){
      message.textContent=String(error.message||"아카이브 요청 실패")+
        " · 계정을 유지한 채 다시 시도할 수 있습니다.";
      notifyInline(message.textContent,"failed");
      // A transient server error must not leave a permanently disabled
      // button: the account choice remains intact for another attempt.
      return {accepted:false,reason:"server_error"};
    }finally{
      submitting=false;refreshButton();
    }
  }
  // Keep the browser's POSTs in order. The server's independent queue then
  // schedules execution; the oldest pending job never blocks new selection.
  function queueSubmission(selection,onStatus,fromPost){
    const run=()=>{
      if(selection){
        platform.value=selection.platform;
        account.value=selection.profileUrl;
        platform.dispatchEvent(new Event("change",{bubbles:true}));
        account.dispatchEvent(new Event("input",{bubbles:true}));
      }
      inlineStatus=typeof onStatus==="function"?onStatus:null;
      return submitCurrentSelection(fromPost);
    };
    const pending=submitSequence.then(run,run);
    submitSequence=pending.then(()=>{},()=>{});
    return pending;
  }
  form.addEventListener("submit",event=>{
    event.preventDefault();
    void queueSubmission({platform:platform.value,profileUrl:account.value},null,false);
  });
  // Called by the saved-post modal. The server still validates the POST.
  // Never auto-POST for URL parameters, unverified snippets or cross-origin links.
  window.INTERSECTION_startPublicAccountBackup=async (selection,onStatus)=>{
    if(!selection||typeof selection!=="object"||
       !["bluesky","mastodon"].includes(selection.platform)||
       typeof selection.profileUrl!=="string"){
      if(typeof onStatus==="function")onStatus("지원되는 공개 Bluesky·Mastodon 계정만 백업할 수 있습니다.","failed");
      return {accepted:false,reason:"unsupported"};
    }
    if(!isPrivateGateway){
      if(typeof onStatus==="function")onStatus("현재 공개 미러에서는 직접 백업을 실행할 수 없습니다. 보관앱에서 열어 실행해야 합니다.","failed");
      return {accepted:false,reason:"public_mirror"};
    }
    // Explicitly confirmed new accounts must not be refused because a
    // previous run has a signed receipt. Queue the next POST behind any
    // currently submitting request, preserving all earlier job IDs.
    return queueSubmission(selection,onStatus,true);
  };
  window.addEventListener("intersection:private-session-ready",()=>{
    void check();
  });
  restoreSelectedAccount();
  refreshAccountHint();
  refreshButton();
  void check();
})();
