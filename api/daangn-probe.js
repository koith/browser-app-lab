// /api/daangn-probe.js — 누적 요청량 차단 검증 (multi-round)
export const config = { maxDuration: 300 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const DONGS = [
  '서초동-6128','잠원동-367','반포동-6126','방배동-6127','서초3동-365','양재동-6130','서초4동-366',
  '역삼동-6144','논현동-6136','삼성동-6140','청담동-6134','신사동-6135','압구정동-6137','대치동-6142',
  '개포동-6146','도곡동-6143','일원동-6148','수서동-6149','세곡동-6150','논현2동-374','역삼1동-370',
  '천호동-451','성내동-448','길동-455','둔촌동-457','암사동-445','명일동-449','고덕동-452','상일동-453',
  '강일동-6280','방배본동-359','방배4동-361','양재1동-379','내곡동-383','반포본동-352','반포1동-353',
  '잠원동-6129','서초1동-363','서초2동-364','반포4동-357',
];

async function fetchOne(code, q) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q);
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
    const html = await r.text();
    const items = [...new Set([...html.matchAll(/href="(?:https?:\/\/www\.daangn\.com)?\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\//g)])].length;
    return { empty: items === 0, bytes: html.length };
  } catch (e) { return { empty: true, error: true }; }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  const rounds = Math.min(parseInt(req.query.rounds || '1', 10), 15);
  const parallel = Math.min(parseInt(req.query.parallel || '10', 10), 40);
  const delay = parseInt(req.query.delay || '0', 10);
  const q = req.query.q || '브루더';
  const codes = DONGS.slice(0, parallel);

  const t0 = Date.now();
  const roundStats = [];
  for (let round = 0; round < rounds; round++) {
    const results = [];
    let idx = 0;
    await Promise.all(Array.from({ length: Math.min(parallel, codes.length) }, async () => {
      while (idx < codes.length) {
        results.push(await fetchOne(codes[idx++], q));
        if (delay) await new Promise(r => setTimeout(r, delay));
      }
    }));
    const empty = results.filter(r => r.empty).length;
    roundStats.push({ round: round + 1, empty, emptyRate: (empty / codes.length * 100).toFixed(0) + '%' });
  }
  return res.status(200).json({
    parallel, delay, rounds, perRound: codes.length,
    totalRequests: codes.length * rounds,
    totalMs: Date.now() - t0,
    roundStats,
  });
}
