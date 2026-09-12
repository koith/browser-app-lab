// /api/daangn.js — 당근 지역별 검색 프록시 (JSON-LD 기반 파싱)
// GET /api/daangn?q=아이폰&regions=서초동-6128,역삼동-6035

export const config = { maxDuration: 60 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

// 프론트가 작은 배치로 호출하므로 한 invocation 안에서도 과도한 병렬화를 피한다.
const CONCURRENCY = 3;
const MAX_REGIONS = 45;
const BLOCK_PAGE_MAX = 220000;
const MAX_ATTEMPTS = 2;

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const q = (req.query.q || '').trim();
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
        results.push(...(await fetchRegion(q, region)));
      } catch (e) {
        errors.push({
          region,
          type: e && e.code ? e.code : 'fetch_error',
          error: String(e && (e.message || e) || 'unknown error').slice(0, 200),
        });
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, regions.length) }, worker));

  const seen = new Set();
  const deduped = [];
  for (const it of results) {
    if (seen.has(it.url)) continue;
    seen.add(it.url);
    deduped.push(it);
  }

  const blockedCount = errors.filter(e => e.type === 'blocked_page').length;
  res.setHeader('Cache-Control', 'no-store');
  return res.status(200).json({
    query: q,
    regionCount: regions.length,
    count: deduped.length,
    tookMs: Date.now() - t0,
    blockedCount,
    okRegionCount: regions.length - errors.length,
    errors,
    items: deduped,
  });
}

async function fetchRegion(q, region) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(region) +
    '&search=' + encodeURIComponent(q);

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const r = await fetch(url, {
      headers: {
        'User-Agent': UA,
        'Accept-Language': 'ko-KR,ko;q=0.9',
        Accept: 'text/html',
      },
      redirect: 'follow',
    });

    if (!r.ok) {
      if (attempt >= MAX_ATTEMPTS - 1) {
        const e = new Error(`HTTP ${r.status}`);
        e.code = 'http_error';
        throw e;
      }
      await backoff(attempt);
      continue;
    }

    const html = await r.text();
    const blocked = isBlockedPage(html);
    if (blocked) {
      if (attempt >= MAX_ATTEMPTS - 1) {
        const e = new Error(`차단성 빈 페이지 (${html.length} bytes)`);
        e.code = 'blocked_page';
        throw e;
      }
      await backoff(attempt);
      continue;
    }

    // 정상 크기의 페이지라면 결과가 0건이어도 정상 검색으로 인정한다.
    return parse(html, region);
  }

  const e = new Error('검색 실패');
  e.code = 'fetch_error';
  throw e;
}

function isBlockedPage(html) {
  // 실측상 차단성 빈 페이지는 약 157KB, 정상 페이지는 360KB+.
  // 구조가 바뀌어도 작은 페이지이면서 ItemList가 없을 때만 차단으로 본다.
  if (html.length >= BLOCK_PAGE_MAX) return false;
  return !/<script\s+type="application\/ld\+json">[\s\S]*?"@type"\s*:\s*"ItemList"/.test(html);
}

function backoff(attempt) {
  return new Promise(r => setTimeout(r, 300 * (attempt + 1) + Math.random() * 300));
}

function parse(html, region) {
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

  const times = [];
  const timeRe = /"createdAt"\s*:\s*"([^"]{10,30})"(?:[\s\S]{0,400}?"boostedAt"\s*:\s*"([^"]{10,30})")?/g;
  let tm;
  while ((tm = timeRe.exec(html)) !== null) {
    times.push({ createdAt: tm[1], boostedAt: tm[2] || null });
  }

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
