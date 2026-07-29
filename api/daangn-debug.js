export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '브루더';
  const rid = req.query.rid || '6128';
  const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'application/json, text/plain, */*',
    Referer: 'https://www.daangn.com/kr/buy-sell/?in=%EC%84%9C%EC%B4%88%EB%8F%99-6128&search=' + encodeURIComponent(q) };
  const bases = [
    `https://www.daangn.com/kr/api/v1/fleamarket/search?region_id=${rid}&search=${encodeURIComponent(q)}`,
    `https://www.daangn.com/kr/api/v1/fleamarket/search?region_id=${rid}&keyword=${encodeURIComponent(q)}`,
    `https://www.daangn.com/kr/api/v1/fleamarket/articles?region_id=${rid}&search=${encodeURIComponent(q)}`,
  ];
  const out = [];
  for (const u of bases) {
    try {
      const r = await fetch(u, { headers: H });
      const b = await r.text();
      out.push({ url: u.replace('https://www.daangn.com',''), status: r.status, ct: r.headers.get('content-type'), len: b.length, body: b.slice(0, 600) });
    } catch (e) { out.push({ url: u, error: String(e.message||e).slice(0,120) }); }
  }
  // 페이지 안에 다음 데이터(remix)가 인라인으로 있는지도 확인
  const pageUrl = 'https://www.daangn.com/kr/buy-sell/?in=%EC%84%9C%EC%B4%88%EB%8F%99-6128&search=' + encodeURIComponent(q);
  const html = await (await fetch(pageUrl, { headers: { 'User-Agent': UA } })).text();
  const hasStreamData = /window\.__remixContext|__remixContext|streamController|"articles?"|fleamarket/i.test(html);
  const jsonHints = [...new Set([...html.matchAll(/"([a-zA-Z_]{4,20}(?:Id|At|Price|Title|title|name))"\s*:/g)].map(m=>m[1]))].slice(0,20);
  return res.status(200).json({ apiTries: out, hasStreamData, jsonHints });
}
