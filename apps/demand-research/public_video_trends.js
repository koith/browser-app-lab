/* INTERSECTION public-video interest: current verified feed only.
 * This is NOT a downloader, third-party saving-count feed, view count, or a
 * complete historical archive. No extra requests, private data or persistence.
 */
(function(root,factory){
 "use strict";
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 if(root&&root.document)api.mount(root);
})(typeof window!=="undefined"?window:null,function(){
 "use strict";
 const LABELS={bluesky:"Bluesky",mastodon:"Mastodon",misskey:"Misskey",
   lemmy:"Lemmy",reddit:"Reddit",x:"X",threads:"Threads",instagram:"Instagram"};
 const HOUR=3600000,DAY=24*HOUR;
 // The app is Korean-localized. Calendar months must use Asia/Seoul rather
 // than UTC so midnight posts are not assigned to the previous month.
 const KST_OFFSET=9*HOUR;
 const koreanMonth=ms=>new Date(ms+KST_OFFSET).toISOString().slice(0,7);
 const koreanTimestamp=ms=>new Intl.DateTimeFormat("ko-KR",{
   timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit",
   hour:"2-digit",minute:"2-digit",hourCycle:"h23"
 }).format(ms);
 const PERIODS={hot:3*HOUR,day:DAY,week:7*DAY,month:30*DAY};
 function safeLink(value){
   if(typeof value!=="string"||value.length>2048)return "";
   let url;try{url=new URL(value);}catch{return "";}
   if(url.protocol!=="https:"||url.username||url.password||url.port)return "";
   const host=url.hostname.toLowerCase();
   if(!host||host==="localhost"||host.endsWith(".local")||host.endsWith(".internal")||
     /^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host))return "";
   return url.href;
 }
 function count(v){
   return typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=100000000?Math.floor(v):null;
 }
 function allVideos(snapshot){
   if(!snapshot||!Array.isArray(snapshot.verified))return [];
   const seen=new Set(),out=[];
   for(const p of snapshot.verified.slice(0,20000)){
     if(!p||!LABELS[p.platform]||p.restricted||p.adultLabeled||
       p.discoveryCandidate||p.adSuspected||typeof p.id!=="string")continue;
     const url=safeLink(p.url),profile=safeLink(p.profileUrl);
     if(!url||!profile)continue;
     const time=Date.parse(p.posted||"");
     if(!Number.isFinite(time)||time<=0)continue;
     const media=(Array.isArray(p.media)?p.media:[]).filter(m=>m?.type==="video");
     if(!media.length)continue;
     const key=p.platform+"|"+profile+"|"+p.id;
     if(seen.has(key))continue;
     seen.add(key);
     const stats=["likes","reposts","replies","quotes"].map(k=>count(p.engagement?.[k]));
     const measured=stats.some(v=>v!==null);
     // Labels are a score of available PUBLIC reactions, not saved/downloads.
     const score=stats.reduce((n,v)=>n+(v??0),0);
     const first=media[0];
     out.push({id:p.id,platform:p.platform,profileUrl:profile,
       url,author:String(p.author||"공개 작성자").slice(0,100),
       time,posted:new Date(time).toISOString(),month:koreanMonth(time),
       videoCount:media.length,thumb:safeLink(first.thumb||""),
       measured,score});
   }
   return out;
 }
 function summarizeSources(rows){
   const counts=new Map();
   for(const row of rows){
     if(!row||!LABELS[row.platform])continue;
     let item=counts.get(row.platform);
     if(!item){item={platform:row.platform,count:0,measured:0};counts.set(row.platform,item);}
     item.count+=1;
     if(row.measured)item.measured+=1;
   }
   return [...counts.values()].sort((a,b)=>b.count-a.count||a.platform.localeCompare(b.platform));
 }
 function derive(snapshot,opts={}){
   const mode=Object.prototype.hasOwnProperty.call(PERIODS,opts.mode)?opts.mode:
     ["latest","archive"].includes(opts.mode)?opts.mode:"day";
   const now=Number.isFinite(opts.nowMs)?opts.nowMs:Date.now();
   const month=typeof opts.month==="string"&&/^\d{4}-\d{2}$/.test(opts.month)?opts.month:"";
   let rows=allVideos(snapshot).filter(r=>r.time<=now);
   if(PERIODS[mode])rows=rows.filter(r=>r.time>=now-PERIODS[mode]);
   if(mode==="archive")rows=rows.filter(r=>month&&r.month===month);
   if(opts.platform&&opts.platform!=="all")rows=rows.filter(r=>r.platform===opts.platform);
   if(mode==="latest"||mode==="archive")rows.sort((a,b)=>b.time-a.time||a.url.localeCompare(b.url));
   else rows.sort((a,b)=>Number(b.measured)-Number(a.measured)||b.score-a.score||
      b.time-a.time||a.url.localeCompare(b.url));
   return rows;
 }
 function months(snapshot,nowMs=Date.now()){
   return [...new Set(allVideos(snapshot).filter(p=>p.time<=nowMs).map(p=>p.month))].sort().reverse();
 }
 function mount(win){
   const doc=win.document,panel=doc.getElementById("videoTrends");
   if(!panel)return;
   const $=id=>doc.getElementById(id);
   const make=(tag,cls,text)=>{
     const el=doc.createElement(tag);
     if(cls)el.className=cls;
     if(text!==undefined)el.textContent=String(text);
     return el;
   };
   let mode="day",month="",platform="all",visible=12,snapshot=null;
   let reviewed=[],reviewIndex=0;
   const reviewDialog=$("videoTrendReviewDialog");
   function showReview(){
     const item=reviewed[reviewIndex];
     if(!item)return;
     $("videoTrendReviewStatus").textContent=(reviewIndex+1)+" / "+reviewed.length+
       " · "+LABELS[item.platform]+" · "+koreanTimestamp(item.time)+" KST";
     const content=$("videoTrendReviewContent");
     content.replaceChildren();
     content.append(make("strong","",item.author));
     if(item.thumb){
       const picture=make("img","video-trend-review-img");
       picture.src=item.thumb;picture.alt="원본 영상 미리보기";picture.referrerPolicy="no-referrer";
       picture.addEventListener("error",()=>picture.remove(),{once:true});
       content.append(picture);
     }
     content.append(make("p","",item.measured?
       "관측된 공개 반응 합계 "+item.score.toLocaleString("ko-KR")+
       " · 영상 "+item.videoCount+"개":
       "공개 반응 수치 미제공 · 영상 "+item.videoCount+"개"));
     const link=make("a","video-trend-review-link","SNS 원문에서 영상 확인");
     link.href=item.url;link.target="_blank";link.rel="noopener noreferrer";
     content.append(link);
     $("videoTrendReviewPrev").disabled=reviewIndex===0;
     $("videoTrendReviewNext").disabled=reviewIndex===reviewed.length-1;
   }
   function moveReview(delta){
     reviewIndex=Math.min(reviewed.length-1,Math.max(0,reviewIndex+delta));
     showReview();
   }

   function read(){
     try{snapshot=win.INTERSECTION_publicVideoSnapshot?.()||null;}catch{snapshot=null;}
   }
   function draw(){
     const avail=months(snapshot);
     const sel=$("videoTrendMonth");
     if(!avail.includes(month))month=avail[0]||"";
     sel.replaceChildren();
     if(!avail.length){const opt=make("option","","월별 자료 없음");opt.value="";sel.append(opt);}
     for(const m of avail){const opt=make("option","",m);opt.value=m;sel.append(opt);}
     sel.value=month;
     sel.hidden=mode!=="archive";
     // Source options come from the current verified snapshot, never guesses
     // or third-party search lead counts.
     const sourceSelect=$("videoTrendSource");
     const available=summarizeSources(allVideos(snapshot));
     sourceSelect.replaceChildren();
     const all=make("option","","전체 SNS");all.value="all";sourceSelect.append(all);
     for(const item of available){
       const option=make("option","",LABELS[item.platform]);
       option.value=item.platform;sourceSelect.append(option);
     }
     if(platform!=="all"&&!available.some(item=>item.platform===platform))platform="all";
     sourceSelect.value=platform;
     doc.querySelectorAll("[data-video-mode]").forEach(btn=>{
       const active=btn.dataset.videoMode===mode;
       btn.classList.toggle("active",active);
       btn.setAttribute("aria-pressed",String(active));
     });
     const scoped=derive(snapshot,{mode,month});
     const coverage=summarizeSources(scoped);
     $("videoTrendCoverage").textContent=coverage.length?
       "SNS별 영상 · "+coverage.map(x=>LABELS[x.platform]+" "+x.count+"건 (반응 제공 "+x.measured+"/"+x.count+")").join(" · "):
       "선택한 기간에 확인된 SNS별 영상이 없습니다.";
     const rows=platform==="all"?scoped:scoped.filter(x=>x.platform===platform);
     const prior=reviewed[reviewIndex]?.url;
     reviewed=rows;
     const matching=reviewed.findIndex(item=>item.url===prior);
     reviewIndex=matching>=0?matching:0;
     $("videoTrendReviewStart").disabled=reviewed.length===0;
     if(reviewDialog.open){
       if(reviewed.length)showReview();
       else reviewDialog.close();
     }
     const shown=rows.slice(0,visible),list=$("videoTrendRows");
     list.replaceChildren();
     for(const [i,r] of shown.entries()){
       const card=make("a","video-trend-card");
       card.href=r.url;card.target="_blank";card.rel="noopener noreferrer";
       card.setAttribute("aria-label",r.author+" · "+LABELS[r.platform]+" 원문 열기");
       const picture=make("span","video-trend-thumb");
       if(r.thumb){
         const img=make("img");img.src=r.thumb;img.alt="원본 게시글 영상 미리보기";
         img.loading="lazy";img.decoding="async";img.referrerPolicy="no-referrer";
         img.addEventListener("error",()=>{img.remove();picture.classList.add("video-trend-no-thumb");});
         picture.append(img);
       }else picture.classList.add("video-trend-no-thumb");
       picture.append(make("span","video-trend-play","▶"));
       if(r.videoCount>1)picture.append(make("span","video-trend-multiple","영상 "+r.videoCount+"개"));
       const meta=make("span","video-trend-meta");
       meta.append(make("b","",String(i+1).padStart(2,"0")+" · "+r.author));
       meta.append(make("small","",LABELS[r.platform]+" · "+koreanTimestamp(r.time)+" KST"));
       meta.append(make("small","",r.measured?
         "확인된 공개 반응 합계 "+r.score.toLocaleString("ko-KR"):"공개 반응 수치 미제공"));
       card.append(picture,meta);list.append(card);
     }
     if(!rows.length)list.append(make("p","video-trend-empty",
       "현재 불러온 공개 게시글에서 해당 기간의 검증된 영상을 찾지 못했습니다."));
     $("videoTrendCount").textContent="확인된 영상 게시글 "+rows.length.toLocaleString("ko-KR")+"건"+
       (snapshot?.partial?" · 수집 일부 미완료":"");
     $("videoTrendMore").hidden=rows.length<=visible;
     $("videoTrendMore").textContent="영상 "+Math.min(12,rows.length-visible)+"건 더 보기";
   }
   function update(){read();draw();}
   doc.querySelectorAll("[data-video-mode]").forEach(btn=>btn.addEventListener("click",()=>{
     mode=btn.dataset.videoMode;visible=12;draw();
   }));
   $("videoTrendMonth").addEventListener("change",()=>{month=$("videoTrendMonth").value;visible=12;draw();});
   $("videoTrendSource").addEventListener("change",()=>{
     platform=$("videoTrendSource").value;visible=12;draw();
   });
   $("videoTrendMore").addEventListener("click",()=>{visible+=12;draw();});
   $("videoTrendReviewStart").addEventListener("click",()=>{
     if(!reviewed.length)return;
     reviewIndex=0;showReview();
     if(!reviewDialog.open)reviewDialog.showModal();
   });
   $("videoTrendReviewPrev").addEventListener("click",()=>moveReview(-1));
   $("videoTrendReviewNext").addEventListener("click",()=>moveReview(1));
   $("videoTrendReviewClose").addEventListener("click",()=>reviewDialog.close());
   reviewDialog.addEventListener("keydown",event=>{
     if(event.key==="ArrowLeft"||event.key==="ArrowRight"){
       event.preventDefault();moveReview(event.key==="ArrowLeft"?-1:1);
     }
   });
   let scheduled=false;
   function schedule(){
     if(scheduled)return;scheduled=true;
     win.queueMicrotask(()=>{scheduled=false;update();});
   }
   win.addEventListener("intersection:feed-updated",schedule);
   win.addEventListener("intersection:date-range-change",schedule);
   update();
 }
 return {allVideos,derive,months,summarizeSources,mount};
});
