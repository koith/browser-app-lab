// /api/pricelens/prices — 제품명으로 네이버 카탈로그 + 쿠팡 가격 수집
// 필수 env: SERPER_KEY (기존 보유)
// 참고: 네이버 쇼핑 검색 API가 2026-07-31 종료(대체 API 없음)되어 Serper 기반으로 전환

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

async function serper(q, num) {
  const r = await fetch('https://google.serper.dev/search', {
    method: 'POST',
    headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, gl: 'kr', hl: 'ko', num: num || 10 })
  });
  if (!r.ok) throw new Error('serper: ' + r.status);
  return (await r.json()).organic || [];
}

function extractPrice(text) {
  const m = (text || '').match(/(?:최저\s*)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})\s*원/);
  return m ? m[1] + '원' : null;
}

// 네이버 가격비교 카탈로그 페이지 탐색
async function naverCatalog(query) {
  const results = await serper(query + ' site:search.shopping.naver.com', 10);
  const catalogs = results
    .filter(o => /search\.shopping\.naver\.com\/catalog\//.test(o.link || ''))
    .slice(0, 4)
    .map(o => ({
      title: (o.title || '').replace(/\s*[:|-]\s*네이버\s*쇼핑.*$/, '').trim(),
      link: o.link,
      price: extractPrice(o.snippet),
      isCatalog: true
    }));
  // 카탈로그가 하나도 없으면 네이버쇼핑 검색 페이지 링크라도 제공
  if (!catalogs.length) {
    catalogs.push({
      title: '네이버쇼핑에서 「' + query + '」 직접 검색',
      link: 'https://search.shopping.naver.com/search/all?query=' + encodeURIComponent(query),
      price: null,
      isCatalog: false
    });
  }
  return catalogs;
}

async function coupang(query) {
  const results = await serper(query + ' site:coupang.com', 10);
  const items = results
    .filter(o => /coupang\.com\/vp\/products/.test(o.link || '') && !/품절|sold\s?out/i.test((o.title||'') + (o.snippet||'')))
    .slice(0, 4)
    .map(o => ({
      title: (o.title || '').replace(/\s*[-|]\s*쿠팡.*$/, '').trim(),
      link: o.link,
      price: extractPrice(o.snippet)
    }));
  if (!items.length) {
    items.push({
      title: '쿠팡에서 「' + query + '」 직접 검색',
      link: 'https://www.coupang.com/np/search?q=' + encodeURIComponent(query),
      price: null
    });
  }
  return items;
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  let { query } = req.body || {};
  if (!query || !query.trim()) return res.status(400).json({ error: 'query required', step: 'input' });
  // 판매 페이지 제목 → 검색어 정제: 옵션/사은품/수량 꼬리 제거
  query = query.split(',')[0]
    .replace(/[\[\(][^\]\)]*[\]\)]/g, ' ')
    .replace(/\+\S+/g, ' ')
    .replace(/\b\d+\s?(개|매|입|세트|팩)\b/g, ' ')
    .replace(/\s+/g, ' ').trim();
  if (!process.env.SERPER_KEY) return res.status(500).json({ error: 'SERPER_KEY 미설정', step: 'config' });

  try {
    const [nv, cp] = await Promise.allSettled([
      naverCatalog(query.trim()),
      coupang(query.trim())
    ]);
    return res.status(200).json({
      naver: nv.status === 'fulfilled' ? nv.value : [],
      coupang: cp.status === 'fulfilled' ? cp.value : [],
      errors: {
        naver: nv.status === 'rejected' ? nv.reason.message : null,
        coupang: cp.status === 'rejected' ? cp.reason.message : null
      }
    });
  } catch (e) {
    return res.status(500).json({ error: e.message, step: 'search' });
  }
};
