/* Wikimedia Analytics article pageviews (CC0, recent, aggregate-only).
 * Views express Wikipedia article attention, not buyers or demand.
 */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
const add=(p,tag,cls,t)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(t!==undefined)e.textContent=String(t);p.append(e);return e;};
const num=n=>Number(n||0).toLocaleString("ko-KR");
const change=n=>typeof n==="number"?(n>0?"+":"")+n.toFixed(2)+"%":"비교 불가";
const label={device:"제품",device_family:"제품군",category:"상품 범주"};
let report=null;
function wikiLink(raw){
 try{const x=new URL(raw);return x.protocol==="https:"&&x.hostname==="en.wikipedia.org"&&
 !x.username&&!x.password?x.href:null}catch{return null}
}
function validate(d){
 if(!d||d.schema_version!==1||d.dataset?.kind!=="current_article_attention_not_demand"||
 d.dataset?.license!=="CC0 1.0"||d.dataset?.is_purchases!==false||
 d.dataset?.is_demand!==false||d.dataset?.contains_individuals!==false||
 !Array.isArray(d.topics)||d.topics.length!==6)throw Error("Wikimedia 집계 출처 및 스키마 오류");
 for(const p of d.topics){
   if(typeof p.title!=="string"||p.title.length>100||
      !Number.isSafeInteger(p.latest_7d_views)||p.latest_7d_views<0||
      !Number.isSafeInteger(p.previous_7d_views)||p.previous_7d_views<0||
      !Array.isArray(p.daily)||p.daily.length!==14||!wikiLink(p.wiki_url))
     throw Error("Wikimedia 항목 검증 실패");
   const seven=p.daily.slice(7).reduce((s,d)=>s+d.views,0);
   const prev=p.daily.slice(0,7).reduce((s,d)=>s+d.views,0);
   if(seven!==p.latest_7d_views||prev!==p.previous_7d_views)
     throw Error("일별 합계와 주간 집계가 다릅니다.");
 }
 return d;
}
function render(){
 if(!report)return;
 const source=report.dataset;
 $("attentionWindow").textContent=source.window_start+" ~ "+source.window_end+
  " (일별, 영어 위키백과)";
 const filter=$("attentionType").value;
 const list=report.topics.filter(p=>!filter||
   (filter==="goods"?p.article_type==="device"||p.article_type==="device_family":
    p.article_type==="category"));
 const panel=$("attentionCards");panel.replaceChildren();
 for(const topic of list){
   const card=add(panel,"article","attention-card");
   const head=add(card,"div","attention-card-head");
   const names=add(head,"div","");
   add(names,"small","",(label[topic.article_type]||"범주")+" · 영문 위키피디아");
   add(names,"h3","",topic.title);
   const diff=add(head,"strong","attention-change",change(topic.week_on_week_change_pct));
   diff.classList.add(topic.difference_views>=0?"up":"down");
   add(diff,"small","","이전 7일 대비");
   const numbers=add(card,"div","attention-count","");
   add(numbers,"b","",num(topic.latest_7d_views));
   add(numbers,"small","","최근 7일 조회 · 직전 7일 "+num(topic.previous_7d_views));
   const history=add(card,"div","attention-spark");
   const peak=Math.max(1,...topic.daily.map(x=>x.views));
   for(const point of topic.daily){
     const bar=add(history,"span","attention-day");
     bar.style.height=Math.max(2,100*point.views/peak)+"%";
     bar.title=point.day+": "+num(point.views)+"회";
     bar.setAttribute("aria-label",bar.title);
   }
   const url=wikiLink(topic.wiki_url);
   if(url){
     const link=add(card,"a","attention-source","문서 조회");
     link.href=url;link.target="_blank";link.rel="noopener noreferrer";
   }
 }
 $("attentionStatus").textContent="Wikimedia Analytics · "+source.window_end+
  "까지의 실제 기사 조회 집계 · "+list.length+"개 항목 · 실제 구매량 아님";
}
async function start(){
 try{
   const r=await fetch("./attention-report.json",{cache:"no-store"});
   if(!r.ok)throw Error("Wikimedia 실측 데이터 배포가 아직 완료되지 않았습니다.");
   report=validate(await r.json());
   $("attentionType").addEventListener("change",render);
   render();
 }catch(error){$("attentionStatus").textContent="관심도 집계 로드 실패: "+String(error.message||error);}
}
if($("attentionLab"))start();
})();
