// 모임(group) / 동네생활(community) 검색 SSR 가능 여부 확인
export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' };

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '등산';
  const region = req.query.region || '서초동-6128';
  const paths = ['/kr/group/', '/kr/group/s/', '/kr/community/', '/kr/community/s/'];
  const out = [];
  for (const p of paths) {
    const url = `https://www.daangn.com${p}?in=${encodeURIComponent(region)}&search=${encodeURIComponent(q)}`;
    try {
      const r = await fetch(url, { headers: H, redirect: 'follow' });
      const html = await r.text();
      const title = (html.match(/<title>([^<]*)<\/title>/) || [])[1] || '';
      const ld = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => {
        try { const d = JSON.parse(m[1]); return d['@type'] + (d.numberOfItems != null ? ':' + d.numberOfItems : ''); } catch { return 'parse-fail'; }
      });
      const links = [...new Set([...html.matchAll(/href="(\/kr\/(?:group|community)\/[^"?#]+\/)"/g)].map(m => m[1]))];
      out.push({ path: p, status: r.status, bytes: html.length, title, jsonLd: ld, linkCount: links.length, sample: links.slice(0, 3) });
    } catch (e) { out.push({ path: p, error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json({ q, region, out });
}
