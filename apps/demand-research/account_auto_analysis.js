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
let records=new Map(),cursor=PAGE,groupCursor=30,scanDone=false,scanAt=0,busy=false,scheduled=false,searchTerm="";
let scanResult={checked:0,failed:0};
function UI(){
 const host=$("accountsView");if(!host)return false;
 if($(ID))return true;
 const section=mk("section","account-auto-section");section.id=ID;
 const summary=mk("p","account-auto-summary","현재 불러온 공개 계정을 확인하는 중입니다.");
 summary.id="accountAutoSummary";
 const title=mk("h3","","같은 운영자가 공개적으로 연결한 계정");
 const groups=mk("div","account-auto-groups");groups.id="accountAutoGroups";
 const groupMore=mk("button","account-auto-more","연결 그룹 더 보기");groupMore.id="accountAutoGroupMore";groupMore.type="button";
 groupMore.addEventListener("click",()=>{groupCursor+=30;render()});
 const listHead=mk("div","account-auto-list-head");
 listHead.append(mk("h4","","발견된 계정 목록"));
 const search=mk("input");search.type="search";search.id="accountAutoSearch";
 search.placeholder="계정 이름 또는 SNS 검색";search.setAttribute("aria-label","발견된 계정 검색");
 search.addEventListener("input",()=>{searchTerm=search.value.trim().toLowerCase();cursor=PAGE;render()});
 listHead.append(search);
 const listing=mk("div","account-auto-rows");listing.id="accountAutoRows";
 const more=mk("button","account-auto-more","계정 더 보기");more.type="button";more.id="accountAutoMore";
 more.addEventListener("click",()=>{cursor+=PAGE;render()});
 const status=mk("p","account-auto-status","");status.id="accountAutoStatus";
 const hints=mk("details","account-auto-method");
 hints.append(mk("summary","","계정 연결은 어떻게 확인하나요?"),
  mk("p","account-auto-hint","프로필 양쪽에서 서로를 다른 SNS 계정이라고 공개적으로 소개한 경우에만 연결된 그룹으로 표시합니다. 미확인 계정은 다른 사람이라고 단정하지 않습니다. 수치는 현재 불러온 게시글 기준이며 전체 SNS 계정 수가 아닙니다."));
 section.append(summary,title,groups,groupMore,listHead,listing,more,status,hints);
 const mount=$("accountAutoMount");
 const legacy=host.querySelector(".account-intro");
 if(mount)mount.append(section);
 else if(legacy)legacy.after(section);
 else host.prepend(section);
 const css=mk("style");css.textContent=`
#accountAutoMount .account-auto-section{padding:0;margin:0;background:transparent;border:0;box-shadow:none}
#accountAutoMount .account-auto-section h3{font-size:14px;font-weight:850;color:#273653;margin:17px 0 9px}
#accountAutoMount .account-auto-summary{font-size:13px;font-weight:750;color:#334b85;background:#f0f5ff;border-radius:9px;padding:12px 13px;margin:0;line-height:1.55}
#accountAutoMount .account-auto-groups{display:grid;gap:8px;margin:8px 0 8px}
#accountAutoMount .account-auto-groups>article{background:#f8faff;border:1px solid #dce4f3;border-radius:9px;padding:11px 12px}
#accountAutoMount .account-auto-groups strong{display:block;font-size:12px;margin-bottom:6px;color:#263c70}
#accountAutoMount .account-auto-groups a,#accountAutoMount .account-auto-rows a{color:#2646a0;text-decoration:none;overflow-wrap:anywhere;font-weight:700}
#accountAutoMount .account-auto-groups a{display:inline-flex;padding:5px 0;margin-right:12px;font-size:12px}
#accountAutoMount .account-auto-groups a:hover,#accountAutoMount .account-auto-rows a:hover{text-decoration:underline}
#accountAutoMount .account-auto-list-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:15px}
#accountAutoMount .account-auto-list-head h4{font-size:14px;margin:0;color:#263653}
#accountAutoMount .account-auto-list-head input{border:1px solid #cbd6e8;border-radius:8px;padding:9px 10px;min-width:0;width:235px;font-size:12px}
#accountAutoMount .account-auto-rows{border-top:1px solid #e1e6f0;margin-top:9px}
#accountAutoMount .account-auto-rows>div{display:flex;justify-content:space-between;gap:10px;align-items:center;border-bottom:1px solid #e9edf4;padding:10px 3px;font-size:12px}
#accountAutoMount .account-auto-rows span{color:#67748b;white-space:nowrap;font-size:11px}
#accountAutoMount .account-auto-status{font-size:11px;color:#64718b;line-height:1.65;margin:12px 0}
#accountAutoMount .account-auto-method{border-top:1px solid #e7eaf2;margin-top:14px;padding-top:5px}
#accountAutoMount .account-auto-method summary{color:#526895;font-size:11px;cursor:pointer;padding:7px 0}
#accountAutoMount .account-auto-hint{font-size:11px;color:#67748b;line-height:1.7;margin:8px 0}
#accountAutoMount .account-auto-more{background:#f1f5ff;border:1px solid #d5def2;border-radius:8px;color:#274398;padding:9px 13px;margin-top:9px;font-size:11px;font-weight:800;cursor:pointer}
#accountAutoMount .account-auto-more[hidden]{display:none}
@media(max-width:720px){
 #accountAutoMount .account-auto-list-head{align-items:stretch;flex-direction:column}
 #accountAutoMount .account-auto-list-head input{width:100%}
 #accountAutoMount .account-auto-rows>div{align-items:flex-start;flex-direction:column;gap:3px}
 #accountAutoMount .account-auto-rows span{white-space:normal}
}
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
 summary.textContent="현재 발견된 계정 "+values.length.toLocaleString("ko-KR")+"개 · 공개 게시글 "+known.toLocaleString("ko-KR")+"건 · 공개 연결 확인 그룹 "+groups.linked.length+"개";
 summary.title="추가로 확인이 필요한 링크 "+indexed.toLocaleString("ko-KR")+"건";
 const eligible=Math.min(values.filter(v=>v.network==="bluesky").length,BSKY_SCAN)+Math.min(values.filter(v=>v.network==="mastodon").length,MASTODON_SCAN);
 status.textContent="연결 확인을 위해 살펴본 프로필 "+scanResult.checked.toLocaleString("ko-KR")+
  "/"+eligible.toLocaleString("ko-KR")+"개"+
  (busy?" · 확인 중":scanDone?" · 이번 확인 완료":"")+
  (scanResult.failed?" · 확인하지 못한 프로필 "+scanResult.failed+"개":"");
 const fg=document.createDocumentFragment();
 for(const [i,group] of groups.linked.slice(0,groupCursor).entries()){
  const item=mk("article");
  item.append(mk("strong","","연결 그룹 "+(i+1)+" · 공개적으로 연결된 SNS 계정 "+group.length+"개"));
  for(const rec of group){
   const a=mk("a","",(names[rec.network]||rec.network)+" @"+rec.user);
   a.href=rec.url;a.target="_blank";a.rel="noopener noreferrer";item.append(a);
  }fg.append(item);
 }
 if(!groups.linked.length)fg.append(mk("p","account-auto-hint",
   scanDone?"확인된 계정 연결이 아직 없습니다. 연결이 없다는 이유만으로 서로 다른 사람으로 계산하지는 않습니다.":
   "공개 프로필에 연결된 다른 SNS 계정이 있는지 확인 중입니다."));
 groupHolder.replaceChildren(fg);
 $("accountAutoGroupMore").hidden=groups.linked.length<=groupCursor;
 $("accountAutoGroupMore").textContent="연결 그룹 더 보기 ("+Math.max(0,groups.linked.length-groupCursor)+"개 남음)";
 const frag=document.createDocumentFragment();
 const filtered=searchTerm?values.filter(rec=>
   rec.user.includes(searchTerm)||(names[rec.network]||rec.network).toLowerCase().includes(searchTerm)):values;
 for(const rec of filtered.slice(0,cursor)){
  const line=mk("div");
  const a=mk("a","",(names[rec.network]||rec.network)+" @"+rec.user);
  a.href=rec.url;a.target="_blank";a.rel="noopener noreferrer";
  line.append(a,mk("span","","확인 글 "+rec.verified+"건"+(rec.indexed?" · 확인 대기 링크 "+rec.indexed+"건":"")));
  frag.append(line);
 }
 if(!filtered.length)frag.append(mk("p","account-auto-hint","검색한 계정을 찾지 못했습니다."));
 rows.replaceChildren(frag);
 $("accountAutoMore").hidden=cursor>=filtered.length;
 $("accountAutoMore").textContent="계정 더 보기 ("+Math.max(0,filtered.length-cursor).toLocaleString("ko-KR")+"개 남음)";
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