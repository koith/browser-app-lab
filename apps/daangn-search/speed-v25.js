// v2.5 hard-capped speed-first scheduler.
// 15 dongs/API call, 4 API calls in parallel (up to 60 dongs/wave), no sleeps.
// Each browser->API call is hard-capped so one slow Vercel request cannot stall the whole search.
const SPEED_BATCH=15, SPEED_PARALLEL=4, CLIENT_API_TIMEOUT_MS=5500;

requestBatch=async function(q,codes){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),CLIENT_API_TIMEOUT_MS);
  try{
    const r=await fetch(`${API}/${endpoint()}?q=${encodeURIComponent(q)}&regions=${encodeURIComponent(codes.join(','))}`,{signal:controller.signal,cache:'no-store'});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
    return d;
  }catch(e){
    if(e&&e.name==='AbortError')throw new Error(`API timeout ${CLIENT_API_TIMEOUT_MS}ms`);
    throw e;
  }finally{
    clearTimeout(timer);
  }
};

pass=async function(q,codes,label='검색'){
  const seen=new Set(items.map(x=>x.url));
  let ok=0,blocked=0,fail=[],completed=0,apiMaxMs=0;
  const batches=[];
  for(let i=0;i<codes.length;i+=SPEED_BATCH)batches.push(codes.slice(i,i+SPEED_BATCH));
  for(let i=0;i<batches.length;i+=SPEED_PARALLEL){
    const wave=batches.slice(i,i+SPEED_PARALLEL);
    const target=Math.min(completed+wave.reduce((n,b)=>n+b.length,0),codes.length);
    setStatus(`<span class="spin"></span>${label} ${completed}/${codes.length} · 다음 ${target}곳 처리 중 · 현재 <b>${items.length}</b>건`);
    const outs=await Promise.all(wave.map(async b=>{
      const t=Date.now();
      try{return {b,d:await requestBatch(q,b),ms:Date.now()-t}}
      catch{return {b,d:null,ms:Date.now()-t}}
    }));
    for(const {b,d,ms} of outs){
      completed+=b.length;
      apiMaxMs=Math.max(apiMaxMs,ms);
      if(!d){fail.push(...b);continue}
      ok+=d.okRegionCount??Math.max(0,b.length-(d.errors||[]).length);
      blocked+=d.blockedCount||0;
      for(const e of d.errors||[])fail.push(e.region);
      for(const it of d.items||[]){
        if(seen.has(it.url))continue;
        seen.add(it.url);
        const m=codeMeta[it.region]||{};
        items.push({...it,gu:m.gu||it.gu||'',dong:it.dong||m.dong||null});
      }
    }
    render();
    setStatus(`<span class="spin"></span>${label} ${completed}/${codes.length} · 현재 <b>${items.length}</b>건`);
  }
  return {ok,blocked,pauses:0,failed:[...new Set(fail)],apiMaxMs};
};

searchAll=async function(opts={}){
  const q=$('q').value.trim();
  if(!q){setStatus('<span class="err">검색어를 입력하세요.</span>');return}
  if(!selected.size){setStatus('<span class="err">지역을 먼저 선택하세요.</span>');renderRegions();openSheet('regionSheet','regionBack');return}
  if(searching)return;
  searching=true;$('go').disabled=true;
  const t0=Date.now();
  try{
    let codes,dongFails=[],manualRetry=!!opts.retryOnly;
    if(manualRetry){codes=[...failedCodes];failedCodes=[]}
    else{
      items=[];failedCodes=[];
      $('results').innerHTML='<div class="loading"><span class="spin"></span> 동네 목록 확인 중...</div>';
      const out=await selectedCodes();codes=out.codes;dongFails=out.dongFails;
    }
    if(!codes.length)throw new Error('검색할 동네 코드가 없습니다.');
    const first=await pass(q,codes,manualRetry?'재검색':'검색');
    failedCodes=first.failed;
    lastMeta={codes:codes.length,ok:Math.max(0,codes.length-failedCodes.length),failed:failedCodes.length,blocked:first.blocked,dongFails:dongFails.length,recovered:0,pauses:0,sec:((Date.now()-t0)/1000).toFixed(1),batch:SPEED_BATCH,parallel:SPEED_PARALLEL,gap:0,apiMaxMs:first.apiMaxMs};
    save('dgn_diag_v25',{at:Date.now(),mode,q,...lastMeta,failedCodes});
    state[mode]={q,items:[...items],meta:lastMeta};
    render();updateStatus();
  }catch(e){setStatus(`<span class="err">검색 실패: ${esc(e.message||e)}</span>`)}
  finally{searching=false;$('go').disabled=false;if(!items.length)render()}
};

const baseUpdateStatus=updateStatus;
updateStatus=function(){
  baseUpdateStatus();
  if(lastMeta&&lastMeta.codes&&lastMeta.apiMaxMs){
    const el=$('status');
    el.innerHTML+=` · API최대 ${(lastMeta.apiMaxMs/1000).toFixed(1)}초`;
  }
};

$('limit').textContent='동네 최대 200곳 · v2.5 속도 우선 · 느린 요청 자동 포기';
