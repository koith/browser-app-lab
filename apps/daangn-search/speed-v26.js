// v2.6 burst mode: fire every 15-dong batch immediately.
// Speed is prioritized over completeness; blocked/slow batches are left for manual retry.
const SPEED_BATCH=15, CLIENT_API_TIMEOUT_MS=4000;

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
  }finally{clearTimeout(timer)}
};

pass=async function(q,codes,label='검색'){
  const seen=new Set(items.map(x=>x.url));
  const batches=[];
  for(let i=0;i<codes.length;i+=SPEED_BATCH)batches.push(codes.slice(i,i+SPEED_BATCH));
  let completed=0,ok=0,blocked=0,fail=[],apiMaxMs=0;
  setStatus(`<span class="spin"></span>${label} 0/${codes.length} · 전체 병렬 검색 시작`);

  const jobs=batches.map(async b=>{
    const t=Date.now();
    let d=null;
    try{d=await requestBatch(q,b)}catch{}
    const ms=Date.now()-t;
    apiMaxMs=Math.max(apiMaxMs,ms);
    completed+=b.length;
    if(!d){fail.push(...b)}else{
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
    setStatus(`<span class="spin"></span>${label} ${Math.min(completed,codes.length)}/${codes.length} · 현재 <b>${items.length}</b>건`);
  });
  await Promise.all(jobs);
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
    lastMeta={codes:codes.length,ok:Math.max(0,codes.length-failedCodes.length),failed:failedCodes.length,blocked:first.blocked,dongFails:dongFails.length,recovered:0,pauses:0,sec:((Date.now()-t0)/1000).toFixed(1),batch:SPEED_BATCH,parallel:'all',gap:0,apiMaxMs:first.apiMaxMs};
    save('dgn_diag_v26',{at:Date.now(),mode,q,...lastMeta,failedCodes});
    state[mode]={q,items:[...items],meta:lastMeta};
    render();updateStatus();
  }catch(e){setStatus(`<span class="err">검색 실패: ${esc(e.message||e)}</span>`)}
  finally{searching=false;$('go').disabled=false;if(!items.length)render()}
};

const baseUpdateStatus=updateStatus;
updateStatus=function(){
  baseUpdateStatus();
  if(lastMeta&&lastMeta.codes&&lastMeta.apiMaxMs){$('status').innerHTML+=` · API최대 ${(lastMeta.apiMaxMs/1000).toFixed(1)}초`;}
};
$('limit').textContent='동네 최대 200곳 · v2.6 버스트 검색 · 속도 최우선';
