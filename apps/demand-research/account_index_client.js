/* Private all-corpus account index viewer. No direct public API and no client writes.
 * Public Pages continues its separately scoped in-memory audit. */
(function(){
"use strict";
if(location.hostname==="koith.github.io")return;
const $=id=>document.getElementById(id);
const host=$("accountsView");if(!host)return;
const privateDetails=$("accountServerData");
if(privateDetails){
  // Keep the complete server directory behind an explicit disclosure click.
  privateDetails.hidden=false;
}
const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);return node};
const panel=el("section");panel.id="privateAccountIndex";
panel.className="account-auto-section";
const title=el("h3","서버에 저장된 전체 계정");
const summary=el("p","서버에 저장된 계정 수를 확인 중입니다.");summary.id="privateAccountSummary";
const caution=el("p","이 숫자는 교집합이 확인한 계정 수입니다. 전체 SNS 계정 수나 실제 사람 수를 뜻하지 않습니다.");
const toolbar=el("div");toolbar.className="account-auto-filters";
const term=el("input");term.type="search";term.placeholder="전체 계정에서 검색";term.setAttribute("aria-label","누적 공개 계정 검색");
const source=el("select");source.setAttribute("aria-label","SNS 필터");
for(const [key,label] of [["","모든 SNS"],["bluesky","Bluesky"],["x","X"],["threads","Threads"],
 ["instagram","Instagram"],["mastodon","Mastodon"],["misskey","Misskey"],["reddit","Reddit"],["lemmy","Lemmy"]]){
 const opt=el("option",label);opt.value=key;source.append(opt);
}
toolbar.append(term,source);
const list=el("div");list.className="account-auto-rows";list.id="privateAccountRows";
const more=el("button","계정 더 보기");more.type="button";more.className="account-auto-more";
panel.append(title,summary,caution,toolbar,list,more);
const mount=$("privateAccountIndexMount");
const local=$("intersectionAutoAccounts");
if(mount)mount.append(panel);
else if(local)local.before(panel);
else host.prepend(panel);
const style=el("style");
style.textContent="#privateAccountIndex{background:white;border:2px solid #293eb3;padding:16px;margin-bottom:12px}"+
 "#privateAccountIndex h3{margin:0 0 8px;font-size:19px}"+
 "#privateAccountIndex p{font-size:12px;color:#4f5d76}"+
 "#privateAccountIndex .account-auto-filters{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}"+
 "#privateAccountIndex input,#privateAccountIndex select{border:1px solid #a7b4cb;padding:9px;font-size:12px}"+
 "#privateAccountIndex input{min-width:180px;flex:1}"+
 "#privateAccountIndex .account-auto-rows>div{display:flex;gap:8px;justify-content:space-between;padding:10px;border-bottom:1px solid #dbe3f1;font-size:12px}"+
 "#privateAccountIndex a{color:#243da8;overflow-wrap:anywhere}"+
 "#privateAccountIndex button{border:0;background:#263dcc;color:white;padding:10px 16px;margin-top:12px;cursor:pointer}";
