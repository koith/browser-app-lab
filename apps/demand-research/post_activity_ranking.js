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
          posts:0,days:new Set(),reactions:0,measuredPosts:0};
       groups.set(key,g);
     }
     g.posts+=1;
     g.days.add(new Date(ms).toISOString().slice(0,10));
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
       score:signal,engagementAvailable:g.measuredPosts>0
     });
   }
   return output.sort((a,b)=>b.score-a.score||b.posts-a.posts||a.profileUrl.localeCompare(b.profileUrl));
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
   let expanded=false,ranking=[],partial=true;
   function draw(){
     const platform=$("activityRankingPlatform").value,order=$("activityRankingSort").value;
     const filtered=ranking.filter(x=>platform==="all"||x.platform===platform);
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
     const show=expanded?20:5;
     if(!sorted.length)list.append(node("div","activity-ranking-empty",
       "현재 검색 조건에 랭킹으로 집계할 공개 게시글이 없습니다."));
     sorted.slice(0,show).forEach((g,index)=>{
       const card=node("article","activity-rank-card");
       const top=node("div","activity-rank-head");
       top.append(node("span","activity-rank-num",String(index+1).padStart(2,"0")),
         node("span","activity-rank-source",LABELS[g.platform]));
       card.append(top);
       const link=node("a","activity-rank-user",g.author);
       link.href=g.profileUrl;link.target="_blank";link.rel="noopener noreferrer";
       link.title="공개 SNS 프로필 열기";
       card.append(link);
       const score=node("div","activity-rank-score",fmt(g.score));
       score.append(node("small","","관측 지수"));
       card.append(score);
       card.append(node("div","activity-rank-stats",
         "게시 "+fmt(g.posts)+" · 활동 "+fmt(g.activeDays)+"일"));
       card.append(node("div","activity-rank-stats",
         g.engagementAvailable?"공개 반응 "+fmt(g.reactions)+" · 제공 "+g.measuredPosts+"/"+g.posts+"건":
         "공개 반응 자료 미제공"));
       list.append(card);
     });
     const more=$("activityRankingMore");more.classList.toggle("hidden",sorted.length<=5);
     more.setAttribute("aria-expanded",String(expanded));more.textContent=expanded?"접기":"더 보기 ("+fmt(Math.min(20,sorted.length))+"위까지)";
     $("activityRankingStatus").textContent="확인된 공개 계정 "+fmt(sorted.length)+"개 · "+
        "관측 게시글 "+fmt(sorted.reduce((n,g)=>n+g.posts,0))+"건"+
        (partial?" · 일부 기간/플랫폼 미확인":" · 현재 조회 범위")+
        " · 지수 = 게시글×2 + 활동일×3 + 공개 반응 보정(자료 제공 시)";
   }
   function update(){
     let snap;try{snap=win.INTERSECTION_publicRankingSnapshot?.();}catch{}
     ranking=compute(snap);partial=snap?.partial!==false;
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
   $("activityRankingPlatform").addEventListener("change",()=>{expanded=false;draw();});
   $("activityRankingSort").addEventListener("change",draw);
   $("activityRankingMore").addEventListener("click",()=>{expanded=!expanded;draw();});
   win.addEventListener("intersection:feed-updated",schedule);
   win.addEventListener("intersection:date-range-change",()=>{expanded=false;schedule();});
   update();
 }
 return {compute,mount};
});
