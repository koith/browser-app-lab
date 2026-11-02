/* Independent CC BY 4.0 published editorial evidence, not consumer demand. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const mk=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=String(value);return e};
const add=(parent,tag,cls,value)=>{const e=mk(tag,cls,value);parent.append(e);return e};
const fmt=n=>Number(n||0).toLocaleString("ko-KR");
function safeLink(raw){try{const u=new URL(String(raw));return u.protocol==="https:"&&!u.username&&!u.password?u.href:null}catch{return null}}
let report=null;
function valid(d){
 if(!d||d.schema_version!==1||d.dataset?.kind!=="real_editorial_product_ratings"||
 d.dataset?.is_consumer_demand!==false||d.dataset?.license!=="CC BY 4.0"||
 !Array.isArray(d.products)||d.products.length>200||
 !Array.isArray(d.categories)||d.categories.length>12)throw Error("공개 평가 보고서 형식이 아닙니다.");
 for(const p of d.products)if(typeof p.name!=="string"||p.name.length>180||
 typeof p.publisher_stated_scores!=="number"||p.publisher_stated_scores<0||
 typeof p.publication_reviews!=="number"||p.publication_reviews<0)throw Error("평가 통계 오류");
 return d;
}
function render(){
 if(!report)return;
 const s=report.summary;
 const box=$("editorialMetrics");box.replaceChildren();
 for(const [label,value,hint] of [
 ["전문가 평가 원본",fmt(s.source_ratings_rows),"전체 CC BY 4.0 원본"],
 ["선택 상품",fmt(s.selected_products),"일반 소비재만 포함"],
 ["매체 명시 점수",fmt(s.publisher_stated_scores),"평균 산출에 포함"],
 ["추론 점수 제외",fmt(s.inferred_scores_excluded),"자동 추정값 제외"]]){
   const tile=add(box,"div","editorial-stat");
   add(tile,"small","",label);add(tile,"strong","",value);add(tile,"span","",hint);
 }
 const cat=$("editorialCategory").value;
 const q=$("editorialSearch").value.trim().toLowerCase();
 const items=report.products.filter(p=>(!cat||p.category===cat)&&
 (!q||(p.name+" "+p.category_name+" "+p.product_id).toLowerCase().includes(q)));
 items.sort((a,b)=>b.publisher_stated_scores-a.publisher_stated_scores||
  (b.publisher_stated_mean_5pt??-1)-(a.publisher_stated_mean_5pt??-1)||
  a.product_id.localeCompare(b.product_id));
 const root=$("editorialCards");root.replaceChildren();
 if(!items.length){add(root,"p","editorial-none","조건에 맞는 데이터가 없습니다.");return;}
 for(const p of items.slice(0,60)){
   const card=add(root,"article","editorial-card"),head=add(card,"div","editorial-card-head");
   const names=add(head,"div","");
   add(names,"small","",p.category_name);add(names,"h3","",p.name);
   const avg=add(head,"strong","editorial-rating",
    p.publisher_stated_mean_5pt===null?"미확정":p.publisher_stated_mean_5pt.toFixed(2)+"/5");
   add(avg,"small","","매체 명시 점수 평균");
   add(card,"p","", "평가 링크 "+fmt(p.publication_reviews)+"개 · 매체 명시 "+
       fmt(p.publisher_stated_scores)+"개 · 추론 제외 "+fmt(p.inferred_scores_excluded)+
       "개 · 무점수 "+fmt(p.unscored_reviews)+"개");
   const links=add(card,"div","editorial-links");
   const pUrl=safeLink(p.product_url);
   if(pUrl){const a=add(links,"a","","상품 근거");a.href=pUrl;a.target="_blank";a.rel="noopener noreferrer";}
   for(const [i,raw] of (p.sample_review_urls||[]).slice(0,3).entries()){
     const url=safeLink(raw);if(!url)continue;
     const a=add(links,"a","","평가 원문 "+(i+1));a.href=url;a.target="_blank";a.rel="noopener noreferrer";
   }
 }
 $("editorialStatus").textContent="실제 전문가 상품 평가 · "+report.dataset.as_of+
   " 출처 조회 · "+fmt(items.length)+"개 상품 · 구매 수요 지표 아님";
}
async function init(){
 try{
 const resp=await fetch("./editorial-report.json",{cache:"no-store"});
 if(!resp.ok)throw Error("공개 평가 보고서가 배포되지 않았습니다.");
 report=valid(await resp.json());
 const select=$("editorialCategory");select.replaceChildren();
 const all=mk("option","","전체 카테고리");all.value="";select.append(all);
 for(const category of report.categories){
   const opt=mk("option","",category.name+" ("+fmt(category.products)+")");
   opt.value=category.id;select.append(opt);
 }
 select.addEventListener("change",render);$("editorialSearch").addEventListener("input",render);
 render();
 }catch(e){$("editorialStatus").textContent="실제 평가 데이터 로드 실패: "+String(e.message||e);}
}
if($("editorialLab"))init();
})();
