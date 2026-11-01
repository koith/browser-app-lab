/* INTERSECTION zero-key public discovery — indexed links, not collected posts.
 * Explicit user intent only, two provider calls per click, small in-memory list,
 * no tokens/cookies or raw result persistence, conservative per-session guard.
 */
(() => {
  "use strict";
  if (location.hostname !== "koith.github.io") return;
  const el = id => document.getElementById(id);
  const root = el("freeDiscovery");
  if (!root) return;
  root.classList.remove("hidden");
  const TERMS = ["뒷계","섹트","일탈계"];
  const PROVIDERS = [
    {id:"keenable",url:"https://api.keenable.ai/v1/search/public"},
    {id:"firecrawl",url:"https://api.firecrawl.dev/v2/search"}
  ];
  const NETWORKS = {
    x:{name:"X",host:["x.com","twitter.com"],path:/^\/([A-Za-z0-9_]{1,15})\/status\/(\d+)(?:\/|$)/i,logo:"assets/x.svg"},
    threads:{name:"Threads",host:["threads.com","threads.net"],path:/^\/@([A-Za-z0-9._]+)\/post\/([A-Za-z0-9_-]+)(?:\/|$)/i,logo:"assets/threads.svg"},
    instagram:{name:"Instagram",host:["instagram.com"],path:/^\/(p|reel)\/([A-Za-z0-9_-]+)(?:\/|$)/i,logo:"assets/instagram.svg"}
  };
  let pending=false,clicks=0,visible=12,current=[],nextAllowed=0;
  const status=message=>{el("indexStatus").textContent=message};
  const make=(tag,cls,value)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(value!==undefined)n.textContent=String(value);
    return n;
  };
  function checkedUrl(platform,url) {
    try {
      const p=new URL(String(url||""));
      const cfg=NETWORKS[platform];
      const h=p.hostname.toLowerCase().replace(/^www\./,"");
      if(p.protocol!=="https:"||!cfg.host.includes(h)||p.username||p.password)return null;
      const m=cfg.path.exec(p.pathname);
      if(!m)return null;
      // Canonical identity strips tracking and query arguments.
      const canonical="https://"+h+p.pathname.replace(/\/+$/,"");
      let profile=null,handle=null;
      if(platform==="x"){
        handle=m[1];profile="https://x.com/"+handle;
      }else if(platform==="threads"){
        handle=m[1];profile="https://www.threads.com/@"+handle;
      }
      return {canonical,identity:platform+":"+m[2],profile,handle};
    }catch{return null}
  }
  function normalize(row,platform,term,provider) {
    if(!row||typeof row!=="object")return null;
    const found=checkedUrl(platform,row.url);
    if(!found)return null;
    const title=String(row.title||"").replace(/\s+/g," ").slice(0,240);
    const description=String(row.description||row.snippet||"").replace(/\s+/g," ").slice(0,450);
    const exact=title.includes(term)||description.includes(term);
    return {...found,platform,title,description,exact,provider};
  }
  async function searchOne(engine,platform,term){
    const domain=NETWORKS[platform].host[0];
    const query='site:'+domain+' "'+term+'"';
    const body=engine.id==="keenable"?
      {query,max_results:10}:{query,limit:10,sources:["web"]};
    const headers={"Content-Type":"application/json","Accept":"application/json"};
    if(engine.id==="keenable")headers["X-Keenable-Title"]="intersection-research";
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),18000);
    try{
      const response=await fetch(engine.url,{method:"POST",mode:"cors",cache:"no-store",
        credentials:"omit",headers,body:JSON.stringify(body),signal:controller.signal});
      if(!response.ok)throw Error("HTTP "+response.status);
      const data=await response.json();
      if(engine.id==="keenable")return Array.isArray(data.results)?data.results:[];
      if(data.success===false)throw Error("Provider rejected query");
      return Array.isArray(data.data?.web)?data.data.web:[];
    }finally{clearTimeout(timer)}
  }
  function link(text,url){
    const a=make("a","",text);a.href=url;a.target="_blank";a.rel="noopener noreferrer";a.referrerPolicy="no-referrer";return a;
  }
  function card(item){
    const node=make("article","index-result");
    const head=make("div","index-result-head");
    const origin=make("span","index-origin");
    const logo=make("img");logo.src=NETWORKS[item.platform].logo;logo.alt="";
    origin.append(logo,make("span","",NETWORKS[item.platform].name));
    head.append(origin,make("span","index-indexed",item.exact?"검색어 확인":"검색엔진 추천 · 미확인"));
    node.append(head);
    node.append(make("p","index-title",item.title||"SNS 게시글 주소 후보"));
    if(item.description)node.append(make("p","index-description",item.description));
    const actions=make("div","index-links");
    actions.append(link("원문 링크 열기",item.canonical));
    if(item.profile)actions.append(link("작성자 프로필",item.profile));
    node.append(actions);
    node.append(make("p","index-info","검색 결과: "+Array.from(item.providers).join(" · ")+" · 게시 날짜 미확인"));
    return node;
  }
  function render(){
    const target=el("indexResults");target.replaceChildren();
    current.slice(0,visible).forEach(post=>target.append(card(post)));
    el("indexMore").classList.toggle("hidden",current.length<=visible);
  }
  async function start(){
    if(pending)return;
    if(clicks>=12){status("이 화면에서 무료 검색은 최대 12회까지만 가능합니다. 새로고침하면 재검색할 수 있습니다.");return}
    if(Date.now()<nextAllowed){status("중복 요청 방지를 위해 잠시 후 다시 검색할 수 있습니다.");return}
    const platform=el("indexPlatform").value,term=el("indexTerm").value;
    if(!NETWORKS[platform]||!TERMS.includes(term))return;
    clicks++;nextAllowed=Date.now()+10000;pending=true;
    const button=el("indexFind");button.disabled=true;
    status(NETWORKS[platform].name+" 공개 인덱스 검색 중…");
    el("indexResults").replaceChildren();el("indexMore").classList.add("hidden");
    current=[];visible=12;
    const settled=await Promise.allSettled(PROVIDERS.map(engine=>searchOne(engine,platform,term)));
    const unique=new Map(),failed=[];
    settled.forEach((part,i)=>{
      const engine=PROVIDERS[i];
      if(part.status!=="fulfilled"){failed.push(engine.id);return}
      part.value.forEach(row=>{
        const candidate=normalize(row,platform,term,engine.id);
        if(!candidate)return;
        const old=unique.get(candidate.identity);
        if(old){
          old.providers.add(engine.id);
          if(!old.exact&&candidate.exact){
            old.title=candidate.title;old.description=candidate.description;old.exact=true;
          }
        }else{
          candidate.providers=new Set([engine.id]);unique.set(candidate.identity,candidate);
        }
      });
    });
    current=Array.from(unique.values()).sort((a,b)=>Number(b.exact)-Number(a.exact));
    render();
    const names=failed.length?" · 응답 실패: "+failed.join(", "):"";
    status("공개 게시글 링크 후보 "+current.length+"건 · 검색어가 결과에 있는 후보 "+
      current.filter(x=>x.exact).length+"건"+names+
      " · 게시 날짜와 원문 내용은 미확인 · 실제 수집 건수에는 포함하지 않음");
    if(!current.length)el("indexResults").append(make("p","index-info","이 검색어로 확인 가능한 공개 SNS 게시글 주소가 없습니다."));
    pending=false;button.disabled=false;
  }
  el("indexFind").addEventListener("click",()=>start().catch(()=>{
    pending=false;el("indexFind").disabled=false;
    status("무료 검색 도중 오류가 발생했습니다. 실제 게시글이 수집된 것은 아닙니다.");
  }));
  el("indexMore").addEventListener("click",()=>{visible+=12;render()});
})();
