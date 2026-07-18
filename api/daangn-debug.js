// /api/daangn-debug.js — 실제 사용 경로(/kr/buy-sell/) 기준 진단
export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '브루더';
  const region = req.query.region || '서초구-362';
  const variants = ['', '&page=2', '&pageNum=2', '&offset=24', '&cursor=2'];
  const out = [];

  for (const v of variants) {
    const url = `https://www.daangn.com/kr/buy-sell/?in=${encodeURIComponent(region)}&search=${encodeURIComponent(q)}${v}`;
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' } });
      const html = await r.text();
      const items = [...new Set([...html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\/)"/g)].map(m => m[1]))];
      const entry = { v: v || 'base', status: r.status, bytes: html.length, itemCount: items.length, first: items[0] || null, last: items[items.length - 1] || null };
      if (!v) {
        entry.timeHits = [...new Set([...html.matchAll(/(?:끌올\s*)?\d+\s*(?:초|분|시간|일|개월|년)\s*전/g)].map(m => m[0]))].slice(0, 6);
        entry.dateFields = [...new Set([...html.matchAll(/"(\w*(?:[Aa]t|[Tt]ime|date))"\s*:\s*"?([\d\-T:\.Z]{8,30})"?/g)].map(m => m[1] + '=' + m[2]))].slice(0, 10);
        const i = html.indexOf(items[0] || 'zzz');
        entry.itemSnippet = i > 0 ? html.slice(Math.max(0, html.lastIndexOf('<a', i)), i + 900) : '';
      }
      out.push(entry);
    } catch (e) { out.push({ v: v || 'base', error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json({ q, region, out });
}
