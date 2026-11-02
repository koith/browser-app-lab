/* Real historical UCI shopping session outcomes (2018, CC BY 4.0).
 * Descriptive aggregates only: no individual visitors, personal traits,
 * SNS account matching, current purchase forecasts or causal assertions.
 */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
const add=(parent,tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=String(txt);parent.append(e);return e};
const nfmt=v=>Number(v||0).toLocaleString("ko-KR");
const pct=v=>typeof v==="number"?v.toFixed(2)+"%":"자료 없음";
const titles={
 month:"월별 비교 (연도 미제공)",
 visitor:"방문 유형별",
 weekend:"주중·주말별",
 product_pages:"상품 페이지 열람 수별"
};
const labels={
 Jan:"1월",Feb:"2월",Mar:"3월",Apr:"4월",May:"5월",June:"6월",
 Jul:"7월",Aug:"8월",Sep:"9월",Oct:"10월",Nov:"11월",Dec:"12월",
 New_Visitor:"신규 방문",Returning_Visitor:"재방문",Other:"기타",
 Weekend:"주말",Weekday:"주중",
 "0":"0회","1–5":"1–5회","6–15":"6–15회",
 "16–40":"16–40회","41+":"41회 이상"
};
let report=null;
function validate(d){
 if(!d||d.schema_version!==1||
 d.dataset?.kind!=="historical_real_ecommerce_sessions"||
 d.dataset?.is_current_data!==false||
 d.dataset?.is_current_market_demand!==false||
 d.dataset?.contains_person_identifiers!==false||
 d.dataset?.license!=="CC BY 4.0"||
 d.dataset?.study_year!==2018||
 !d.summary||!d.segments)throw Error("공식 과거 세션 집계 형식이 아닙니다.");
 for(const k of ["sessions","purchases","conversion_pct"])
  if(typeof d.summary[k]!=="number"||!Number.isFinite(d.summary[k])||d.summary[k]<0)
   throw Error("요약 통계 오류");
 if(d.summary.purchases>d.summary.sessions||d.summary.sessions>20000)
  throw Error("요약 통계 범위 오류");
 for(const key of Object.keys(titles)){
   if(!Array.isArray(d.segments[key])||d.segments[key].length>15)
     throw Error("구간 집계 형식 오류");
   const s=d.segments[key];
   for(const p of s)if(typeof p.sessions!=="number"||p.sessions<0||
    typeof p.purchases!=="number"||p.purchases<0||
    p.purchases>p.sessions)throw Error("구간 통계 범위 오류");
   if(s.reduce((a,b)=>a+b.sessions,0)!==d.summary.sessions||
      s.reduce((a,b)=>a+b.purchases,0)!==d.summary.purchases)
     throw Error("구간 합계가 전체 세션 수와 다릅니다.");
 }
 return d;
}
function render(){
 if(!report)return;
 const stats=$("sessionMetrics");stats.replaceChildren();
 for(const [name,value,note] of [
  ["과거 쇼핑 세션",nfmt(report.summary.sessions),"개인별 방문 수가 아님"],
  ["구매로 끝난 세션",nfmt(report.summary.purchases),"매출액이 아님"],
  ["관측 전환율",pct(report.summary.conversion_pct),"2018년 발표 자료"],
  ["Wilson 95% 구간",
   (report.summary.wilson_95_pct||[]).map(pct).join(" – "),"표본 설계 반영한 모집단 예측 아님"]
 ]){
   const e=add(stats,"div","session-stat");
   add(e,"small","",name);add(e,"strong","",value);add(e,"span","",note);
 }
 const dimension=$("sessionDimension").value;
 const rows=report.segments[dimension]||[];
 const panel=$("sessionRows");panel.replaceChildren();
 add($("sessionDimensionLabel"),"span","","");
 $("sessionDimensionLabel").textContent=titles[dimension];
 const max=Math.max(1,...rows.map(p=>p.conversion_pct||0));
 rows.forEach((r)=>{
   const line=add(panel,"div","session-row");
   const heading=add(line,"div","session-row-head");
   add(heading,"b","",labels[r.id]||r.id);
   const rate=r.minimum_group_size_met?pct(r.conversion_pct):"표본 부족";
   add(heading,"strong","",rate);
   const track=add(line,"div","session-track");
   const fill=add(track,"div","session-fill");
   fill.style.width=(r.minimum_group_size_met?Math.max(.6,100*(r.conversion_pct||0)/max):0)+"%";
   fill.setAttribute("aria-label",rate);
   const note=add(line,"small","","세션 "+nfmt(r.sessions)+
     "건 · 구매 완료 "+nfmt(r.purchases)+"건");
   if(r.minimum_group_size_met&&Array.isArray(r.wilson_95_pct))
     note.textContent+=" · Wilson 95% "+r.wilson_95_pct.map(pct).join("–");
 });
 $("sessionStatus").textContent="UCI 공개 2018년 연구 자료 · 총 "+nfmt(report.summary.sessions)+
   "개 세션 · 현재 구매 전환율이나 매출 전망이 아닙니다.";
}
async function start(){
 try{
  const r=await fetch("./session-report.json",{cache:"no-store"});
  if(!r.ok)throw Error("UCI 세션 집계 파일이 아직 배포되지 않았습니다.");
  report=validate(await r.json());
  $("sessionDimension").addEventListener("change",render);
  render();
 }catch(err){$("sessionStatus").textContent="쇼핑 세션 집계 로드 실패: "+String(err.message||err);}
}
if($("sessionLab"))start();
})();
