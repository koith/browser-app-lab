// v2.4 aggressive speed-first scheduler.
// 15 dongs per API call, four calls in parallel (up to 60 dongs/wave), no fixed sleeps.
// Failed/blocked/timeout dongs are left for manual retry only.
const SPEED_BATCH=15, SPEED_PARALLEL=4;

pass=async function(q,codes,label='검색'){
  const seen=new Set(items.map(x=>x.url));
  let ok=0,blocked=0,fail=[];
  const batches=[];
  for(let i=0;i<codes.length;i+=SPEED_BATCH)batches.push(codes.slice(i,i+SPEED_BATCH));
  let completed=0;
  for(let i=0;i<batches.length;i+=SPEED_PARALLEL){
    const wave=batches.slice(i,i+SPEED_PARALLEL);
    setStatus(`<span class="spin"></span>${label} ${Math.min(completed+wave.reduce((n,b)=>n+b.length,0),codes.length)}/${codes.length} · 현재 <b>${items.length}</b>건`);
    const outs=await Promise.all(wave.map(async b=>{
      try{return {b,d:await requestBatch(q,b)}}catch{return {b,d:null}}
    }));
    for(const {b,d} of outs){
      completed+=b.length;
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
  }
  return {ok,blocked,pauses:0,failed:[...new Set(fail)]};
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
    lastMeta={codes:codes.length,ok:Math.max(0,codes.length-failedCodes.length),failed:failedCodes.length,blocked:first.blocked,dongFails:dongFails.length,recovered:0,pauses:0,sec:((Date.now()-t0)/1000).toFixed(1),batch:SPEED_BATCH,parallel:SPEED_PARALLEL,gap:0};
    save('dgn_diag_v24',{at:Date.now(),mode,q,...lastMeta,failedCodes});
    state[mode]={q,items:[...items],meta:lastMeta};
    render();updateStatus();
  }catch(e){setStatus(`<span class="err">검색 실패: ${esc(e.message||e)}</span>`)}
  finally{searching=false;$('go').disabled=false;if(!items.length)render()}
};

$('limit').textContent='동네 최대 200곳 · 초고속 우선 검색';
