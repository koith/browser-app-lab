// /api/daangn-regions.js — 지역 코드 수집기 (1회성)
// GET /api/daangn-regions?seed=서초4동-366
// 해당 지역 페이지 1개를 fetch → 페이지 소속(시/도) + 페이지 내 모든 ?in= 링크 반환
// 프론트(수집 모드)가 BFS로 반복 호출하며 서울/경기 구·시 코드를 모음

export const config = { maxDuration: 30 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const seed = (req.query.seed || '').trim();
  if (!seed) return res.status(400).json({ error: 'seed 파라미터 필요 (예: 서초4동-366)' });

  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(seed);
  const r = await fetch(url, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' },
    redirect: 'follow',
  });
  if (!r.ok) return res.status(502).json({ error: `daangn HTTP ${r.status}` });
  const html = await r.text();

  // 페이지 소속 지역 (예: "서울특별시 서초구 서초4동 중고거래 | 당근")
  const titleM = html.match(/<title>([^<]*)<\/title>/);
  const pageRegion = titleM ? titleM[1].replace(/중고거래.*$/, '').trim() : '';

  // 페이지 내 모든 ?in=이름-ID 링크 수집
  const links = new Map();
  const linkRe = /[?&]in=([^"&#]+)/g;
  let m;
  while ((m = linkRe.exec(html)) !== null) {
    let code;
    try {
      code = decodeURIComponent(m[1]);
    } catch {
      continue;
    }
    if (/^[가-힣0-9]+-\d+$/.test(code)) links.set(code, true);
  }

  return res.status(200).json({
    seed,
    pageRegion, // 프론트가 서울/경기 여부 판단에 사용
    links: [...links.keys()],
  });
}
