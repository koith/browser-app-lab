// /api/daangn-debug.js — 검색 결과 HTML 구조 진단용 (임시)
export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '의자';
  const region = req.query.region || '서초구-362';
  const out = [];

  for (const page of ['', '&page=2']) {
    const url = `https://www.daangn.com/kr/buy-sell/s/?in=${encodeURIComponent(region)}&search=${encodeURIComponent(q)}${page}`;
    let html = '';
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' } });
      html = await r.text();
      const anchors = [...html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\/)"/g)].map(m => m[1]);
      const uniq = [...new Set(anchors)];
      // 시간 표기 후보 탐색
      const timeHits = [...new Set([...html.matchAll(/(끌올\s*)?\d+\s*(초|분|시간|일|개월|년)\s*전/g)].map(m => m[0]))].slice(0, 8);
      const isoHits = [...new Set([...html.matchAll(/"(?:createdAt|publishedAt|updatedAt|refreshedAt|sortedAt)"\s*:\s*"([^"]{10,30})"/g)].map(m => m[0]))].slice(0, 5);
      // 첫 매물 앵커 원문 스니펫
      const idx = html.indexOf('/kr/buy-sell/', html.indexOf('<main') > 0 ? html.indexOf('<main') : 0);
      const anchorStart = html.lastIndexOf('<a', idx);
      const snippet = anchorStart > 0 ? html.slice(anchorStart, anchorStart + 1200) : '';
      out.push({ page: page || 'page1', status: r.status, bytes: html.length, itemCount: uniq.length, firstItems: uniq.slice(0, 3), timeHits, isoHits, snippet });
    } catch (e) {
      out.push({ page: page || 'page1', error: String(e.message || e).slice(0, 150) });
    }
  }
  return res.status(200).json({ q, region, out });
}
