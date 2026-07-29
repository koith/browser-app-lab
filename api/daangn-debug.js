export const config = { maxDuration: 30 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '브루더';
  const region = req.query.region || '서초동-6128';
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q);
  const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
  const html = await r.text();
  // 진단 지표들
  const ldBlocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  const ldTypes = ldBlocks.map(m => { try { return JSON.parse(m[1])['@type']; } catch { return 'parse-fail'; } });
  const hasItemList = ldBlocks.some(m => { try { return JSON.parse(m[1])['@type'] === 'ItemList'; } catch { return false; } });
  const anchorCount = [...html.matchAll(/href="(?:https?:\/\/www\.daangn\.com)?\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\//g)].length;
  const title = (html.match(/<title>([^<]*)<\/title>/) || [])[1] || '';
  // 첫 ld 블록 원문 앞부분
  const firstLd = ldBlocks.length ? ldBlocks[0][1].slice(0, 500) : null;
  const bodySample = html.slice(0, 200);
  return res.status(200).json({
    status: r.status, bytes: html.length, title,
    ldCount: ldBlocks.length, ldTypes, hasItemList, anchorCount,
    firstLd, bodySample,
  });
}
