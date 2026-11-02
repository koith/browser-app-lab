/* Account grouping view. Never infer same real person from behavioral signals. */
(function(){
"use strict";
if(location.hostname==="koith.github.io")return;
const $=id=>document.getElementById(id);
const host=$("accountsView");if(!host)return;
const node=(tag,value)=>{
 const n=document.createElement(tag);if(value!==undefined)n.textContent=String(value);return n;
};
const section=node("section");section.id="intersectionOwnerGroups";
section.setAttribute("aria-label","복수 SNS 계정 통합 그룹");
const title=node("h3","복수 SNS 계정 통합 · A 그룹 보기");
const summary=node("p","공개적으로 서로를 자신의 계정이라고 밝힌 SNS 프로필을 그룹으로 묶습니다.");
summary.id="intersectionGroupSummary";
const caveat=node("p","이 그룹은 공개 자기 계정 선언의 상호 연결 관계입니다. 법적 신원이나 동일 개인을 확정하지 않으며, 미확인 계정은 임의 병합하지 않습니다.");
const groups=node("div");groups.id="intersectionGroupRows";
const more=node("button","연결 그룹 더 보기");more.type="button";more.id="intersectionGroupMore";
section.append(title,summary,caveat,groups,more);
const before=$("privateAccountIndex")||$("intersectionAutoAccounts");
if(before)before.before(section);else host.prepend(section);
const css=node("style");
css.textContent="#intersectionOwnerGroups{background:#fff;padding:18px;border:2px solid #28469e;box-shadow:3px 3px 0 #ffda33;margin-bottom:18px;color:#14244a}"+
 "#intersectionOwnerGroups h3{font-size:18px;margin:0 0 8px}"+
 "#intersectionOwnerGroups p{font-size:12px;line-height:1.65;color:#536179}"+
 "#intersectionGroupRows details{border:1px solid #cfd9f1;margin:8px 0;padding:12px}"+
 "#intersectionGroupRows summary{cursor:pointer;font-weight:700;font-size:13px;color:#1a3a8e}"+
 "#intersectionGroupRows .group-body{padding:10px 0;display:grid;gap:6px;font-size:12px}"+
 "#intersectionGroupRows a{color:#2a4caf;overflow-wrap:anywhere}"+
 "#intersectionGroupRows span{color:#536179;margin-left:7px}"+
 "#intersectionGroupMore{border:0;background:#263dc9;color:#fff;padding:11px 16px;cursor:pointer}";
document.head.append(css);
const LIMIT=30;
let rows=[],total=0,count=null,unresolved=0,loading=false,last=0,failed="";
function render(){
 if(failed){summary.textContent="그룹 조회 불가: "+failed;more.hidden=true;return}
 if(count===null){summary.textContent="확인된 연결 관계 집계 중…";more.hidden=true;return}
 summary.textContent="수집 계정 "+Number(count).toLocaleString("ko-KR")+"개 · 양방향 자기 계정 선언 그룹 "+
  Number(total).toLocaleString("ko-KR")+"개 · 연결된 계정 "+
  Number(count-unresolved).toLocaleString("ko-KR")+"개 · 연결 미확인 "+
  Number(unresolved).toLocaleString("ko-KR")+"개";
 const fragment=document.createDocumentFragment();
 for(const group of rows){
  const details=node("details");
  details.append(node("summary","그룹 "+group.group_id+" · SNS 계정 "+group.account_count+
    "개 · 고유 원문 "+group.distinct_posts+"건 · 하루 1회 제한 기여 "+(group.capped_daily_contributions||0)+"일"));
  const body=node("div");body.className="group-body";
  body.append(node("p","연결 근거: 양방향 공개 프로필에서 서로를 자신의 계정으로 명시"));
  for(const a of group.accounts||[]){
   const line=node("div"),link=node("a",a.platform+" · "+a.profileUrl);
   link.href=a.profileUrl;link.target="_blank";link.rel="noopener noreferrer";link.referrerPolicy="no-referrer";
   line.append(link,node("span","원문 "+a.verified_posts+"건"));body.append(line);
  }
  details.append(body);fragment.append(details);
 }
 if(!rows.length)fragment.append(node("p","확인된 자기 계정 선언 그룹이 없습니다. 미발견은 운영자가 각각 다른 사람이라는 증거가 아닙니다."));
 groups.replaceChildren(fragment);
 more.hidden=rows.length>=total;
 more.disabled=loading;
 more.textContent="연결 그룹 더 보기 ("+Math.max(0,total-rows.length).toLocaleString("ko-KR")+"개 남음)";
}
async function load(reset){
 if(loading)return;
 loading=true;if(reset){rows=[];total=0}
 try{
  const params=new URLSearchParams({offset:String(rows.length),limit:String(LIMIT)});
  const res=await fetch("/api/account-groups?"+params,
   {credentials:"same-origin",cache:"no-store",headers:{"Accept":"application/json"}});
  if(!res.ok)throw Error(res.status===401?"인증 전":res.status===503?"비공개 저장소 미연결":"HTTP "+res.status);
  const data=await res.json();
  if(!Array.isArray(data.items)||!Number.isSafeInteger(data.total))throw Error("서버 데이터 형식 오류");
  rows.push(...data.items);total=data.total;count=data.account_count;unresolved=data.unresolved_accounts;
  failed="";last=Date.now();
 }catch(error){failed=String(error.message||error).slice(0,100);last=Date.now()}
 finally{loading=false;render()}
}
more.addEventListener("click",()=>load(false));
$("viewAccounts")?.addEventListener("click",()=>{if(Date.now()-last>15000)load(true)});
window.addEventListener("intersection:feed-updated",()=>{
 if(!rows.length&&Date.now()-last>15000)load(true);
});
render();
})();