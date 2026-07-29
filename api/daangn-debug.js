export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  const q = req.query.q || '브루더';
  const region = req.query.region || '천호제3동-6128';
  // 여러 후보 URL 형태 시도 (당근이 경로를 바꿨을 가능성)
  const cands = [
    'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q),
    'https://www.daangn.com/kr/buy-sell/s/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q),
  ];
  const out = [];
  for (const url of cands) {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
    const html = await r.text();
    const ld = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
    const anchors = [...html.matchAll(/href="(?:https?:\/\/www\.daangn\.com)?\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\//g)].length;
    const numItems = (html.match(/"numberOfItems"\s*:\s*(\d+)/) || [])[1] || null;
    out.push({ url: url.replace('https://www.daangn.com',''), status: r.status, bytes: html.length, ldCount: ld.length, anchors, numItems });
  }
  return res.status(200).json({ ts: new Date().toISOString(), out });
}
