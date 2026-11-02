/* INTERSECTION automatic public-account audit.
 * All discovered profile URLs are accounted for without an opt-in watch click.
 * Cross-network connections require reciprocal, exact public-profile links.
 * No hidden-account discovery, behavioral re-identification, persistent history,
 * or automated paid-provider calls.
 */
(function(){
"use strict";
const ID="intersectionAutoAccounts";
const PAGE=80, BSKY_SCAN=160, MASTODON_SCAN=32, REFRESH_MS=4*60*1000;
const $=id=>document.getElementById(id);
const mk=(tag,cls,text)=>{
 const el=document.createElement(tag);
 if(cls)el.className=cls;
 if(text!==undefined)el.textContent=String(text);
 return el;
};
const names={bluesky:"Bluesky",x:"X",threads:"Threads",instagram:"Instagram",
 mastodon:"Mastodon",misskey:"Misskey",reddit:"Reddit",lemmy:"Lemmy"};
function parseProfile(raw){
 let u;try{u=new URL(String(raw||""))}catch{return null}
 if(u.protocol!=="https:"||u.username||u.password||u.port)return null;
 const host=u.hostname.toLowerCase().replace(/^www\./,"");
 let path;try{path=decodeURIComponent(u.pathname).replace(/\/+$/,"")}catch{return null}
 const a=path.split("/").filter(Boolean);
 let network="",user="",url="";
 if(host==="bsky.app"&&a.length===2&&a[0]==="profile"&&
   /^(?:did:(?:plc|web):[\w.:-]{6,140}|[a-z0-9][a-z0-9.-]{2,199})$/i.test(a[1])){
   network="bluesky";user=a[1].toLowerCase();url="https://bsky.app/profile/"+user;
 }else if(["x.com","twitter.com"].includes(host)&&a.length===1&&/^[a-z0-9_]{1,15}$/i.test(a[0])&&
   !["home","search","explore","login","settings"].includes(a[0].toLowerCase())){
   network="x";user=a[0].toLowerCase();url="https://x.com/"+user;
 }else if(["threads.com","threads.net"].includes(host)&&a.length===1&&/^@[\w.]{1,40}$/.test(a[0])){
   network="threads";user=a[0].slice(1).toLowerCase();url="https://www.threads.com/@"+user;
 }else if(host==="instagram.com"&&a.length===1&&/^[\w.]{1,30}$/.test(a[0])&&
   !["p","reel","explore","accounts","direct"].includes(a[0].toLowerCase())){
   network="instagram";user=a[0].toLowerCase();url="https://www.instagram.com/"+user+"/";
 }else if(["mastodon.social","planet.moe","twingyeo.kr"].includes(host)&&
   a.length===1&&/^@[\w.-]{1,60}$/.test(a[0])){
   network="mastodon";user=a[0].slice(1).toLowerCase();url="https://"+host+"/@"+user;
 }else if(["misskey.io","hoto.moe"].includes(host)&&a.length===1&&/^@[\w.-]{1,60}$/.test(a[0])){
   network="misskey";user=a[0].slice(1).toLowerCase();url="https://"+host+"/@"+user;
 }else if(host==="reddit.com"&&a.length===2&&a[0].toLowerCase()==="user"&&/^[\w-]{3,20}$/.test(a[1])){
   network="reddit";user=a[1].toLowerCase();url="https://www.reddit.com/user/"+user+"/";
 }else if(host==="lemmy.world"&&a.length===2&&a[0]==="u"&&/^[\w-]{3,50}$/.test(a[1])){
   network="lemmy";user=a[1].toLowerCase();url="https://lemmy.world/u/"+user;
 }
 if(!url)return null;
 return {id:network+":"+new URL(url).host+":"+user,network,user,url};
}
function discover(){
 let snap;
 try{snap=window.INTERSECTION_publicAccountSnapshot?.()}catch{}
 const records=new Map();
 for(const [kind,arr] of [["verified",snap?.verified],["indexed",snap?.candidates]]){
  if(!Array.isArray(arr))continue;
  for(const p of arr){
   const profile=parseProfile(p?.profileUrl);if(!profile)continue;
   let rec=records.get(profile.id);
   if(!rec){rec={...profile,verified:0,indexed:0,claims:new Set()};records.set(rec.id,rec)}
   rec[kind]++;
  }
 }
 return records;
}
function findLinks(raw){
 const urls=String(raw||"").match(/https:\/\/[^\s<>"'\u0000-\u001f]+/gi)||[];
 const found=new Set();
 for(let href of urls.slice(0,70)){
  href=href.replace(/[),.;!?\]}]+$/,"");
  const p=parseProfile(href);if(p)found.add(p.id);
 }
 return found;
}
const SELF_DECLARE=/(?:my\s+(?:other|alt|alternate|second|backup)\s+(?:account|profile)|also\s+me\s+(?:on|at)|(?:내|제)\s*(?:다른|부|보조|서브)\s*계정|(?:나의|제)\s*(?:계정|SNS)\s*목록|(?:본인|같은\s*사람)의\s*(?:다른|부)\s*계정)/i;
function addClaim(row,raw){
 if(!SELF_DECLARE.test(String(raw||"")))return;
 for(const key of findLinks(raw))if(key!==row.id)row.claims.add(key);
}
async function get(url){
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),8000);
 try{
  const res=await fetch(url,{mode:"cors",credentials:"omit",cache:"no-store",headers:{"Accept":"application/json"},signal:ctrl.signal});
  if(!res.ok)throw Error("HTTP "+res.status);
  return await res.json();
 }finally{clearTimeout(timer)}
}
let records=new Map(),cursor=PAGE,groupCursor=30,scanDone=false,scanAt=0,busy=false,scheduled=false;
let scanResult={checked:0,failed:0};
function UI(){
 const host=$("accountsView");if(!host)return false;
 if($(ID))return true;
 const section=mk("section","account-auto-section");section.id=ID;
 const title=mk("h3","","공개 자기 계정 연결 그룹 · 자동 분석");
 const summary=mk("p","account-auto-summary","게시글 인덱스에서 공개 계정을 자동 집계하고 있습니다.");
 summary.id="accountAutoSummary";
 const hints=mk("p","account-auto-hint",
  "동일 SNS의 중복 프로필은 자동 정리합니다. 서로 다른 SNS 계정은 양쪽에서 자신이 운영하는 다른 계정이라고 공개 선언한 경우에만 A 그룹으로 표시합니다. 실제 개인의 신원을 확정하는 것은 아닙니다.");
 const status=mk("p","account-auto-status","");status.id="accountAutoStatus";
 const groups=mk("div","account-auto-groups");groups.id="accountAutoGroups";
 const groupMore=mk("button","account-auto-more","연결 그룹 더 보기");groupMore.id="accountAutoGroupMore";groupMore.type="button";
 groupMore.addEventListener("click",()=>{groupCursor+=30;render()});
 const listing=mk("div","account-auto-rows");listing.id="accountAutoRows";
 const more=mk("button","account-auto-more","결과 더 보기");more.type="button";more.id="accountAutoMore";
 more.addEventListener("click",()=>{cursor+=PAGE;render()});
 section.append(title,summary,hints,status,groups,groupMore,listing,more);
 const legacy=host.querySelector(".account-intro");
 if(legacy)legacy.before(section);else host.prepend(section);
 const css=mk("style");css.textContent=`
.account-auto-section{padding:20px 18px;margin:0 0 22px;background:#fff;border:2px solid #252f77;box-shadow:4px 4px 0 #ffdd29}
.account-auto-section h3{font-size:19px;margin:0 0 10px;color:#14276e}
.account-auto-section .account-auto-summary{font-size:14px;font-weight:700;color:#14276e;margin:5px 0}
.account-auto-section .account-auto-hint,.account-auto-status{font-size:12px;color:#52627d;line-height:1.6;margin:6px 0 10px}
.account-auto-groups{display:grid;gap:7px;margin:8px 0 12px}
.account-auto-groups>article{background:#eef3ff;border-left:4px solid #3451cb;padding:10px}
.account-auto-groups strong{display:block;margin-bottom:5px}
.account-auto-groups a,.account-auto-rows a{color:#2040a7;text-decoration:underline;overflow-wrap:anywhere}
.account-auto-groups a+a{margin-left:12px}
.account-auto-rows{border-top:1px solid #d6deed}
.account-auto-rows>div{display:flex;justify-content:space-between;gap:12px;align-items:center;border-bottom:1px solid #e2e7f0;padding:10px 2px;font-size:12px}
.account-auto-rows span{white-space:nowrap;color:#52627d}
.account-auto-more{background:#263dd0;color:#fff;padding:10px 16px;border:0;margin-top:12px;font-weight:700;cursor:pointer}
.account-auto-more[hidden]{display:none}
`;
 document.head.append(css);
 return true;
}
function groupsOf(rows){
 const parent=new Map([...rows.keys()].map(id=>[id,id]));
 function root(id){while(parent.get(id)!==id){parent.set(id,parent.get(parent.get(id)));id=parent.get(id)}return id}
 function join(a,b){a=root(a);b=root(b);if(a!==b)parent.set(b,a)}
 const pairs=[];
 for(const rec of rows.values())for(const target of rec.claims){
  const other=rows.get(target);
  if(other&&rec.id!==other.id&&other.claims.has(rec.id)&&rec.id<other.id){
   join(rec.id,other.id);pairs.push([rec.id,other.id]);
  }
 }
 const byRoot=new Map();
 for(const rec of rows.values()){
  const key=root(rec.id);
  if(!byRoot.has(key))byRoot.set(key,[]);
  byRoot.get(key).push(rec);
 }
 const linked=[...byRoot.values()].filter(a=>a.length>1)
  .sort((a,b)=>b.length-a.length||a[0].id.localeCompare(b[0].id));
 return {linked,pairs,unlinked:[...byRoot.values()].filter(a=>a.length===1).length};
}
function render(){
 if(!UI())return;
 const summary=$("accountAutoSummary"),status=$("accountAutoStatus"),rows=$("accountAutoRows"),groupHolder=$("accountAutoGroups");
 const values=[...records.values()].sort((a,b)=>b.verified-a.verified||b.indexed-a.indexed||a.id.localeCompare(b.id));
 const known=values.reduce((n,x)=>n+x.verified,0),indexed=values.reduce((n,x)=>n+x.indexed,0);
 const groups=groupsOf(records);
 summary.textContent="자동 발견 "+values.length.toLocaleString("ko-KR")+"개 공개 계정 · 원문 확인 글 "+known.toLocaleString("ko-KR")+
  "건 · 인덱스 링크 "+indexed.toLocaleString("ko-KR")+"건 · 상호 링크 확인 그룹 "+groups.linked.length+"개 (현재 불러온 데이터 기준)";
 const eligible=Math.min(values.filter(v=>v.network==="bluesky").length,BSKY_SCAN)+Math.min(values.filter(v=>v.network==="mastodon").length,MASTODON_SCAN);
 status.textContent="공개 프로필 근거 조회 "+scanResult.checked+"/"+eligible+
  "개 (실패 "+scanResult.failed+" · 미지원/미조회 계정은 연결 미확정)"+
  (busy?" · 자동 검증 진행 중":scanDone?" · 이번 조회 완료":"");
 const fg=document.createDocumentFragment();
 for(const [i,group] of groups.linked.slice(0,groupCursor).entries()){
  const item=mk("article");
  item.append(mk("strong","","A-"+String(i+1).padStart(3,"0")+" · 공개 자기 계정 연결 "+group.length+"개"));
  for(const rec of group){
   const a=mk("a","",(names[rec.network]||rec.network)+" @"+rec.user);
   a.href=rec.url;a.target="_blank";a.rel="noopener noreferrer";item.append(a);
  }fg.append(item);
 }
 if(!groups.linked.length)fg.append(mk("p","account-auto-hint",
   scanDone?"이번에 검사한 공개 프로필에서는 상호 링크를 확인하지 못했습니다. 미확인 계정을 별도 사용자로 단정하지 않습니다.":
   "상호 링크가 확인되면 이곳에 자동 표시됩니다."));
 groupHolder.replaceChildren(fg);
 $("accountAutoGroupMore").hidden=groups.linked.length<=groupCursor;
 $("accountAutoGroupMore").textContent="연결 그룹 더 보기 ("+Math.max(0,groups.linked.length-groupCursor)+"개 남음)";
 const frag=document.createDocumentFragment();
 for(const rec of values.slice(0,cursor)){
  const line=mk("div");
  const a=mk("a","",(names[rec.network]||rec.network)+" @"+rec.user);
  a.href=rec.url;a.target="_blank";a.rel="noopener noreferrer";
  line.append(a,mk("span","","글 "+rec.verified+" · 링크 "+rec.indexed));
  frag.append(line);
 }
 rows.replaceChildren(frag);
 $("accountAutoMore").hidden=cursor>=values.length;
 $("accountAutoMore").textContent="결과 더 보기 ("+Math.max(0,values.length-cursor).toLocaleString("ko-KR")+"개 남음)";
}
function refresh(){
 const next=discover(),previousSize=records.size;
 const unchanged=next.size===records.size&&[...next].every(([key,v])=>{
  const old=records.get(key);return old&&old.verified===v.verified&&old.indexed===v.indexed;
 });
 if(unchanged)return;
 for(const [key,rec] of next){
  const old=records.get(key);
  if(old)rec.claims=old.claims;
 }
 records=next;render();
 if(!busy&&(next.size!==previousSize||!scanDone||Date.now()-scanAt>REFRESH_MS))scan().catch(()=>{});
}
function schedule(){
 if(scheduled)return;scheduled=true;
 requestAnimationFrame(()=>{scheduled=false;refresh()});
}
async function scan(){
 if(busy||!records.size)return;
 busy=true;scanDone=false;scanAt=Date.now();scanResult={checked:0,failed:0,skipped:0};render();
 const bsky=[...records.values()].filter(v=>v.network==="bluesky").slice(0,BSKY_SCAN);
 const mast=[...records.values()].filter(v=>v.network==="mastodon").slice(0,MASTODON_SCAN);
 // Batch requests to the official public Bluesky AppView. No API token.
 for(let i=0;i<bsky.length;i+=20){
  const batch=bsky.slice(i,i+20);
  const q=new URLSearchParams();
  batch.forEach(v=>q.append("actors",v.user));
  try{
   const response=await get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles?"+q);
   const got=new Map();
   for(const p of Array.isArray(response.profiles)?response.profiles:[]){
    if(p.handle)got.set(String(p.handle).toLowerCase(),p);
    if(p.did)got.set(String(p.did).toLowerCase(),p);
   }
   for(const row of batch){
    const profile=got.get(row.user);
    if(profile){addClaim(row,profile.description||"");scanResult.checked++}
    else scanResult.failed++;
   }
  }catch{scanResult.failed+=batch.length}
  render();
 }
 // Other providers are not mass-queried. This is a small bounded public lookup.
 for(const row of mast){
  try{
   const origin=new URL(row.url).origin;
   const p=await get(origin+"/api/v1/accounts/lookup?"+new URLSearchParams({acct:row.user}));
   if(p?.locked||p?.suspended){scanResult.failed++;continue}
   const doc=new DOMParser().parseFromString(String(p?.note||""),"text/html");
   const note=String(doc.body.textContent||"");
   for(const f of p?.fields||[]){
    const d=new DOMParser().parseFromString(String(f.value||""),"text/html");
    const label=String(f.name||"")+" "+String(d.body.textContent||"");
    for(const link of d.querySelectorAll("a[href]"))addClaim(row,label+" "+link.href);
   }
   for(const link of doc.querySelectorAll("a[href]"))addClaim(row,note+" "+link.href);
   scanResult.checked++;
  }catch{scanResult.failed++}
  render();
 }
 busy=false;scanDone=true;render();
}
window.INTERSECTION_autoAccountStats=()=>({
 accountCount:records.size,linkGroups:groupsOf(records).linked.length,
 profileChecks:scanResult.checked,failedChecks:scanResult.failed,
 checkedScope:"currently loaded public post snapshot",scanFinished:scanDone
});
if(!UI())return;
window.addEventListener("intersection:feed-updated",schedule);
window.addEventListener("intersection:date-range-change",schedule);
$("viewAccounts")?.addEventListener("click",()=>{refresh();render()});
refresh();
})();