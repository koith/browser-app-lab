export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const BASE = 'https://www.daangn.com/kr/api/v1/fleamarket/search';
const PAGE = 'https://www.daangn.com/kr/buy-sell/s/?in=%EC%84%9C%EC%B4%88%EA%B5%AC-362&search=%EB%B8%8C%EB%A3%A8%EB%8D%94';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const out = {};

  // 1) 페이지 방문해 쿠키 확보
  const pr = await fetch(PAGE, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
  const raw = pr.headers.getSetCookie ? pr.headers.getSetCookie() : [pr.headers.get('set-cookie')].filter(Boolean);
  const cookie = raw.map(c => c.split(';')[0]).join('; ');
  out.cookieCount = raw.length;
  out.cookiePreview = cookie.slice(0, 200);

  const url = BASE + '?region_id=362&search=' + encodeURIComponent('브루더');
  const variants = [
    { name: 'cookie+secfetch', h: { Cookie: cookie, Referer: PAGE, Origin: 'https://www.daangn.com',
        'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty' } },
    { name: 'cookie only', h: { Cookie: cookie, Referer: PAGE } },
    { name: 'no cookie + secfetch', h: { Referer: PAGE, Origin: 'https://www.daangn.com',
        'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty' } },
    { name: 'x-requested-with', h: { Cookie: cookie, Referer: PAGE, 'X-Requested-With': 'XMLHttpRequest' } },
  ];
  out.tries = [];
  for (const v of variants) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9', ...v.h } });
      const b = await r.text();
      out.tries.push({ name: v.name, status: r.status, len: b.length, body: b.slice(0, 500) });
    } catch (e) { out.tries.push({ name: v.name, error: String(e.message || e).slice(0, 120) }); }
  }
  return res.status(200).json(out);
}
