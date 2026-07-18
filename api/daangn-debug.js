// /api/daangn-debug.js — 검색 추가 로딩 API 탐색
export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' };
  const root = 'https://www.daangn.com/kr/buy-sell/s/?in=' + encodeURIComponent('서초구-362') + '&search=' + encodeURIComponent('브루더');
  const html = await (await fetch(root, { headers: H })).text();

  const scripts = [...new Set([...html.matchAll(/(?:src|href)="([^"]+\.js)"/g)].map(m => m[1]))]
    .map(u => u.startsWith('http') ? u : 'https://www.daangn.com' + u);
  // 검색 관련 청크 우선
  scripts.sort((a, b) => (/(search|buy-sell|article|list)/i.test(b) ? 1 : 0) - (/(search|buy-sell|article|list)/i.test(a) ? 1 : 0));

  const hits = new Set();
  const grep = (t) => {
    for (const m of t.matchAll(/["'`](https?:\/\/[a-z0-9\.\-]*(?:karrot|daangn)[a-z0-9\.\-]*\/[^"'`\s]{0,90})["'`]/gi)) hits.add(m[1]);
    for (const m of t.matchAll(/["'`](\/[a-z0-9_\-\/\.]*(?:search|articles|flea_market|graphql|api)[a-z0-9_\-\/\.]*)["'`]/gi)) hits.add(m[1]);
  };
  grep(html);

  const scanned = [];
  for (const su of scripts.slice(0, 14)) {
    try {
      const r = await fetch(su, { headers: H });
      if (!r.ok) { scanned.push(su.split('/').pop() + ' HTTP' + r.status); continue; }
      const t = await r.text();
      grep(t);
      scanned.push(su.split('/').pop() + ' ok');
    } catch { scanned.push(su.split('/').pop() + ' ERR'); }
  }
  const filtered = [...hits].filter(h => /search|article|graphql|api|flea/i.test(h));
  return res.status(200).json({ scriptCount: scripts.length, scanned, hitCount: filtered.length, hits: filtered.slice(0, 100) });
}
