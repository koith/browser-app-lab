// /api/daangn-debug.js — fleamarket/search API 파라미터 규격 탐색
export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const BASE = 'https://www.daangn.com/kr/api/v1/fleamarket/search';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const H = {
    'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9',
    Accept: 'application/json, text/plain, */*',
    Referer: 'https://www.daangn.com/kr/buy-sell/s/?in=%EC%84%9C%EC%B4%88%EA%B5%AC-362&search=%EB%B8%8C%EB%A3%A8%EB%8D%94',
  };
  const q = encodeURIComponent(req.query.q || '브루더');
  const region = encodeURIComponent(req.query.region || '서초구-362');

  const gets = [
    `?search=${q}&in=${region}`,
    `?search=${q}&in=${region}&page=2`,
    `?search=${q}&in=${region}&pageToken=2`,
    `?query=${q}&in=${region}`,
    `?keyword=${q}&regionId=362`,
    `?search=${q}&regionId=362&offset=38&limit=24`,
  ];
  const out = [];
  for (const g of gets) {
    try {
      const r = await fetch(BASE + g, { headers: H });
      const t = await r.text();
      out.push({ method: 'GET', params: g, status: r.status, ct: r.headers.get('content-type'), body: t.slice(0, 400) });
    } catch (e) { out.push({ method: 'GET', params: g, error: String(e.message || e).slice(0, 120) }); }
  }

  // POST 시도
  const posts = [
    { search: req.query.q || '브루더', in: req.query.region || '서초구-362' },
    { keyword: req.query.q || '브루더', regionId: 362, page: 2 },
  ];
  for (const b of posts) {
    try {
      const r = await fetch(BASE, { method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
      const t = await r.text();
      out.push({ method: 'POST', params: JSON.stringify(b), status: r.status, ct: r.headers.get('content-type'), body: t.slice(0, 400) });
    } catch (e) { out.push({ method: 'POST', params: JSON.stringify(b), error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json({ base: BASE, out });
}
