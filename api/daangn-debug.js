export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const BASE = 'https://www.daangn.com/kr/api/v1/fleamarket/search';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'application/json, text/plain, */*',
    Referer: 'https://www.daangn.com/kr/buy-sell/s/?in=%EC%84%9C%EC%B4%88%EA%B5%AC-362&search=%EB%B8%8C%EB%A3%A8%EB%8D%94' };
  const q = encodeURIComponent(req.query.q || '브루더');
  const rid = req.query.rid || '362';

  const tries = [
    `?region_id=${rid}`,
    `?region_id=${rid}&search=${q}`,
    `?region_id=${rid}&keyword=${q}`,
    `?region_id=${rid}&query=${q}`,
    `?region_id=${rid}&search=${q}&page=2`,
    `?region_id=${rid}&search=${q}&page_token=2`,
    `?region_id=${rid}&search=${q}&offset=38&limit=24`,
    `?region_id=${rid}&search=${q}&only_on_sale=true`,
  ];
  const out = [];
  for (const t of tries) {
    try {
      const r = await fetch(BASE + t, { headers: H });
      const body = await r.text();
      out.push({ params: t, status: r.status, len: body.length, body: body.slice(0, 700) });
    } catch (e) { out.push({ params: t, error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json({ out });
}
