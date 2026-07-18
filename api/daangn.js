// /api/daangn.js — 당근 지역별 검색 프록시
// GET /api/daangn?q=아이폰&regions=서초구-362,강남구-XXX&onSale=true
// 여러 지역을 병렬 fetch → 매물 파싱 → 통합 JSON 반환

export const config = { maxDuration: 60 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const CONCURRENCY = 6;
const MAX_REGIONS = 60;

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const q = (req.query.q || '').trim();
  const onSale = req.query.onSale === 'true';
  const regions = (req.query.regions || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  if (!q) return res.status(400).json({ error: 'q 파라미터 필요' });
  if (!regions.length) return res.status(400).json({ error: 'regions 파라미터 필요' });
  if (regions.length > MAX_REGIONS)
    return res.status(400).json({ error: `지역은 최대 ${MAX_REGIONS}개` });

  const t0 = Date.now();
  const results = [];
  const errors = [];

  // 동시성 제한 병렬 처리
  let idx = 0;
  async function worker() {
    while (idx < regions.length) {
      const region = regions[idx++];
      try {
        const items = await fetchRegion(q, region, onSale);
        results.push(...items);
      } catch (e) {
        errors.push({ region, error: String(e.message || e).slice(0, 200) });
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  // 매물 URL 기준 중복 제거 (인접 지역 중복 노출 대비)
  const seen = new Set();
  const deduped = [];
  for (const it of results) {
    if (seen.has(it.url)) continue;
    seen.add(it.url);
    deduped.push(it);
  }

  res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
  return res.status(200).json({
    query: q,
    regionCount: regions.length,
    count: deduped.length,
    tookMs: Date.now() - t0,
    errors,
    items: deduped,
  });
}

async function fetchRegion(q, region, onSale) {
  const url =
    'https://www.daangn.com/kr/buy-sell/?in=' +
    encodeURIComponent(region) +
    '&search=' +
    encodeURIComponent(q) +
    (onSale ? '&only_on_sale=true' : '');

  const r = await fetch(url, {
    headers: {
      'User-Agent': UA,
      'Accept-Language': 'ko-KR,ko;q=0.9',
      Accept: 'text/html,application/xhtml+xml',
    },
    redirect: 'follow',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const html = await r.text();
  return parseListings(html, region);
}

function parseListings(html, searchedRegion) {
  const items = [];
  // 매물 상세 링크 앵커 추출 (절대/상대 href 모두 대응, 검색용 /s/ 경로 제외)
  const anchorRe =
    /<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g;
  let m;
  while ((m = anchorRe.exec(html)) !== null) {
    const path = m[1];
    const inner = m[2];

    // 썸네일
    const imgM = inner.match(/<img[^>]*src="([^"]+)"/);
    // 텍스트만 추출
    const text = inner
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/\s+/g, ' ')
      .trim();
    if (!text) continue;

    // 판매 상태
    let status = 'on_sale';
    let rest = text;
    const stM = rest.match(/^(거래완료|판매완료|예약중)/);
    if (stM) {
      status = stM[1] === '예약중' ? 'reserved' : 'sold';
      rest = rest.slice(stM[1].length).trim();
    }

    // 상대 시간 (SSR에 없을 수 있음 → null 허용)
    let ago = null;
    const agoM = rest.match(/(?:끌올\s*)?(\d+)\s*(초|분|시간|일|개월|년)\s*전/);
    if (agoM) {
      const n = parseInt(agoM[1], 10);
      const unit = { 초: 1, 분: 60, 시간: 3600, 일: 86400, 개월: 2592000, 년: 31536000 }[agoM[2]];
      ago = n * unit; // 초 단위 경과시간 (근사)
      rest = rest.replace(agoM[0], '').trim();
    }

    // "제목 + 가격 + 동네명 + ·" 분해: 가격/나눔의 '마지막' 출현을 앵커로 사용
    let title = rest;
    let price = null; // 원 단위 숫자, 나눔=0
    let dong = null;
    const priceRe = /([\d,]+)\s*원|나눔/g;
    let pm, last = null;
    while ((pm = priceRe.exec(rest)) !== null) last = pm;
    if (last) {
      title = rest.slice(0, last.index).trim() || rest;
      price = last[1] ? parseInt(last[1].replace(/,/g, ''), 10) : 0;
      dong = rest.slice(last.index + last[0].length).replace(/·\s*$/, '').trim() || null;
    }

    items.push({
      url: 'https://www.daangn.com' + path,
      title,
      price, // null=파싱 실패, 0=나눔
      status, // on_sale | reserved | sold
      dong,
      region: searchedRegion, // 검색에 사용한 구/시 코드
      agoSec: ago, // null 가능
      thumb: imgM ? imgM[1] : null,
    });
  }
  return items;
}
