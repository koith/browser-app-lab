// /api/daangn-regions.js — 지역 코드 수집기 (1회성)
// GET /api/daangn-regions?seed=서초4동-366[&debug=1]
// 일반 페이지(주변 동 링크) + 검색 페이지(구/시 헤더 링크)를 모두 읽어 링크 통합 반환

export const config = { maxDuration: 30 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const seed = (req.query.seed || '').trim();
  const debug = req.query.debug === '1';
  if (!seed) return res.status(400).json({ error: 'seed 파라미터 필요 (예: 서초4동-366)' });

  const base = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(seed);
  const urls = [base, base + '&search=' + encodeURIComponent('시계')]; // 검색 페이지에만 구/시 헤더 노출

  let pageRegion = '';
  const links = new Map();
  const hrefsSample = new Set();
  const fails = [];

  for (const url of urls) {
    let html;
    try {
      const r = await fetch(url, {
        headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' },
        redirect: 'follow',
      });
      if (!r.ok) { fails.push(`${url.includes('search') ? 'search' : 'plain'}: HTTP ${r.status}`); continue; }
      html = await r.text();
    } catch (e) {
      fails.push(String(e.message || e).slice(0, 120));
      continue;
    }

    if (!pageRegion) {
      const titleM = html.match(/<title>([^<]*)<\/title>/);
      if (titleM) pageRegion = titleM[1].replace(/중고거래.*$/, '').trim();
    }

    const linkRe = /[?&](?:amp;)?in=([^"&#\s]+)/g;
    let m;
    while ((m = linkRe.exec(html)) !== null) {
      let code;
      try { code = decodeURIComponent(m[1]); } catch { continue; }
      if (/^[가-힣0-9]+-\d+$/.test(code)) links.set(code, true);
    }

    if (debug) {
      const hrefRe = /href="([^"]*buy-sell[^"]*)"/g;
      let h;
      while ((h = hrefRe.exec(html)) !== null && hrefsSample.size < 80) hrefsSample.add(h[1]);
    }
  }

  if (!pageRegion && fails.length === urls.length)
    return res.status(502).json({ error: 'daangn fetch 실패', fails });

  const out = { seed, pageRegion, links: [...links.keys()], fails };
  if (debug) out.hrefsSample = [...hrefsSample];
  return res.status(200).json(out);
}