document.head.append(style);
const LIMIT=80;
let data=null,rows=[],busy=false,pendingReset=false,pendingMore=false,userPaged=false,lastFetch=0,query="",platform="",error="",poll=0;
const option={credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}};
function render(){
 if(!data){
   summary.textContent=error?"비공개 계정 DB: "+error:"계정 인덱스 연결 확인 중…";
   more.hidden=true;return;
 }
 summary.textContent="서버에 저장된 계정 "+Number(data.accounts).toLocaleString("ko-KR")+"개 · 확인된 게시글 "+
  Number(data.source_rows).toLocaleString("ko-KR")+"건"+
  (data.refreshing?" · 목록 갱신 중":"");
 const w=data.public_scan_windows||{};
 caution.textContent="공개 Bluesky 조회: 완료 "+(w.done||0)+" · 대기 "+(w.pending||0)+
   " · 미완료 "+(w.incomplete||0)+" · 확인 실패 "+(w.failed||0)+
   ". 다른 SNS는 연결된 수집 출처에서 확인된 자료만 포함합니다.";
 const frag=document.createDocumentFragment();
 for(const record of rows){
   const div=el("div");const a=el("a",record.platform+" · "+record.profileUrl);
   a.href=record.profileUrl;a.target="_blank";a.rel="noopener noreferrer";a.referrerPolicy="no-referrer";
   div.append(a,el("span","원문 확인 "+record.verified_posts+"건"));frag.append(div);
 }
 if(!rows.length)frag.append(el("p",busy?"서버 목록 조회 중…":"일치하는 보관 계정이 없습니다."));
 list.replaceChildren(frag);
 more.hidden=rows.length>=(data.filtered_total??data.accounts);more.disabled=busy;
 more.textContent="더 보기 ("+Math.max(0,(data.filtered_total??data.accounts)-rows.length).toLocaleString("ko-KR")+"개 남음)";
}
async function load(reset){
 // Changing search/provider while an earlier GET is in flight must never
 // silently discard the user's latest selection. Coalesce into one reload.
 if(busy){
  // A pagination click can land between two asynchronous status requests.
  // Never throw away an acknowledged user action; a changed search/filter
  // takes precedence over appending stale results from the old selection.
  if(reset){pendingReset=true;pendingMore=false}
  else if(!pendingReset)pendingMore=true;
  return;
 }
 busy=true;
 if(reset){rows=[];data=null}
 try{
   await (window.INTERSECTION_AUTH_READY||Promise.resolve());
   const statusResp=await fetch("/api/accounts/status",option);
   if(!statusResp.ok)throw Error(statusResp.status===401?"비공개 세션 미인증":statusResp.status===503?"인덱스 저장소 미설정":"HTTP "+statusResp.status);
   const stats=await statusResp.json();
   const params=new URLSearchParams({offset:String(rows.length),limit:String(LIMIT)});
   if(query)params.set("q",query);if(platform)params.set("platform",platform);
   const pageResp=await fetch("/api/accounts?"+params,option);
   if(!pageResp.ok)throw Error("목록 HTTP "+pageResp.status);
   const page=await pageResp.json();
   rows.push(...page.items);data={...stats,filtered_total:page.total};error="";lastFetch=Date.now();
   if(stats.refreshing&&!userPaged&&poll++<6)
    setTimeout(()=>{if(!userPaged)load(true)},5000);
   // The local audit remains visible for independently verified reciprocal links.
 }catch(e){error=String(e.message||e).slice(0,90);lastFetch=Date.now()}
 finally{
  busy=false;
  render();
  if(pendingReset){
   pendingReset=false;
   pendingMore=false;
   load(true);
  }else if(pendingMore){
   pendingMore=false;
   load(false);
  }
 }
}
more.addEventListener("click",()=>{userPaged=true;load(false)});
// Mobile WebKit's search input can remain focused while its value is
// cleared (including the native clear button). Relying only on "change"
// meant no new request until blur and sometimes lost the reset entirely.
let searchTimer=null;
function apply(){
 if(searchTimer!==null){clearTimeout(searchTimer);searchTimer=null}
 const nextQuery=term.value.trim().slice(0,80);
 const nextPlatform=source.value;
 if(query===nextQuery&&platform===nextPlatform)return;
 query=nextQuery;platform=nextPlatform;poll=0;userPaged=false;
 load(true);
}
term.addEventListener("input",()=>{
 if(searchTimer!==null)clearTimeout(searchTimer);
 searchTimer=setTimeout(apply,220);
});
term.addEventListener("search",apply);
term.addEventListener("change",apply);
source.addEventListener("change",apply);
$("viewAccounts")?.addEventListener("click",()=>{if(Date.now()-lastFetch>12000){poll=0;load(true)}});
window.addEventListener("intersection:feed-updated",()=>{if(!data&&Date.now()-lastFetch>12000)load(true)});
render();
})();