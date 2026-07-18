export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const kw = req.query.kw || '서초구';
  const H = {
    'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9',
    Accept: 'application/json, text/plain, */*',
    Referer: 'https://www.daangn.com/kr/buy-sell/',
  };
  const base = 'https://www.daangn.com/kr/api/v1/regions/keyword';
  const tries = [
    `${base}?keyword=${encodeURIComponent(kw)}`,
    `${base}?query=${encodeURIComponent(kw)}`,
    `${base}?search=${encodeURIComponent(kw)}`,
    `${base}?keyword=${encodeURIComponent(kw)}&country_code=kr`,
    `https://www.daangn.com/kr/api/v1/regions/coord?lat=37.4837&lng=127.0324`,
  ];
  const out = [];
  for (const u of tries) {
    try {
      const r = await fetch(u, { headers: H });
      const b = await r.text();
      out.push({ url: u.replace('https://www.daangn.com', ''), status: r.status, len: b.length, body: b.slice(0, 900) });
    } catch (e) { out.push({ url: u, error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json({ out });
}
