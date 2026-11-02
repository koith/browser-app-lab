/* INTERSECTION no-fee public cross-SNS discovery.
 * Explicit click; indexed candidates never masquerade as dated source posts.
 * Only a matching, public X original with a source timestamp may enter the feed.
 * No API keys, bulk archives, media downloads, storage, or paid endpoints.
 */
(() => {
  "use strict";
  if (location.hostname !== "koith.github.io") return;
  const el=id=>document.getElementById(id),root=el("freeDiscovery");
  if(!root)return;
  root.classList.remove("hidden");
  const TERMS=["뒷계","섹트","일탈계"];
  const PROVIDERS=[
    {id:"keenable",url:"https://api.keenable.ai/v1/search/public"},
    {id:"firecrawl",url:"https://api.firecrawl.dev/v2/search"}
  ];
  const NETWORKS={
    x:{name:"X",hosts:["x.com","twitter.com"],path:/^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]+)(?:\/|$)/i,logo:"assets/x.svg"},
    threads:{name:"Threads",hosts:["threads.com","threads.net"],path:/^\/@([A-Za-z0-9._]+)\/post\/([A-Za-z0-9_-]+)(?:\/|$)/i,logo:"assets/threads.svg"},
    instagram:{name:"Instagram",hosts:["instagram.com"],path:/^\/(p|reel)\/([A-Za-z0-9_-]+)(?:\/|$)/i,logo:"assets/instagram.svg"}
  };
  let busy=false,clicks=0,visible=12,results=[],nextAllowed=0,version=0;
  const fetchCache=new Map();
  const status=s=>{el("indexStatus").textContent=s};
  const make=(tag,cls,value)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(value!==undefined)n.textContent=String(value);
    return n;
  };
  const termsIn=text=>TERMS.filter(t=>String(text||"").includes(t));
  function canonical(platform,input){
    try{
      const u=new URL(String(input||"")),cfg=NETWORKS[platform];
      const host=u.hostname.toLowerCase().replace(/^www\./,"");
      if(u.protocol!=="https:"||u.username||u.password||!cfg.hosts.includes(host))return null;
      const match=cfg.path.exec(u.pathname);
      if(!match)return null;
      let profile="",handle="";
      if(platform==="x"){handle=match[1];profile="https://x.com/"+handle}
      if(platform==="threads"){handle=match[1];profile="https://www.threads.com/@"+handle}
      return {url:"https://"+host+u.pathname.replace(/\/+$/,""),
        identity:platform+":"+match[2],postId:match[2],handle,profile};
    }catch{return null}
  }
  function normalize(row,platform,term,provider){
    if(!row||typeof row!=="object")return null;
    const link=canonical(platform,row.url);
    if(!link)return null;
    const title=String(row.title||"").replace(/\s+/g," ").slice(0,240);
    const description=String(row.description||row.snippet||"").replace(/\s+/g," ").slice(0,500);
    const matched=termsIn(title+" "+description);
    const exact=term==="all"?matched.length>0:matched.includes(term);
    return {...link,platform,term:term==="all"?(matched[0]||""):term,
      title,description,exact,matched,providers:new Set([provider]),
      indexDate:String(row.published_at||"").slice(0,24),verifiedText:"",verifiedDate:"",
      sourceChecked:false,sourceAvailable:false};
  }
  async function request(engine,platform,term){
    const domain=NETWORKS[platform].hosts[0];
    const phrase=term==="all"?"("+
      TERMS.map(t=>'"'+t+'"').join(" OR ")+")":'"'+term+'"';
    const query="site:"+domain+" "+phrase;
    const body=engine.id==="keenable"?
      {query,max_results:35}:{query,limit:20,sources:["web"]};
    const headers={"Content-Type":"application/json","Accept":"application/json"};
    if(engine.id==="keenable")headers["X-Keenable-Title"]="intersection-research";
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),20000);
    try{
      const res=await fetch(engine.url,{method:"POST",credentials:"omit",mode:"cors",
        cache:"no-store",headers,body:JSON.stringify(body),signal:ctrl.signal});
      if(!res.ok)throw Error("HTTP "+res.status);
      const data=await res.json();
      if(engine.id==="keenable")return Array.isArray(data.results)?data.results:[];
      if(data.success===false)throw Error("검색 제공자가 결과를 거부했습니다");
      return Array.isArray(data.data?.web)?data.data.web:[];
    }finally{clearTimeout(timer)}
  }
  function link(label,url){
    const a=make("a","",label);a.href=url;a.target="_blank";a.rel="noopener noreferrer";
    a.referrerPolicy="no-referrer";return a;
  }
  async function getPublicX(item){
    const key="x:"+item.postId;
    if(fetchCache.has(key))return fetchCache.get(key);
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),14000);
    try{
      const res=await fetch("https://api.fxtwitter.com/status/"+
        encodeURIComponent(item.postId),{mode:"cors",credentials:"omit",
        cache:"no-store",signal:ctrl.signal});
      if(!res.ok)throw Error("HTTP "+res.status);
      const data=await res.json(),t=data?.tweet;
      if(!t||String(t.id||"")!==item.postId||t.author?.protected===true)
        throw Error("공개 원문 ID 확인 실패");
      const body=String(t.text||"").slice(0,5000),dateMs=Date.parse(String(t.created_at||""));
      if(!body||!Number.isFinite(dateMs)||dateMs>Date.now()+86400000)
        throw Error("본문 또는 작성시각 미확인");
      const verified={
        id:item.postId,author:String(t.author?.name||t.author?.screen_name||item.handle||""),
        url:item.url,text:body,created_at:new Date(dateMs).toISOString(),protected:false};
      fetchCache.set(key,verified);
      return verified;
    }finally{clearTimeout(timer)}
  }
  function registerX(item,verified){
    if(!verified||!termsIn(verified.text).length)return {accepted:false,reason:"keyword"};
    if(typeof window.INTERSECTION_acceptPublicX!=="function")return {accepted:false,reason:"unavailable"};
    return window.INTERSECTION_acceptPublicX(verified);
  }
  async function verifyX(item,button,output,quiet=false){
    if(button){button.disabled=true;item.expanded=true}
    if(output)output.textContent="X 공개 원문을 확인하는 중…";
    try{
      const verified=await getPublicX(item);
      item.sourceChecked=true;
      item.sourceAvailable=true;
      item.verifiedDate=verified.created_at;
      const matched=termsIn(verified.text);
      if(!matched.length){
        item.verifyInfo="원문 조회 성공 · 검색어 불일치";
        if(output)output.textContent=item.verifyInfo;
        return {accepted:false,reason:"keyword"};
      }
      item.verifiedText=verified.text.slice(0,1200);
      item.matched=matched;item.exact=true;
      const admitted=registerX(item,verified);
      item.verifyInfo=admitted.accepted?
        "공개 원문 확인 · 기간 내 게시글 피드 반영":
        admitted.reason==="outside-period"?"공개 원문 확인 · 선택한 기간 밖":
        admitted.reason==="duplicate"?"공개 원문 확인 · 이미 표시한 글":
        "공개 원문 확인 · 현재 피드 반영 조건 미충족";
      if(output){
        const date=new Date(item.verifiedDate).toLocaleString("ko-KR");
        output.replaceChildren(make("strong","",item.verifyInfo+" · "+date),
          make("p","index-description",item.verifiedText));
        output.append(make("p","index-info","비공식 FxEmbed 공개 원문 조회 · 저장하지 않음"));
      }
      return admitted;
    }catch(e){
      item.verifyInfo="X 공개 원문 재확인 실패";
      if(output)output.textContent=item.verifyInfo+" · "+String(e.message||e).slice(0,80);
      return {accepted:false,reason:"unavailable"};
    }finally{
      if(button)button.disabled=false;
      if(!quiet)updateStats();
    }
  }
  async function checkPage(item,button,output,quiet=false){
    if(button){button.disabled=true;item.expanded=true}
    if(output)output.textContent="공개 페이지 텍스트 확인 중…";
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),15000);
    try{
      const url="https://api.keenable.ai/v1/fetch/public?"+
        new URLSearchParams({url:item.url});
      const res=await fetch(url,{credentials:"omit",mode:"cors",cache:"no-store",
        headers:{"Accept":"application/json","X-Keenable-Title":"intersection-research"},
        signal:ctrl.signal});
      if(!res.ok)throw Error("HTTP "+res.status);
      const info=await res.json();
      // A cached third-party page extract is NOT proof the post is still live.
      const link=canonical(item.platform,info.url);
      if(!link||link.identity!==item.identity)
        throw Error("다른 페이지로 연결됨");
      const body=String(info.content||"").slice(0,20000);
      const terms=termsIn(body);
      item.sourceChecked=true;
      if(!terms.length||!body.trim())
        throw Error("공개 페이지에서 대상 검색어 확인 실패");
      item.sourceAvailable=true;item.matched=terms;item.exact=true;
      item.verifiedText=body.slice(0,1200);
      item.indexDate=String(info.published_at||item.indexDate||"").slice(0,24);
      item.verifyInfo="공개 웹페이지 텍스트 확인 · 원문 게시일/현재 상태 미확인";
      if(output){
        output.replaceChildren(make("strong","",item.verifyInfo),
          make("p","index-description",item.verifiedText));
        output.append(make("p","index-info","Keenable 공개 페이지 추출 · 저장하지 않음"));
      }
      return true;
    }catch(error){
      item.verifyInfo="원문 페이지 텍스트 확인 실패";
      if(output)output.textContent=item.verifyInfo+" · "+String(error.message||error).slice(0,65);
      return false;
    }finally{clearTimeout(timer);if(button)button.disabled=false;if(!quiet)updateStats()}
  }
  function card(item){
    const node=make("article","index-result");
    const head=make("div","index-result-head"),origin=make("span","index-origin");
    const logo=make("img");logo.src=NETWORKS[item.platform].logo;logo.alt="";
    origin.append(logo,make("span","",NETWORKS[item.platform].name));
    const label=item.sourceAvailable?
      (item.platform==="x"?"X 공개 원문 확인":"공개 페이지 텍스트 확인"):
      item.exact?"검색어 있는 링크 · 미확인":"검색엔진 링크 · 미확인";
    head.append(origin,make("span","index-indexed",label));node.append(head);
    node.append(make("p","index-title",item.title||"SNS 게시글 주소 후보"));
    if(item.verifiedText)
      node.append(make("p","index-description",item.verifiedText.slice(0,400)));
    else if(item.description)
      node.append(make("p","index-description",item.description));
    const actions=make("div","index-links");
    actions.append(link("원문 링크 열기",item.url));
    if(item.profile)actions.append(link("작성자 프로필",item.profile));
    node.append(actions);
    node.append(make("p","index-info","검색 경로: "+Array.from(item.providers).join(", ")+
      " · "+(item.verifiedDate?"원문 게시일 확인":"원문 게시 날짜 미확인")));
    const verify=make("button","index-check",
      item.platform==="x"?"X 공개 원문 확인 (무료)":"무료 공개 페이지 확인");
    const result=make("div","index-verify-result");
    if(item.expanded && item.verifyInfo){
      result.append(make("strong","",item.verifyInfo+
        (item.verifiedDate?" · "+new Date(item.verifiedDate).toLocaleString("ko-KR"):"")));
      if(item.verifiedText)result.append(make("p","index-description",item.verifiedText));
    }
    verify.addEventListener("click",async()=>{
      if(item.platform==="x")await verifyX(item,verify,result);
      else await checkPage(item,verify,result);
      render();
    });
    node.append(verify,result);
    return node;
  }
  function render(){
    const target=el("indexResults");target.replaceChildren();
    results.slice(0,visible).forEach(item=>target.append(card(item)));
    el("indexMore").classList.toggle("hidden",results.length<=visible);
  }
  function updateStats(errors=[]){
    const sourceCounts=Object.keys(NETWORKS).map(k=>NETWORKS[k].name+" "+
      results.filter(x=>x.platform===k).length).join(" · ");
    const checked=results.filter(x=>x.sourceAvailable).length;
    status("무료 검색 후보 "+results.length+"건 ("+sourceCounts+")"+
      " · 공개 원문/페이지 확인 "+checked+"건"+
      (errors.length?" · 제공자 응답 실패 "+errors.join(", "):"")+
      " · 원문/게시 시각 미확인 링크는 실제 수집 건수에서 제외");
  }
  async function enriched(items,limit,fn){
    let accepted=0;
    // Fixed small batch to respect free services and avoid source crawling.
    for(let offset=0;offset<Math.min(items.length,limit);offset+=3){
      const batch=items.slice(offset,Math.min(offset+3,limit));
      const parts=await Promise.allSettled(batch.map(item=>fn(item)));
      accepted+=parts.filter(p=>p.status==="fulfilled"&&p.value===true).length;
    }
    return accepted;
  }
  async function begin(){
    if(busy)return;
    if(clicks>=12){status("현재 브라우저의 무료 조회 횟수 상한에 도달했습니다.");return}
    if(Date.now()<nextAllowed){status("반복 요청을 줄이기 위해 잠시 뒤 다시 조회해주세요.");return}
    const platform=el("indexPlatform").value,term=el("indexTerm").value;
    const platforms=platform==="all"?Object.keys(NETWORKS):[platform];
    if(platforms.some(p=>!NETWORKS[p])||(!TERMS.includes(term)&&term!=="all"))return;
    clicks++;nextAllowed=Date.now()+10000;busy=true;version++;
    const epoch=version,button=el("indexFind");button.disabled=true;
    el("indexResults").replaceChildren();el("indexMore").classList.add("hidden");
    results=[];visible=12;
    status(platform==="all"?"세 SNS 통합 무료 검색 중…":NETWORKS[platform].name+" 무료 검색 중…");
    try{
      const tasks=platforms.flatMap(p=>PROVIDERS.map(provider=>({p,provider})));
      const values=await Promise.allSettled(tasks.map(t=>request(t.provider,t.p,term)));
      if(epoch!==version)return;
      const unique=new Map(),errors=[];
      values.forEach((v,i)=>{
        const t=tasks[i];
        if(v.status!=="fulfilled"){errors.push(t.provider.id+"-"+t.p);return}
        for(const row of v.value){
          const candidate=normalize(row,t.p,term,t.provider.id);
          if(!candidate)continue;
          const old=unique.get(candidate.identity);
          if(old){
            old.providers.add(t.provider.id);
            old.matched=Array.from(new Set([...old.matched,...candidate.matched]));
            if(!old.exact&&candidate.exact){
              old.exact=true;old.term=candidate.term;old.title=candidate.title;
              old.description=candidate.description;
            }
          }else unique.set(candidate.identity,candidate);
        }
      });
      results=Array.from(unique.values()).sort((a,b)=>Number(b.exact)-Number(a.exact));
      render();updateStats(errors);
      if(!results.length){
        el("indexResults").append(make("p","index-info",
          "무료 검색으로 확인된 게시글 주소가 없습니다. 일부 SNS는 공개 검색 인덱스가 제공되지 않습니다."));
        return;
      }
      if(platform==="all"){
        // An explicit all-source search may validate a few public originals.
        // The complete indexed list remains separately labelled even if
        // no dated source could be added to the real post feed.
        const x=results.filter(r=>r.platform==="x");
        await enriched(x,9,async item=>{
          const v=await verifyX(item,null,null,true);return v.accepted===true;
        });
        await enriched(results.filter(r=>r.platform==="threads"&&r.exact),4,
          async item=>checkPage(item,null,null,true));
        await enriched(results.filter(r=>r.platform==="instagram"&&r.exact),3,
          async item=>checkPage(item,null,null,true));
        render();updateStats(errors);
      }
    }catch(error){
      status("무료 검색 실패 · "+String(error.message||error).slice(0,100));
    }finally{busy=false;button.disabled=false}
  }
  el("indexFind").addEventListener("click",()=>begin());
  el("indexMore").addEventListener("click",()=>{visible+=12;render()});
})();
