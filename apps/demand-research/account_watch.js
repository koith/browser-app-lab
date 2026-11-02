/* INTERSECTION public-account watch: local opt-in watch list, source-scoped
 * public feeds, deduplicated content signals. No inferred same-person identity,
 * no login/cookies, no private-account data and no persistent post archive. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
if(!$("accountsView")||typeof window.INTERSECTION_publicAccountSnapshot!=="function")return;
const STORE="intersection:public-account-watch:v1",MAX_WATCH=80;
const DAY=86400000,TTL=10*60*1000;
const SERVICE_LABELS={bluesky:"Bluesky",x:"X",threads:"Threads",instagram:"Instagram",
 mastodon:"Mastodon",misskey:"Misskey",reddit:"Reddit",lemmy:"Lemmy"};
const SERVICE_ICONS={bluesky:"assets/bluesky.svg",x:"assets/x.svg",threads:"assets/threads.svg",
 instagram:"assets/instagram.svg",mastodon:"assets/mastodon.svg",
 misskey:"assets/misskey.svg",reddit:"assets/reddit.svg",lemmy:"assets/lemmy.svg"};
const PRODUCT_PATTERN=/(?:구매|구입|샀다|샀어|주문|배송|제품|상품|가격|결제|할인|후기|리뷰|품질|반품|환불|사이즈|재구매|구독|추천)/i;
let storageWorks=true, watches=[],remote=new Map(),busyKeys=new Set();
let currentView="posts",selectedAccount="",rafPending=false;
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
function node(tag,cls,text){
 const el=document.createElement(tag);if(cls)el.className=cls;
 if(text!==undefined)el.textContent=String(text);return el;
}
function link(label,href,cls){
 const a=node("a",cls,label);a.href=href;a.target="_blank";
 a.rel="noopener noreferrer";a.referrerPolicy="no-referrer";return a;
}
function profile(raw){
 let u;try{u=new URL(String(raw||""))}catch{return null}
 if(u.protocol!=="https:"||u.username||u.password||u.port)return null;
 const host=u.hostname.toLowerCase().replace(/^www\./,"");
 let p;try{p=decodeURIComponent(u.pathname).replace(/\/+$/,"")}catch{return null}
 const parts=p.split("/").filter(Boolean);
 let platform="",username="",url="";
 if(host==="bsky.app"&&parts.length===2&&parts[0]==="profile"&&
    (/^(?:did:(?:plc|web):[A-Za-z0-9._:-]{6,140}|[A-Za-z0-9][A-Za-z0-9.-]{2,199})$/).test(parts[1])){
   platform="bluesky";username=parts[1].toLowerCase();
   url="https://bsky.app/profile/"+encodeURIComponent(username).replace(/%3A/gi,":");
 }else if(["x.com","twitter.com"].includes(host)&&parts.length===1&&
    /^[A-Za-z0-9_]{1,15}$/.test(parts[0])&&
    !["home","search","explore","i","settings","login"].includes(parts[0].toLowerCase())){
   platform="x";username=parts[0].toLowerCase();url="https://x.com/"+username;
 }else if(["threads.com","threads.net"].includes(host)&&parts.length===1&&
     /^@[a-zA-Z0-9._]{1,40}$/.test(parts[0])){
   platform="threads";username=parts[0].slice(1).toLowerCase();
   url="https://www.threads.com/@"+username;
 }else if(host==="instagram.com"&&parts.length===1&&
     /^[A-Za-z0-9._]{1,30}$/.test(parts[0])&&
     !["p","reel","explore","accounts","direct"].includes(parts[0].toLowerCase())){
   platform="instagram";username=parts[0].toLowerCase();
   url="https://www.instagram.com/"+username+"/";
 }else if(["mastodon.social","planet.moe","twingyeo.kr"].includes(host)&&
     parts.length===1&&/^@[A-Za-z0-9_.-]{1,60}$/.test(parts[0])){
   platform="mastodon";username=parts[0].slice(1).toLowerCase();
   url="https://"+host+"/@"+username;
 }else if(["misskey.io","hoto.moe"].includes(host)&&parts.length===1&&
     /^@[A-Za-z0-9_.-]{1,60}$/.test(parts[0])){
   platform="misskey";username=parts[0].slice(1).toLowerCase();
   url="https://"+host+"/@"+username;
 }else if(host==="reddit.com"&&parts.length===2&&parts[0].toLowerCase()==="user"&&
     /^[A-Za-z0-9_-]{3,20}$/.test(parts[1])){
   platform="reddit";username=parts[1].toLowerCase();url="https://www.reddit.com/user/"+username+"/";
 }else if(host==="lemmy.world"&&parts.length===2&&parts[0]==="u"&&
     /^[A-Za-z0-9_-]{3,50}$/.test(parts[1])){
   platform="lemmy";username=parts[1].toLowerCase();url="https://lemmy.world/u/"+username;
 }
 if(!url)return null;
 const identity=platform+":"+new URL(url).hostname+":"+username;
 return {key:identity,platform,username,url};
}
function read(){
 try{
   const rows=JSON.parse(localStorage.getItem(STORE)||"[]");
   if(!Array.isArray(rows))return[];
   let seen=new Set(),out=[];
   for(const row of rows.slice(0,MAX_WATCH)){
     const p=profile(typeof row==="string"?row:row?.url);
     if(p&&!seen.has(p.key)){seen.add(p.key);out.push(p)}
   }
   return out;
 }catch{storageWorks=false;return[]}
}
function write(){
 if(!storageWorks)return;
 try{localStorage.setItem(STORE,JSON.stringify(watches.map(w=>w.url)))}
 catch{storageWorks=false;$("accountWatchStatus").textContent="이 환경에서는 브라우저 저장소를 사용할 수 없습니다. 추적 목록은 현재 화면에서만 유지됩니다."}
}
watches=read();
function setView(view){
 currentView=view==="accounts"?"accounts":"posts";
 const acc=currentView==="accounts";
 $("postsView").classList.toggle("hidden",acc);
 $("accountsView").classList.toggle("hidden",!acc);
 $("viewPosts").classList.toggle("active",!acc);
 $("viewAccounts").classList.toggle("active",acc);
 $("viewPosts").setAttribute("aria-selected",String(!acc));
 $("viewAccounts").setAttribute("aria-selected",String(acc));
 if(acc)render();
}
function scheduleRender(){
 if(rafPending)return;rafPending=true;
 requestAnimationFrame(()=>{rafPending=false;render()});
}
function chooseWatch(raw,fromPost=false){
 const p=profile(raw);
 if(!p){$("accountWatchStatus").textContent="지원되는 SNS의 공개 프로필 주소를 확인해주세요. 게시글 주소는 추가할 수 없습니다.";return false}
 if(watches.some(w=>w.key===p.key)){
   $("accountWatchStatus").textContent="이미 추적 중인 공개 계정입니다.";
 }else{
   if(watches.length>=MAX_WATCH){$("accountWatchStatus").textContent="추적 목록 상한(80개)입니다. 일부 항목을 해제해주세요.";return false}
   watches.push(p);write();
   $("accountWatchStatus").textContent=SERVICE_LABELS[p.platform]+" 계정을 추적 목록에 추가했습니다.";
 }
 if(fromPost&&$("detail")?.open)$("detail").close();
 setView("accounts");refreshWatch(p,false);return true;
}
window.INTERSECTION_watchPublicAccount=function(p){
 if(!p||!p.profileUrl)return false;
 return chooseWatch(p.profileUrl,true);
};
function sameAccount(p,watch){
 if(!p?.profileUrl)return false;
 const normalized=profile(p.profileUrl);
 return normalized?.key===watch.key;
}
function snapshot(){
 try{return window.INTERSECTION_publicAccountSnapshot()}catch{return {verified:[],candidates:[],fromMs:0,toMs:0}}
}
function storedActivity(w,snap){
 const items=new Map();
 for(const post of snap.verified||[]){
   if(!sameAccount(post,w)||!post.id||!post.text||!Number.isFinite(Date.parse(post.posted)))continue;
   items.set(String(post.id),{id:String(post.id),text:String(post.text).slice(0,2000),
      posted:post.posted,url:post.url,platform:w.platform});
 }
 const remoteData=remote.get(w.key);
 if(remoteData){
   for(const post of remoteData.items||[])if(post.id&&!items.has(post.id))items.set(post.id,post);
 }
 const lo=Number(snap.fromMs)||0,hi=Number(snap.toMs)||Date.now()+DAY;
 const confirmed=[...items.values()].filter(item=>{
   const ms=Date.parse(item.posted);
   return Number.isFinite(ms)&&ms>=lo&&ms<hi;
 }).sort((a,b)=>Date.parse(b.posted)-Date.parse(a.posted));
 const candidates=(snap.candidates||[]).filter(p=>sameAccount(p,w)).length;
 return {posts:confirmed,candidates,checked:!!remoteData,lastFetch:remoteData?.checkedAt||0,
   error:remoteData?.error||"",provider:remoteData?.provider||""};
}
function contentFingerprint(text){
 const body=String(text||"").toLowerCase().replace(/https?:\/\/\S+/g,"")
  .replace(/[^\p{L}\p{N}]+/gu," ").trim().replace(/\s+/g," ");
 return body.length>=24?body:"";
}
function dedupedContent(posts){
 const unique=new Set();let matched=0,duplicates=0;
 for(const post of posts){
   if(!PRODUCT_PATTERN.test(post.text||""))continue;
   const key=contentFingerprint(post.text)||"post:"+post.id;
   if(unique.has(key)){duplicates++;continue}
   unique.add(key);matched++;
 }
 return {matched,duplicates};
}
function metricText(value){return Number(value||0).toLocaleString("ko-KR")}
function makeSource(p){
 const wrap=node("span","source-badge");wrap.setAttribute("aria-label","출처: "+SERVICE_LABELS[p.platform]);
 const icon=SERVICE_ICONS[p.platform];if(icon){
   const img=node("img");img.src=icon;img.alt="";img.loading="lazy";img.addEventListener("error",()=>img.remove());wrap.append(img);
 }
 wrap.append(node("span","",SERVICE_LABELS[p.platform]||p.platform));return wrap;
}
function card(w,data){
 const root=node("article","account-watch-card");
 const head=node("div","account-watch-head");head.append(makeSource(w),
   node("strong","account-watch-title","@"+w.username));root.append(head);
 const stats=node("div","account-stats");
 const commerce=dedupedContent(data.posts);
 for(const [label,value] of [["확인 글",data.posts.length],["상품 언급",commerce.matched],["미확인 링크",data.candidates]]){
    const box=node("div");box.append(node("strong","",metricText(value)),node("span","",label));stats.append(box);
 }
 root.append(stats);
 const last=data.posts[0]?.posted;
 root.append(node("div","account-watch-meta",last?
    "최근 확인 활동: "+new Date(last).toLocaleDateString("ko-KR"):
    "기간 내 확인된 글 없음"));
 const actions=node("div","account-watch-actions");
 const inspect=node("button","primary","활동 상세");inspect.type="button";inspect.addEventListener("click",()=>openDetail(w));actions.append(inspect);
 const refresh=node("button","","새 글 확인");refresh.type="button";
 const canRefresh=w.platform==="bluesky"||w.platform==="mastodon";
 refresh.disabled=!canRefresh||busyKeys.has(w.key);
 refresh.title=canRefresh?"공개 계정 원문에서 최신 글을 확인":"현재 검색 피드에서 확인된 공개 게시글만 집계";
 refresh.addEventListener("click",()=>refreshWatch(w,true));actions.append(refresh);
 actions.append(link("SNS 프로필",w.url));
 const remove=node("button","danger","추적 해제");remove.type="button";
 remove.addEventListener("click",()=>{
   watches=watches.filter(x=>x.key!==w.key);remote.delete(w.key);write();render();
   $("accountWatchStatus").textContent="추적 목록에서 해제했습니다. 저장된 공개 프로필 주소도 삭제했습니다.";
   if($("accountDialog").open&&selectedAccount===w.key)$("accountDialog").close();
 });
 actions.append(remove);root.append(actions);
 if(data.error)root.append(node("div","account-hint","공개 피드 조회 실패 · "+data.error));
 return root;
}
function render(){
 $("watchCount").textContent=String(watches.length);
 $("accountMetricTracked").textContent=metricText(watches.length);
 const snap=snapshot(),record=watches.map(w=>({w,...storedActivity(w,snap)}));
 const seenPosts=new Set();
 for(const account of record){
   for(const item of account.posts)seenPosts.add(item.id);
 }
 $("accountMetricVerified").textContent=metricText(seenPosts.size);
 $("accountMetricCandidates").textContent=metricText(record.reduce((n,a)=>n+a.candidates,0));
 if(currentView!=="accounts")return;
 const needle=$("accountWatchSearch").value.trim().toLowerCase();
 const visible=record.filter(a=>!needle||(a.w.username+" "+a.w.platform).toLowerCase().includes(needle))
    .sort((a,b)=>b.posts.length-a.posts.length||a.w.platform.localeCompare(b.w.platform));
 const list=$("accountWatchList"),frag=document.createDocumentFragment();
 if(!visible.length){
   frag.append(node("div","account-empty",watches.length?
       "조건과 일치하는 추적 계정이 없습니다.":"추적 계정이 없습니다. 게시글 상세에서 공개 계정을 선택해 추가할 수 있습니다."));
 }else for(const x of visible)frag.append(card(x.w,x));
 list.replaceChildren(frag);
}
function openDetail(w){
 selectedAccount=w.key;
 const content=$("accountDialogContent"),snap=snapshot(),data=storedActivity(w,snap);
 content.replaceChildren();
 const header=node("div","account-watch-head");header.append(makeSource(w),node("h3","", "@"+w.username));
 content.append(header,link("공개 프로필 열기",w.url));
 const commerce=dedupedContent(data.posts);
 content.append(node("p","detail-summary",
  "선택 기간에 실제 확인된 공개 글 "+data.posts.length+"건 · 상품 관련 단어가 있는 고유 글 "+
  commerce.matched+"건 · 중복 문구 제거 "+commerce.duplicates+"건 · 출처 미확인 링크 "+data.candidates+"건"));
 content.append(node("p","detail-summary",
  "이 값은 해당 사용자의 전체 활동량이 아니라, 교집합의 현재 검색 결과 및 공개 계정 피드 표본입니다. 상품 구매·선호·성적 활동·동일인 여부를 추정하지 않습니다."));
 const hist=new Array(7).fill(0),now=Date.now();
 for(const post of data.posts){
   const d=Math.floor((now-Date.parse(post.posted))/DAY);
   if(d>=0&&d<7)hist[6-d]++;
 }
 const bar=node("div","account-activity-bars");
 const max=Math.max(1,...hist);
 hist.forEach((n,i)=>{
    const b=node("div");
    b.style.height=Math.max(2,Math.round(65*n/max))+"px";
    b.title=(6-i)+"일 전: 확인 글 "+n+"건";
    b.setAttribute("aria-label",b.title);bar.append(b);
 });
 content.append(node("strong","", "최근 7일 확인 글 분포"),bar);
 const rows=node("div","account-detail-posts");
 for(const post of data.posts.slice(0,35)){
   const entry=node("div");
   entry.append(node("small","",new Date(post.posted).toLocaleString("ko-KR")+" · "+(PRODUCT_PATTERN.test(post.text)?"상품 관련 표현 포함":"공개 글")));
   entry.append(node("p","",post.text.length>350?post.text.slice(0,350)+"…":post.text));
   if(post.url&&/^https:\/\//i.test(post.url))entry.append(link("원문 보기",post.url));
   rows.append(entry);
 }
 if(!data.posts.length)rows.append(node("p","account-empty","선택 기간에 원문과 날짜가 확인된 게시글이 없습니다."));
 content.append(rows);
 $("accountDialog").showModal();
}
function cleanDate(value){
 const n=Date.parse(String(value||""));
 return Number.isFinite(n)&&n<=Date.now()+DAY?new Date(n).toISOString():"";
}
async function getJSON(url){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),13000);
 try{
  const r=await fetch(url,{mode:"cors",credentials:"omit",cache:"no-store",
    headers:{"Accept":"application/json"},signal:controller.signal});
  if(!r.ok)throw Error("HTTP "+r.status);
  return await r.json();
 }finally{clearTimeout(timer)}
}
async function fetchBluesky(w){
 const args=new URLSearchParams({actor:w.username,limit:"50",filter:"posts_no_replies",includePins:"false"});
 const data=await getJSON("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?"+args);
 if(!Array.isArray(data.feed))throw Error("공개 게시글 목록을 확인할 수 없습니다.");
 const posts=[];
 for(const entry of data.feed){
    if(entry?.reason||!entry?.post?.uri||!entry.post.record||!entry.post.author)continue;
    const p=entry.post;
    const actor=String(p.author.handle||"").toLowerCase();
    const did=String(p.author.did||"").toLowerCase();
    if(w.username!==actor&&w.username!==did)continue;
    if(p.viewer?.replyDisabled||p.labels?.some(x=>x.val==="!hide"||x.val==="!takedown"))continue;
    const posted=cleanDate(p.record.createdAt||p.indexedAt);
    const text=String(p.record.text||"").slice(0,2000);
    const m=/^at:\/\/did:[^/]+\/app\.bsky\.feed\.post\/([a-z0-9]+)$/i.exec(p.uri);
    if(!posted||!m||!text)continue;
    posts.push({id:p.uri,text,posted,platform:"bluesky",
      url:"https://bsky.app/profile/"+encodeURIComponent(did)+"/post/"+m[1]});
 }
 return posts;
}
async function fetchMastodon(w){
 const origin=new URL(w.url).origin;
 const user=await getJSON(origin+"/api/v1/accounts/lookup?"+new URLSearchParams({acct:w.username}));
 if(!user||!String(user.id||""))throw Error("공개 계정을 확인할 수 없습니다.");
 if(user.locked||user.suspended)return[];
 const data=await getJSON(origin+"/api/v1/accounts/"+encodeURIComponent(String(user.id))+"/statuses?"+
  new URLSearchParams({limit:"40",exclude_reblogs:"true"}));
 if(!Array.isArray(data))throw Error("공개 상태 목록을 확인할 수 없습니다.");
 const posts=[];
 for(const item of data){
   if(!item||item.visibility!=="public"||item.reblog||String(item.account?.id||"")!==String(user.id))continue;
   const posted=cleanDate(item.created_at);
   const html=new DOMParser().parseFromString(String(item.content||""),"text/html");
   html.querySelectorAll("script,style,noscript").forEach(x=>x.remove());
   const text=String(html.body.textContent||"").trim().slice(0,2000);
   let canonical;try{
     canonical=new URL(String(item.url||""));
     if(canonical.protocol!=="https:"||canonical.hostname!==new URL(origin).hostname)continue;
   }catch{continue}
   if(posted&&text)posts.push({id:"mastodon:"+origin+":"+item.id,posted,text,url:canonical.href,platform:"mastodon"});
 }
 return posts;
}
async function refreshWatch(w,manual){
 if(!w||!watches.some(x=>x.key===w.key)||busyKeys.has(w.key))return;
 if(!["bluesky","mastodon"].includes(w.platform)){
   if(manual)$("accountWatchStatus").textContent="이 플랫폼은 현재 수집된 공개 게시글만 집계합니다. 인증이 없는 공개 계정 피드 API는 아직 검증되지 않았습니다.";
   return;
 }
 const previous=remote.get(w.key);
 if(!manual&&previous&&Date.now()-previous.checkedAt<TTL)return;
 busyKeys.add(w.key);render();
 if(manual)$("accountWatchStatus").textContent=SERVICE_LABELS[w.platform]+" 공개 글 확인 중…";
 try{
    const posts=w.platform==="bluesky"?await fetchBluesky(w):await fetchMastodon(w);
    if(watches.some(x=>x.key===w.key)){
      remote.set(w.key,{items:posts,provider:"public-api",checkedAt:Date.now(),error:""});
      if(manual)$("accountWatchStatus").textContent="공개 계정 피드 "+posts.length+"건 확인 · 글 내용은 브라우저 저장소에 보관하지 않습니다.";
    }
 }catch(e){
    remote.set(w.key,{items:previous?.items||[],provider:"public-api",
      checkedAt:Date.now(),error:String(e.message||e).slice(0,75)});
    if(manual)$("accountWatchStatus").textContent="조회 실패: "+String(e.message||e).slice(0,90);
 }finally{busyKeys.delete(w.key);render()}
}
$("viewPosts").addEventListener("click",()=>setView("posts"));
$("viewAccounts").addEventListener("click",()=>setView("accounts"));
$("viewAccounts").parentElement.addEventListener("keydown",e=>{
 if(e.key!=="ArrowLeft"&&e.key!=="ArrowRight")return;
 e.preventDefault();
 const tab=e.key==="ArrowRight"?"accounts":"posts";
 setView(tab);$(tab==="accounts"?"viewAccounts":"viewPosts").focus();
});
$("accountWatchForm").addEventListener("submit",e=>{
 e.preventDefault();
 if(chooseWatch($("accountProfileInput").value))$("accountProfileInput").value="";
});
$("accountWatchSearch").addEventListener("input",scheduleRender);
$("closeAccountDialog").addEventListener("click",()=>$("accountDialog").close());
$("accountDialog").addEventListener("click",e=>{if(e.target===$("accountDialog"))$("accountDialog").close()});
window.addEventListener("intersection:feed-updated",scheduleRender);
window.addEventListener("intersection:date-range-change",scheduleRender);
window.addEventListener("storage",e=>{if(e.key===STORE){watches=read();render()}});
render();
// On page load, bounded refresh: no background monitoring or polling.
Promise.resolve().then(async()=>{
  const initial=watches.filter(w=>w.platform==="bluesky"||w.platform==="mastodon").slice(0,4);
  for(const w of initial)await refreshWatch(w,false);
});
})();
