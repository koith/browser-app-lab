/* INTERSECTION: automatic, zero-key multi-SNS discovery in the MAIN feed.
 * No separate search buttons, forms, cards, or local/cloud persistence.
 * Unverified source-index links are clearly labelled and carry no invented date.
 * Sources: keyless KeenAble and Firecrawl public indexes, no cookies or API keys.
 * Public X originals may enter the dated feed only after actual source-ID,
 * timestamp, visibility and keyword validation through an unofficial reader.
 */
(() => {
  "use strict";
  const receive=window.INTERSECTION_receiveCandidates;
  const acceptX=window.INTERSECTION_acceptPublicX;
  // The app runs from both the public Pages mirror and the private Render
  // gateway. Previously Render was excluded, silently disabling the only
  // working X/Threads/Instagram discovery route during Bluesky outages.
  const allowedHost=location.hostname==="koith.github.io"||
    location.hostname==="intersection-originals-free.onrender.com";
  if(!allowedHost||typeof receive!=="function"||typeof acceptX!=="function")return;

  const TERMS=["뒷계","섹트","일탈계"];
  const NETWORKS={
    x:{hosts:["x.com","twitter.com"],
      pattern:/^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]+)\/?$/i},
    threads:{hosts:["threads.com","threads.net"],
      pattern:/^\/@([A-Za-z0-9._]+)\/post\/([A-Za-z0-9_-]+)\/?$/i},
    instagram:{hosts:["instagram.com"],
      pattern:/^\/(p|reel)\/([A-Za-z0-9_-]+)\/?$/i}
  };
  const PROVIDERS=[
    {id:"keenable",url:"https://api.keenable.ai/v1/search/public",limit:35},
    {id:"firecrawl",url:"https://api.firecrawl.dev/v2/search",limit:20}
  ];
  const records=new Map(),originals=new Map();
  let started=false,completed=false;

  function canonical(network,raw){
    const config=NETWORKS[network];
    try{
      const u=new URL(String(raw||""));
      const host=u.hostname.toLowerCase().replace(/^www\./,"");
      if(u.protocol!=="https:"||u.username||u.password||!config.hosts.includes(host))
        return null;
      const match=config.pattern.exec(u.pathname);
      if(!match)return null;
      return {url:"https://"+host+u.pathname.replace(/\/+$/,""),
        id:network+":"+match[2],postId:match[2],handle:match[1]};
    }catch{return null}
  }
  function termsIn(s){return TERMS.filter(term=>String(s||"").includes(term))}
  function candidate(network,row,provider){
    if(!row||typeof row!=="object")return null;
    const found=canonical(network,row.url);
    if(!found)return null;
    const title=String(row.title||"").replace(/\s+/g," ").slice(0,210);
    const description=String(row.description||row.snippet||"").replace(/\s+/g," ").slice(0,430);
    if(!title&&!description)return null;
    return {...found,platform:network,title,description,provider,
      matched:termsIn(title+" "+description)};
  }
  async function request(provider,network){
    const phrase="("+TERMS.map(term=>'"'+term+'"').join(" OR ")+")";
    const query="site:"+NETWORKS[network].hosts[0]+" "+phrase;
    const body=provider.id==="keenable"?
      {query,max_results:provider.limit}:
      {query,limit:provider.limit,sources:["web"]};
    const headers={"Accept":"application/json","Content-Type":"application/json"};
    if(provider.id==="keenable")headers["X-Keenable-Title"]="intersection-research";
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),17000);
    try{
      const res=await fetch(provider.url,{method:"POST",body:JSON.stringify(body),
        credentials:"omit",cache:"no-store",mode:"cors",headers,signal:ctrl.signal});
      if(!res.ok)throw Error("HTTP "+res.status);
      const payload=await res.json();
      if(provider.id==="keenable")return Array.isArray(payload.results)?payload.results:[];
      if(payload.success===false)throw Error("Source search rejected");
      return Array.isArray(payload.data?.web)?payload.data.web:[];
    }finally{clearTimeout(timer)}
  }
  function publish(){
    // Main viewer keeps dated original posts separate from unverifiable search leads.
    // Non-matching snippets are not treated as posts until original text
    // independently establishes that they match one of the topic terms.
    const rows=Array.from(records.values())
      .sort((a,b)=>b.matched.length-a.matched.length)
      .map(x=>({platform:x.platform,url:x.url,title:x.title,
        description:x.description,provider:Array.from(x.providers).join(",")}));
    receive(rows);
  }
  async function readX(item){
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),12000);
    try{
      // The public legacy FxEmbed API documents /:handle/status/:id.
      // /status/:id alone can return a 404 on some gateway versions.
      const url="https://api.fxtwitter.com/"+
        encodeURIComponent(item.handle||"i")+"/status/"+
        encodeURIComponent(item.postId);
      const res=await fetch(url,{mode:"cors",credentials:"omit",
        cache:"no-store",signal:ctrl.signal});
      if(!res.ok)return false;
      const payload=await res.json(),tweet=payload?.tweet;
      if(!tweet||String(tweet.id||"")!==item.postId||tweet.author?.protected===true)
        return false;
      const text=String(tweet.text||"");
      // Prefer provider's UTC epoch: iOS Safari does not consistently parse
      // legacy X date strings such as "Sun Jul 17 09:35:58 +0000 2022".
      const epoch=Number(tweet.created_timestamp);
      const dateMs=Number.isFinite(epoch)&&epoch>0?epoch*1000:
        Date.parse(String(tweet.created_at||""));
      if(!text||text.length>5000||!Number.isFinite(dateMs)||
        dateMs>Date.now()+86400000||!termsIn(text).length)return false;
      const media=[];
      const m=tweet.media||{};
      for(const photo of (Array.isArray(m.photos)?m.photos:[]).slice(0,12)){
        if(photo&&typeof photo.url==="string")
          media.push({type:"image",url:photo.url,thumb:photo.url});
      }
      for(const video of (Array.isArray(m.videos)?m.videos:[]).slice(0,12)){
        if(video&&typeof video.url==="string")
          media.push({type:"video",url:video.url,thumb:video.thumbnail_url||""});
      }
      const verified={
        id:item.postId,text,created_at:new Date(dateMs).toISOString(),
        author:String(tweet.author?.name||tweet.author?.screen_name||item.handle||""),
        avatarUrl:String(tweet.author?.avatar_url||""),
        possibly_sensitive:!!tweet.possibly_sensitive,
        engagement:{likes:tweet.likes,reposts:tweet.retweets,replies:tweet.replies},
        media:media.slice(0,12),
        protected:false,url:item.url
      };
      originals.set(item.id,verified);
      const result=acceptX(verified);
      if(result?.accepted)records.delete(item.id);
      return !!result?.accepted;
    }catch{return false}
    finally{clearTimeout(timer)}
  }
  async function readPublicPage(item){
    if(item.matched.length) return false;
    const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),13000);
    try{
      const endpoint="https://api.keenable.ai/v1/fetch/public?"+
        new URLSearchParams({url:item.url});
      const res=await fetch(endpoint,{mode:"cors",credentials:"omit",
        cache:"no-store",headers:{"Accept":"application/json",
          "X-Keenable-Title":"intersection-research"},signal:ctrl.signal});
      if(!res.ok)return false;
      const page=await res.json();
      const actual=canonical(item.platform,page.url);
      if(!actual||actual.id!==item.id)return false;
      const raw=String(page.content||"").slice(0,3000);
      const matched=termsIn(raw);
      if(!matched.length)return false;
      // Third-party extraction may be cached or include surrounding markup:
      // metadata is NEVER promoted into a dated real post without source proof.
      item.matched=matched;
      item.description=raw.replace(/\s+/g," ").slice(0,420);
      return true;
    }catch{return false}
    finally{clearTimeout(timer)}
  }
  async function limited(items,limit,worker){
    // Bound automatic validation to protect shared free public endpoints.
    const targets=items.slice(0,limit);
    for(let i=0;i<targets.length;i+=3){
      await Promise.allSettled(targets.slice(i,i+3).map(worker));
    }
  }
  async function start(){
    if(started)return;
    started=true;
    const tasks=Object.keys(NETWORKS).flatMap(network=>
      PROVIDERS.map(provider=>({network,provider})));
    const settled=await Promise.allSettled(tasks.map(t=>request(t.provider,t.network)));
    settled.forEach((item,i)=>{
      if(item.status!=="fulfilled")return;
      const {network,provider}=tasks[i];
      for(const row of item.value){
        const next=candidate(network,row,provider.id);
        if(!next)continue;
        const old=records.get(next.id);
        if(old){
          old.providers.add(provider.id);
          if(next.matched.length>old.matched.length){
            old.title=next.title;old.description=next.description;old.matched=next.matched;
          }
        }else records.set(next.id,{...next,providers:new Set([provider.id])});
      }
    });
    publish();
    // Check up to 24 likely matches on X (index-only results can be
    // false positives), and up to 4 links on each Meta network where
    // snippet was incomplete. Never bypass provider denials.
    const x=Array.from(records.values()).filter(x=>x.platform==="x")
      .sort((a,b)=>b.matched.length-a.matched.length);
    await limited(x,24,readX);
    publish();
    for(const network of ["threads","instagram"]){
      const missing=Array.from(records.values()).filter(
        item=>item.platform===network&&!item.matched.length);
      await limited(missing,4,readPublicPage);
      publish();
    }
    completed=true;
    window.INTERSECTION_autoCoverageStatus={
      completed,candidates:records.size,
      datedOriginals:originals.size,
      sources:[...new Set(Array.from(records.values(),x=>x.platform))]
    };
  }
  window.addEventListener("intersection:date-range-change",()=>{
    // A period change wipes dated feed cards; replay previously verified
    // ORIGINAL source records into the new range without paid network calls.
    for(const record of originals.values())acceptX(record);
    publish();
  });
  // Main feed initializes its date state in an earlier inline script.
  // Start immediately without asking the visitor to click a second control.
  setTimeout(()=>start().catch(()=>{completed=true}),180);
})();
