// /api/daangn.js — 당근 지역별 검색 프록시 (JSON-LD 기반 파싱)
// GET /api/daangn?q=아이폰&regions=서초구-362,강남구-XXX&onSale=true

export const config = { maxDuration: 60 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const CONCURRENCY = 8;
const MAX_REGIONS = 45;

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const q = (req.query.q || '').trim();
  const onSale = req.query.onSale === 'true';
  const regions = (req.query.regions || '').split(',').map(s => s.trim()).filter(Boolean);

  if (!q) return res.status(400).json({ error: 'q 파라미터 필요' });
  if (!regions.length) return res.status(400).json({ error: 'regions 파라미터 필요' });
  if (regions.length > MAX_REGIONS) return res.status(400).json({ error: `지역은 최대 ${MAX_REGIONS}개` });

  const t0 = Date.now();
  const results = [];
  const errors = [];

  let idx = 0;
  async function worker() {
    while (idx < regions.length) {
      const region = regions[idx++];
      try {
        results.push(...(await fetchRegion(q, region, onSale)));
      } catch (e) {
        errors.push({ region, error: String(e.message || e).slice(0, 200) });
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  const seen = new Set();
  const deduped = [];
  for (const it of results) {
    if (seen.has(it.url)) continue;
    seen.add(it.url);
    deduped.push(it);
  }

  res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
  return res.status(200).json({
    query: q, regionCount: regions.length, count: deduped.length,
    tookMs: Date.now() - t0, errors, items: deduped,
  });
}

async function fetchRegion(q, region, onSale) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(region) +
    '&search=' + encodeURIComponent(q) + '';
  const r = await fetch(url, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' },
    redirect: 'follow',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return parse(await r.text(), region);
}

function parse(html, region) {
  // 1) JSON-LD ItemList에서 제목/가격/이미지/상태/URL 추출
  let products = [];
  for (const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    let data;
    try { data = JSON.parse(m[1]); } catch { continue; }
    if (data && data['@type'] === 'ItemList' && Array.isArray(data.itemListElement)) {
      products = data.itemListElement
        .map(e => e && e.item)
        .filter(p => p && p.url)
        .map(p => ({
          url: p.url,
          title: p.name || '',
          price: p.offers && p.offers.price != null ? Math.round(parseFloat(p.offers.price)) : null,
          status: p.offers && /InStock/i.test(p.offers.availability || '') ? 'on_sale' : 'sold',
          thumb: p.image || null,
        }));
      break;
    }
  }

  // 2) 임베디드 데이터에서 시간 추출 (문서 순서 = 목록 순서)
  const times = [];
  const timeRe = /"createdAt"\s*:\s*"([^"]{10,30})"(?:[\s\S]{0,400}?"boostedAt"\s*:\s*"([^"]{10,30})")?/g;
  let tm;
  while ((tm = timeRe.exec(html)) !== null) {
    times.push({ createdAt: tm[1], boostedAt: tm[2] || null });
  }

  // 3) 동네명 추출 (앵커 텍스트 기반, URL로 매칭)
  const dongByUrl = {};
  for (const am of html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g)) {
    const text = am[2].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const dm = text.match(/(?:원|나눔)\s*([가-힣]+(?:동|읍|면|가))/);
    if (dm) dongByUrl['https://www.daangn.com' + am[1]] = dm[1];
  }

  const useTimes = times.length >= products.length;
  return products.map((p, i) => {
    const t = useTimes ? times[i] : null;
    const created = t && t.createdAt ? Date.parse(t.createdAt + (/[Z+]/.test(t.createdAt) ? '' : '+09:00')) : null;
    const boosted = t && t.boostedAt ? Date.parse(t.boostedAt + (/[Z+]/.test(t.boostedAt) ? '' : '+09:00')) : null;
    const shown = boosted || created;
    return {
      ...p,
      region,
      dong: dongByUrl[p.url] || null,
      createdAt: created || null,
      boostedAt: boosted || null,
      sortTime: shown || null,
      isBoosted: !!(boosted && created && boosted - created > 60000),
    };
  });
}
