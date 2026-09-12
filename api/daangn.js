// /api/daangn.js — 당근 지역별 검색 프록시 (speed-first fast-fail)
export const config = { maxDuration: 60 };
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const CONCURRENCY=15, MAX_REGIONS=45, BLOCK_PAGE_MAX=220000, FETCH_TIMEOUT_MS=3500;

export default async function handler(req,res){
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET, OPTIONS');
  if(req.method==='OPTIONS') return res.status(200).end();
  const q=(req.query.q||'').trim();
  const regions=(req.query.regions||'').split(',').map(s=>s.trim()).filter(Boolean);
  if(!q) return res.status(400).json({error:'q 파라미터 필요'});
  if(!regions.length) return res.status(400).json({error:'regions 파라미터 필요'});
  if(regions.length>MAX_REGIONS) return res.status(400).json({error:`지역은 최대 ${MAX_REGIONS}개`});
  const t0=Date.now(),results=[],errors=[];let idx=0;
  async function worker(){
    while(idx<regions.length){
      const region=regions[idx++];
      try{results.push(...await fetchRegion(q,region));}
      catch(e){errors.push({region,type:e&&e.code?e.code:'fetch_error',attempts:1,lastBytes:e&&Number.isFinite(e.lastBytes)?e.lastBytes:null,error:String(e&&(e.message||e)||'unknown error').slice(0,200)});}
    }
  }
  await Promise.all(Array.from({length:Math.min(CONCURRENCY,regions.length)},worker));
  const seen=new Set(),items=[];
  for(const it of results){if(seen.has(it.url))continue;seen.add(it.url);items.push(it);}
  const blockedCount=errors.filter(e=>e.type==='blocked_page').length;
  const timeoutCount=errors.filter(e=>e.type==='timeout').length;
  res.setHeader('Cache-Control','no-store');
  return res.status(200).json({query:q,regionCount:regions.length,count:items.length,tookMs:Date.now()-t0,blockedCount,timeoutCount,okRegionCount:regions.length-errors.length,errors,items});
}

async function fetchRegion(q,region){
  const url='https://www.daangn.com/kr/buy-sell/?in='+encodeURIComponent(region)+'&search='+encodeURIComponent(q);
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);
  try{
    const r=await fetch(url,{headers:{'User-Agent':UA,'Accept-Language':'ko-KR,ko;q=0.9',Accept:'text/html'},redirect:'follow',signal:controller.signal});
    if(!r.ok){const e=new Error(`HTTP ${r.status}`);e.code='http_error';throw e;}
    // Important: keep the abort timer alive until the full HTML body has been consumed.
    const html=await r.text();
    if(isBlockedPage(html)){const e=new Error(`차단성 빈 페이지 (${html.length} bytes)`);e.code='blocked_page';e.lastBytes=html.length;throw e;}
    return parse(html,region);
  }catch(err){
    if(err&&err.name==='AbortError'){const e=new Error(`timeout ${FETCH_TIMEOUT_MS}ms`);e.code='timeout';throw e;}
    throw err;
  }finally{
    clearTimeout(timer);
  }
}
function isBlockedPage(html){if(html.length>=BLOCK_PAGE_MAX)return false;return !/<script\s+type="application\/ld\+json">[\s\S]*?"@type"\s*:\s*"ItemList"/.test(html);}
function parse(html,region){
  let products=[];
  for(const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)){let data;try{data=JSON.parse(m[1]);}catch{continue;}if(data&&data['@type']==='ItemList'&&Array.isArray(data.itemListElement)){products=data.itemListElement.map(e=>e&&e.item).filter(p=>p&&p.url).map(p=>({url:p.url,title:p.name||'',price:p.offers&&p.offers.price!=null?Math.round(parseFloat(p.offers.price)):null,status:p.offers&&/InStock/i.test(p.offers.availability||'')?'on_sale':'sold',thumb:p.image||null}));break;}}
  const times=[];for(const tm of html.matchAll(/"createdAt"\s*:\s*"([^"]{10,30})"(?:[\s\S]{0,400}?"boostedAt"\s*:\s*"([^"]{10,30})")?/g))times.push({createdAt:tm[1],boostedAt:tm[2]||null});
  const dongByUrl={};for(const am of html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g)){const text=am[2].replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();const dm=text.match(/(?:원|나눔)\s*([가-힣]+(?:동|읍|면|가))/);if(dm)dongByUrl['https://www.daangn.com'+am[1]]=dm[1];}
  const useTimes=times.length>=products.length;
  return products.map((p,i)=>{const t=useTimes?times[i]:null;const created=t&&t.createdAt?Date.parse(t.createdAt+(/[Z+]/.test(t.createdAt)?'':'+09:00')):null;const boosted=t&&t.boostedAt?Date.parse(t.boostedAt+(/[Z+]/.test(t.boostedAt)?'':'+09:00')):null;return {...p,region,dong:dongByUrl[p.url]||null,createdAt:created||null,boostedAt:boosted||null,sortTime:boosted||created||null,isBoosted:!!(boosted&&created&&boosted-created>60000)};});
}
