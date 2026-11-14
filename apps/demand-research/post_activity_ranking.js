/* INTERSECTION: observed activity ranking of public platform accounts.
 * Counts only validated, currently observed public posts (not people).
 * No text analysis, identity linkage, history storage, background tracking,
 * demographic assumptions, or independent network requests.
 */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 if(root&&root.document)api.mount(root);
})(typeof window!=="undefined"?window:null,function(){
 "use strict";
 const LABELS={bluesky:"Bluesky",x:"X",threads:"Threads",instagram:"Instagram",
   mastodon:"Mastodon",misskey:"Misskey",reddit:"Reddit",lemmy:"Lemmy"};
 const STATS=["likes","reposts","replies","quotes"];
 // Reuse only HTTPS media URLs already provided by the visible public feed.
 function safeThumbnail(raw){
   if(typeof raw!=="string"||raw.length>2048)return "";
   let u;try{u=new URL(raw);}catch{return "";}
   if(u.protocol!=="https:"||u.username||u.password||u.port)return "";
   if(/^(localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(u.hostname.toLowerCase()))return "";
   return u.href;
 }
 const fmt=n=>Number(n||0).toLocaleString("ko-KR");
 function canonical(raw,platform){
   if(!LABELS[platform])return "";
   let u;try{u=new URL(String(raw||""));}catch{return "";}
   if(u.protocol!=="https:"||u.username||u.password||u.port||u.search||u.hash)return "";
   const host=u.hostname.toLowerCase();
   if(/^(localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host))return "";
   if(platform==="bluesky"&&host!=="bsky.app")return "";
   if(platform==="x"&&host!=="x.com")return "";
   if(platform==="reddit"&&host!=="www.reddit.com"&&host!=="reddit.com")return "";
   if(platform==="threads"&&host!=="www.threads.net"&&host!=="threads.net")return "";
   if(platform==="instagram"&&host!=="www.instagram.com"&&host!=="instagram.com")return "";
   if(platform==="lemmy"&&!/^\/(u|c)\//.test(u.pathname))return "";
   if(platform==="mastodon"&&!/^\/(@|users\/)/.test(u.pathname))return "";
   if(platform==="misskey"&&!/^\/@/.test(u.pathname))return "";
   if(!/^\/\S{2,}/.test(u.pathname))return "";
   return "https://"+host+u.pathname.replace(/\/+$/,"");
 }
 function count(value){
   return typeof value==="number"&&Number.isFinite(value)&&value>=0&&value<=100000000?Math.floor(value):null;
 }
 function compute(snapshot){
   if(!snapshot||!Array.isArray(snapshot.verified))return [];
   const seen=new Set(),groups=new Map(),from=Number(snapshot.fromMs),to=Number(snapshot.toMs);
   if(!Number.isFinite(from)||!Number.isFinite(to)||from>=to)return [];
   for(const p of snapshot.verified.slice(0,20000)){
     if(!p||typeof p.id!=="string"||p.id.length>500||
       typeof p.platform!=="string"||!LABELS[p.platform])continue;
     const profile=canonical(p.profileUrl,p.platform);
     if(!profile)continue;
     const ms=Date.parse(p.posted);
     if(!Number.isFinite(ms)||ms<from||ms>=to)continue;
     // Some federated providers issue post IDs within each server or actor.
     // Deduplicate repeats within the same public account, not across actors.
     const key=p.platform+"|"+profile;
     const postKey=key+"|"+p.id;
     if(seen.has(postKey))continue;
     seen.add(postKey);
     let g=groups.get(key);
     if(!g){
       g={platform:p.platform,profileUrl:profile,
          author:String(p.author||profile.split("/").pop()).slice(0,90),
          posts:0,days:new Set(),reactions:0,measuredPosts:0,
          latestMs:-Infinity,earliestMs:Infinity,latestId:"",latestThumbnail:"",latestAvatar:"",profileCreatedAt:"",profilePostCount:null};
       groups.set(key,g);
     }
     g.posts+=1;
     const publicAvatar=safeThumbnail(p.avatarUrl);
     if(publicAvatar)g.latestAvatar=publicAvatar;
     g.days.add(new Date(ms).toISOString().slice(0,10));
     g.earliestMs=Math.min(g.earliestMs,ms);
     const created=Date.parse(p.profileCreatedAt||"");
     if(Number.isFinite(created)&&created>0&&created<=ms&&
        (!g.profileCreatedAt||created<Date.parse(g.profileCreatedAt)))
       g.profileCreatedAt=new Date(created).toISOString();
     const lifetime=count(p.profilePostCount);
     if(lifetime!==null)g.profilePostCount=Math.max(g.profilePostCount??0,lifetime);
     if(ms>g.latestMs||(ms===g.latestMs&&p.id>g.latestId)){
       g.latestMs=ms;g.latestId=p.id;
       g.latestThumbnail=safeThumbnail(p.thumbnailUrl);
     }
     const values=STATS.map(k=>count(p.engagement?.[k]));
     if(values.some(v=>v!==null)){
       g.measuredPosts+=1;
       // Multiple networks report reactions differently; never make absent data 0.
       g.reactions+=values.reduce((acc,v)=>acc+(v??0),0);
     }
   }
   const output=[];
   for(const g of groups.values()){
     const activeDays=g.days.size;
     // A transparent bounded signal, not follower reach or human influence.
     const signal=2*g.posts+3*activeDays+
       (g.measuredPosts?Math.round(6*Math.log2(1+g.reactions)):0);
     output.push({
       platform:g.platform,profileUrl:g.profileUrl,author:g.author,
       posts:g.posts,activeDays,reactions:g.reactions,
       measuredPosts:g.measuredPosts,
       score:signal,engagementAvailable:g.measuredPosts>0,
       latestThumbnail:g.latestThumbnail,latestAvatar:g.latestAvatar,latestPosted:new Date(g.latestMs).toISOString(),
       firstObservedPosted:new Date(g.earliestMs).toISOString(),
       profileCreatedAt:g.profileCreatedAt,profilePostCount:g.profilePostCount
     });
   }
   return output.sort((a,b)=>b.score-a.score||b.posts-a.posts||a.profileUrl.localeCompare(b.profileUrl));
 }
 function cohortOf(g,nowMs=Date.now()){
   const date=Date.parse(g.profileCreatedAt||"");
   if(Number.isFinite(date)&&date>0&&date<=nowMs)
     return nowMs-date>=30*86400000?"established":"new";
   // A verifiably old public post proves the account existed before the
   // current month even when a provider omits account-creation metadata.
   const observed=Date.parse(g.firstObservedPosted||"");
   if(Number.isFinite(observed)&&observed>0&&observed<=nowMs&&
      nowMs-observed>=30*86400000)return "established";
   if(Number.isInteger(g.profilePostCount)&&g.profilePostCount>=20)return "established";
   if(g.posts>=2&&g.activeDays>=2)return "established";
   return "new";
 }
 function mount(win){
   const doc=win.document;
   const panel=doc.getElementById("activityRanking");
   if(!panel)return;
   const $=id=>doc.getElementById(id);
   const node=(tag,cls,text)=>{
     const e=doc.createElement(tag);if(cls)e.className=cls;
     if(text!==undefined)e.textContent=String(text);
     return e;
   };
   let visibleCount=20,ranking=[],cohort="established",cohortTouched=false;
   let providerOutage=false;
   const profileCache=new Map(),pendingProfiles=new Set(),profileRetryAfter=new Map();
   let profileFetchActive=false;
   function mergeProfileEvidence(){
     for(const g of ranking){
       const evidence=profileCache.get(g.profileUrl);
       if(!evidence)continue;
       if(evidence.createdAt)g.profileCreatedAt=evidence.createdAt;
       if(Number.isInteger(evidence.postsCount))g.profilePostCount=evidence.postsCount;
     }
   }
   async function hydratePublicProfiles(){
     if(typeof win.fetch!=="function"||profileFetchActive)return;
     const want=ranking.filter(g=>g.platform==="bluesky"&&
        !profileCache.has(g.profileUrl)&&!pendingProfiles.has(g.profileUrl)&&
        (profileRetryAfter.get(g.profileUrl)||0)<=Date.now()).slice(0,120);
     if(!want.length)return;
     profileFetchActive=true;
     try{
       for(let i=0;i<want.length;i+=25){
         const batch=want.slice(i,i+25);
         batch.forEach(g=>pendingProfiles.add(g.profileUrl));
         try{
           const u=new URL("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles");
           for(const g of batch)u.searchParams.append("actors",g.profileUrl.split("/profile/")[1]);
           const init={cache:"no-store",credentials:"omit"};
           if(typeof win.AbortSignal?.timeout==="function")init.signal=win.AbortSignal.timeout(9000);
           const response=await win.fetch(u.href,init);
           if(!response.ok)throw Error("public profile lookup unavailable");
           const payload=await response.json();
           if(!Array.isArray(payload.profiles))throw Error("invalid profile response");
           for(const g of batch){
             const actor=g.profileUrl.split("/profile/")[1].toLowerCase();
             const profile=payload.profiles.find(p=>p&&
               (String(p.did||"").toLowerCase()===actor||
                String(p.handle||"").toLowerCase()===actor));
             const joined=Date.parse(profile?.createdAt||"");
             const posts=count(profile?.postsCount);
             // Missing profile records and transient provider failures are
             // not proof of a new account. Retry on a later feed update.
             if(!profile){profileRetryAfter.set(g.profileUrl,Date.now()+60000);continue;}
             profileCache.set(g.profileUrl,{
               createdAt:Number.isFinite(joined)&&joined>0&&joined<=Date.now()?new Date(joined).toISOString():"",
               postsCount:posts
             });
             profileRetryAfter.delete(g.profileUrl);
           }
         }catch{
           batch.forEach(g=>profileRetryAfter.set(g.profileUrl,Date.now()+60000));
         }finally{
           batch.forEach(g=>pendingProfiles.delete(g.profileUrl));
           mergeProfileEvidence();
           draw();
         }
       }
     }finally{profileFetchActive=false;}
   }
   const dialog=$("activityRankingDialog"),detail=$("activityRankingDialogContent");
   function closeDetail(){
     if(!dialog)return;
     if(typeof dialog.close==="function"&&dialog.open)dialog.close();
     else dialog.removeAttribute("open");
     if(detail)detail.replaceChildren();
   }
   function openDetail(g,rank){
     if(!dialog||!detail)return;
     detail.replaceChildren();
     const intro=node("div","activity-rank-detail-intro");
     const title=node("div","");
     title.append(node("div","activity-rank-detail-source",LABELS[g.platform]+" · #"+rank),
       node("div","activity-rank-detail-title",g.author));
     intro.append(title);
     if(g.latestThumbnail||g.latestAvatar){
       const img=node("img","activity-rank-detail-thumb");
       img.src=g.latestThumbnail||g.latestAvatar;
       img.alt=g.latestThumbnail?"최근 게시글 이미지":"공개 프로필 사진";
       img.referrerPolicy="no-referrer";
       // A broken post image must never silently become a different account
       // image. Profile avatars are used only when no post photo was provided.
       img.addEventListener("error",()=>img.remove());
       intro.append(img);
     }
     detail.append(intro);
     const metrics=node("div","activity-rank-detail-metrics");
     for(const [label,value] of [
       ["활동 지수",fmt(g.score)],["게시글",fmt(g.posts)],
       ["활동 일수",fmt(g.activeDays)+"일"],
       ["공개 반응",g.engagementAvailable?fmt(g.reactions):"미제공"],
       ["반응 제공",fmt(g.measuredPosts)+" / "+fmt(g.posts)+"건"],
       ["최근 게시글",new Date(g.latestPosted).toLocaleDateString("ko-KR")],
       ["계정 공개 이력",g.profileCreatedAt?
          new Date(g.profileCreatedAt).toLocaleDateString("ko-KR")+"부터":
          (g.profilePostCount!==null?"누적 "+fmt(g.profilePostCount)+"건":"확인 중/미확인")],
       ["활동 구분",cohortOf(g)==="established"?"기존 활동":"신규/이력 미확인"]
     ]){
       const metric=node("div","activity-rank-detail-metric");
       metric.append(node("small","",label),node("strong","",value));
       metrics.append(metric);
     }
     detail.append(metrics,node("div","activity-rank-detail-note",
       "기간 내 활동 지수: 게시글×2 + 활동 일수×3 + 공개 반응 보정 · 기존 활동: 공개 프로필 생성일 30일 이상, 생성일 미제공 시 누적 게시글 20건 이상 또는 조회 기간 중 서로 다른 날 2일 이상 활동 · 신규 활동에는 공개 이력 미확인 계정도 포함 · 다른 SNS 계정을 동일인으로 추정하지 않음"));
     const link=node("a","activity-rank-detail-link","SNS 프로필 열기 ↗");
     link.href=g.profileUrl;link.target="_blank";link.rel="noopener noreferrer";
     detail.append(link);
     if(typeof dialog.showModal==="function")dialog.showModal();
     else dialog.setAttribute("open","");
   }
   function draw(){
     const platform=$("activityRankingPlatform").value,order=$("activityRankingSort").value;
     const visible=ranking.filter(x=>platform==="all"||x.platform===platform);
     const established=visible.filter(x=>cohortOf(x)==="established");
     const newcomer=visible.filter(x=>cohortOf(x)==="new");
     // An unavailable age API should not leave the entire ranking blank on
     // first load. Do not mislabel unverified accounts as established.
     if(!cohortTouched)cohort=established.length?"established":"new";
     const filtered=cohort==="established"?established:newcomer;
     doc.querySelectorAll("[data-rank-cohort]").forEach(btn=>{
       const selected=btn.dataset.rankCohort===cohort;
       btn.classList.toggle("active",selected);
       btn.setAttribute("aria-selected",String(selected));
       const n=btn.dataset.rankCohort==="established"?established.length:newcomer.length;
       btn.textContent=(btn.dataset.rankCohort==="established"?"기존 활동 ":"신규 활동 ")+n;
     });
     const sorter={
       posts:(a,b)=>b.posts-a.posts,
       days:(a,b)=>b.activeDays-a.activeDays,
       reactions:(a,b)=>Number(b.engagementAvailable)-Number(a.engagementAvailable)||b.reactions-a.reactions,
       signal:(a,b)=>b.score-a.score
     }[order]||((a,b)=>b.score-a.score);
     const sorted=filtered.sort((a,b)=>sorter(a,b)||b.score-a.score||
        a.profileUrl.localeCompare(b.profileUrl));
     const list=$("activityRankingRows");
     list.replaceChildren();
     const show=visibleCount;
     if(!sorted.length)list.append(node("div","activity-ranking-empty",
       providerOutage?"Bluesky 공개 검색 장애 · 랭킹 집계가 불완전합니다. 0명은 실제 활동 0명이 아닙니다.":
       ranking.some(g=>g.platform==="bluesky"&&pendingProfiles.has(g.profileUrl))?
         "공개 프로필 이력 확인 중…":"해당 분류의 확인된 계정이 없습니다. 신규 활동에는 공개 이력 미확인 계정도 포함됩니다."));
     sorted.slice(0,show).forEach((g,index)=>{
       const card=node("button","activity-rank-card");
       card.type="button";
       card.setAttribute("aria-label",index+1+"위 "+g.author+" 상세 보기");
       card.append(node("span","activity-rank-num",String(index+1).padStart(2,"0")));
       const thumb=node("span","activity-rank-thumb");
       if(g.latestThumbnail||g.latestAvatar){
         const img=node("img","");
         img.src=g.latestThumbnail||g.latestAvatar;img.alt="";
         img.loading="lazy";img.decoding="async";img.referrerPolicy="no-referrer";
         img.addEventListener("error",()=>{
           img.remove();thumb.classList.add("activity-rank-thumb-empty");
         });
         thumb.append(img);
       }else thumb.classList.add("activity-rank-thumb-empty");
       card.append(thumb);
       card.addEventListener("click",()=>openDetail(g,index+1));
       list.append(card);
     });
     const more=$("activityRankingMore");
     more.classList.toggle("hidden",sorted.length<=show);
     more.setAttribute("aria-expanded",String(show>20));
     more.setAttribute("aria-label",`랭킹 ${Math.min(20,Math.max(0,sorted.length-show))}명 더 보기`);
     more.textContent="더 보기";
   }
   function update(){
     let snap;try{snap=win.INTERSECTION_publicRankingSnapshot?.();}catch{}
     providerOutage=Boolean(snap?.providerOutage);
     ranking=compute(snap);
     mergeProfileEvidence();
     const select=$("activityRankingPlatform"),prev=select.value;
     const available=[...new Set(ranking.map(x=>x.platform))].sort();
     select.replaceChildren();
     const all=node("option","","전체 SNS");all.value="all";select.append(all);
     for(const p of available){const o=node("option","",LABELS[p]);o.value=p;select.append(o);}
     select.value=available.includes(prev)?prev:"all";
     draw();
     void hydratePublicProfiles();
   }
   let scheduled=false;
   function schedule(){
     if(scheduled)return;scheduled=true;
     win.queueMicrotask(()=>{scheduled=false;update();});
   }
   doc.querySelectorAll('[data-rank-cohort]').forEach(btn=>btn.addEventListener('click',()=>{cohort=btn.dataset.rankCohort;cohortTouched=true;visibleCount=20;closeDetail();doc.querySelectorAll('[data-rank-cohort]').forEach(b=>{b.classList.toggle('active',b===btn);b.setAttribute('aria-selected',String(b===btn));});draw();}));
   $("activityRankingPlatform").addEventListener("change",()=>{visibleCount=20;closeDetail();draw();});
   $("activityRankingSort").addEventListener("change",()=>{closeDetail();draw();});
   $("activityRankingMore").addEventListener("click",()=>{visibleCount+=20;draw();});
   $("activityRankingDialogClose")?.addEventListener("click",closeDetail);
   dialog?.addEventListener("click",e=>{if(e.target===dialog)closeDetail();});
   dialog?.addEventListener("close",()=>detail?.replaceChildren());
   win.addEventListener("intersection:feed-updated",schedule);
   win.addEventListener("intersection:date-range-change",()=>{visibleCount=20;closeDetail();schedule();});
   update();
 }
 return {compute,cohortOf,mount};
});
