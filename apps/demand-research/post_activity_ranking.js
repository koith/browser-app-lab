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
     const postKey=p.platform+":"+p.id;
     if(seen.has(postKey))continue;
     seen.add(postKey);
     const key=p.platform+"|"+profile;
     let g=groups.get(key);
     if(!g){
       g={platform:p.platform,profileUrl:profile,
          author:String(p.author||profile.split("/").pop()).slice(0,90),
          posts:0,days:new Set(),reactions:0,measuredPosts:0,
          latestMs:-Infinity,latestId:"",latestThumbnail:"",profileCreatedAt:"",profilePostCount:null};
       groups.set(key,g);
     }
     g.posts+=1;
     g.days.add(new Date(ms).toISOString().slice(0,10));
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
       latestThumbnail:g.latestThumbnail,latestPosted:new Date(g.latestMs).toISOString(),
       profileCreatedAt:g.profileCreatedAt,profilePostCount:g.profilePostCount
     });
   }
   return output.sort((a,b)=>b.score-a.score||b.posts-a.posts||a.profileUrl.localeCompare(b.profileUrl));
 }
 function cohortOf(g,nowMs=Date.now()){
   const date=Date.parse(g.profileCreatedAt||"");
   if(Number.isFinite(date)&&date>0&&date<=nowMs)
     return nowMs-date>=30*86400000?"established":"new";
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
   let visibleCount=20,ranking=[],cohort="established";
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
     if(g.latestThumbnail){
       const img=node("img","activity-rank-detail-thumb");
       img.src=g.latestThumbnail;img.alt="최근 게시글 썸네일";img.referrerPolicy="no-referrer";
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
       ["최근 게시글",new Date(g.latestPosted).toLocaleDateString("ko-KR")]
     ]){
       const metric=node("div","activity-rank-detail-metric");
       metric.append(node("small","",label),node("strong","",value));
       metrics.append(metric);
     }
     detail.append(metrics,node("div","activity-rank-detail-note",
       "현재 검색 기간에 관측된 공개 게시글 기준 · 기존 활동군은 관측 게시글 3건 이상 및 활동일 3일 이상, 신규 활동군은 그 외 · 계정 생성일을 뜻하지 않음 · 활동 지수는 게시글×2 + 활동 일수×3 + 공개 반응 보정"));
     const link=node("a","activity-rank-detail-link","SNS 프로필 열기 ↗");
     link.href=g.profileUrl;link.target="_blank";link.rel="noopener noreferrer";
     detail.append(link);
     if(typeof dialog.showModal==="function")dialog.showModal();
     else dialog.setAttribute("open","");
   }
   function draw(){
     const platform=$("activityRankingPlatform").value,order=$("activityRankingSort").value;
     const filtered=ranking.filter(x=>(platform==="all"||x.platform===platform)&& (cohort==="established"?(x.posts>=3&&x.activeDays>=3):(x.posts<3||x.activeDays<3)));
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
     if(!sorted.length)list.append(node("div","activity-ranking-empty","랭킹 없음"));
     sorted.slice(0,show).forEach((g,index)=>{
       const card=node("button","activity-rank-card");
       card.type="button";
       card.setAttribute("aria-label",index+1+"위 "+g.author+" 상세 보기");
       card.append(node("span","activity-rank-num",String(index+1).padStart(2,"0")));
       const thumb=node("span","activity-rank-thumb");
       if(g.latestThumbnail){
         const img=node("img","");
         img.src=g.latestThumbnail;img.alt="";img.loading="lazy";
         img.decoding="async";img.referrerPolicy="no-referrer";
         img.addEventListener("error",()=>{img.remove();thumb.classList.add("activity-rank-thumb-empty");});
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
     ranking=compute(snap);
     const select=$("activityRankingPlatform"),prev=select.value;
     const available=[...new Set(ranking.map(x=>x.platform))].sort();
     select.replaceChildren();
     const all=node("option","","전체 SNS");all.value="all";select.append(all);
     for(const p of available){const o=node("option","",LABELS[p]);o.value=p;select.append(o);}
     select.value=available.includes(prev)?prev:"all";
     draw();
   }
   let scheduled=false;
   function schedule(){
     if(scheduled)return;scheduled=true;
     win.queueMicrotask(()=>{scheduled=false;update();});
   }
   doc.querySelectorAll('[data-rank-cohort]').forEach(btn=>btn.addEventListener('click',()=>{cohort=btn.dataset.rankCohort;visibleCount=20;closeDetail();doc.querySelectorAll('[data-rank-cohort]').forEach(b=>{b.classList.toggle('active',b===btn);b.setAttribute('aria-selected',String(b===btn));});draw();}));
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
