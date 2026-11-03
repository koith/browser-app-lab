/* INTERSECTION: explicitly selected public account archive.
 * Works only in authenticated private gateway, never stores credentials or
 * profile history in Pages/localStorage. A queued job is not a saved record.
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
  let ready=false;
  async function check(){
    try{
      const response=await fetch("/api/target-archive/status",{
        credentials:"same-origin",cache:"no-store"});
      if(!response.ok)throw new Error("private gateway unavailable");
      const result=await response.json();
      ready=Boolean(result.enabled);
      submit.disabled=!ready;
      message.textContent=ready
        ?"개인용 보관 서버 연결됨 · 공개 게시글과 직접 작성한 답글, 원본 첨부를 순차 백업합니다."
        :"서버의 아카이브 실행 권한이 아직 설정되지 않았습니다. GitHub Actions에서 직접 실행할 수 있습니다.";
    }catch{
      ready=false;
      submit.disabled=true;
      message.textContent="공개 Pages에서는 직접 백업을 실행하지 않습니다. 아래 GitHub Actions에서 계정을 지정해 실행하세요.";
    }
    workflow.hidden=ready;
  }
  form.addEventListener("submit",async e=>{
    e.preventDefault();
    if(!ready){message.textContent="비공개 보관 서버 미연결";return;}
    const value=account.value.trim();
    if(value.length<3||value.length>260)return;
    submit.disabled=true;
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
      message.textContent="작업 요청 접수. 현재는 대기 상태이며, 테라박스 저장 성공이 확인된 것은 아닙니다. 기존 계정 데이터는 지우지 않습니다.";
      account.value="";
    }catch(error){
      message.textContent=String(error.message||"아카이브 요청 실패");
    }finally{submit.disabled=!ready;}
  });
  void check();
})();
