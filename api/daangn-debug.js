export const config = { maxDuration: 60 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' };

async function look(code, q) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q);
  const r = await fetch(url, { headers: H });
  const html = await r.text();
  const raw = r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')].filter(Boolean);
  let resolved = null;
  for (const c of raw) {
    const m = c.match(/search_region=([^;]+)/);
    if (m) { try { resolved = JSON.parse(Buffer.from(decodeURIComponent(m[1]), 'base64').toString('utf8')).regionName; } catch {} }
  }
  const n = html.match(/"numberOfItems"\s*:\s*(\d+)/);
  const urls = [...new Set([...html.matchAll(/"url":"(https:\/\/www\.daangn\.com\/kr\/buy-sell\/[^"]+)"/g)].map(m => m[1]))];
  return { code, resolved, numberOfItems: n ? +n[1] : null, urls };
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '브루더';
  // 서초구 코드 + 서초구 소속 동 코드들
  const codes = ['서초구-362', '서초동-6128', '잠원동-367', '반포동-6126', '방배동-6127', '서초3동-365', '서초4동-366'];
  const out = [];
  const all = new Set();
  for (const c of codes) {
    try {
      const r = await look(c, q);
      r.urls.forEach(u => all.add(u));
      out.push({ code: r.code, resolved: r.resolved, n: r.numberOfItems, uniqueUrls: r.urls.length });
    } catch (e) { out.push({ code: c, error: String(e.message || e).slice(0, 100) }); }
  }
  return res.status(200).json({ q, perRegion: out, unionTotal: all.size });
}
