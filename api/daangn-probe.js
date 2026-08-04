// /api/daangn-probe.js — 봇 방어 임계점 측정
// GET ?parallel=N&delay=M  → N개 동을 동시(지연 M)로 요청해 빈 응답률 측정
export const config = { maxDuration: 120 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

// 서초구 + 강남구 일부 동 코드 (실측용 고정 목록, 40개)
const DONGS = [
  '서초동-6128','잠원동-367','반포동-6126','방배동-6127','서초3동-365','양재동-6130','서초4동-366',
  '역삼동-6144','논현동-6136','삼성동-6140','청담동-6134','신사동-6135','압구정동-6137','대치동-6142',
  '개포동-6146','도곡동-6143','일원동-6148','수서동-6149','세곡동-6150','논현2동-374','역삼1동-370',
  '천호동-451','성내동-448','길동-455','둔촌동-457','암사동-445','명일동-449','고덕동-452','상일동-453',
  '강일동-6280','방배본동-359','방배4동-361','양재1동-379','내곡동-383','반포본동-352','반포1동-353',
  '잠원동-6129','서초1동-363','서초2동-364','반포4동-357',
];

async function fetchOne(code, q) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q) + '&_=' + Date.now() + Math.random();
  const t0 = Date.now();
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
    const html = await r.text();
    const items = [...new Set([...html.matchAll(/href="(?:https?:\/\/www\.daangn\.com)?\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\//g)])].length;
    // 차단성 빈 페이지는 크기가 작음(~156KB), 정상 검색결과 페이지는 큼(~360KB+)
    // numberOfItems가 명시적으로 0이면 '진짜 결과 없음'
    const numItems = (html.match(/"numberOfItems"\s*:\s*(\d+)/) || [])[1];
    return { code, ms: Date.now() - t0, bytes: html.length, items, numItems: numItems!=null?+numItems:null, empty: items === 0 };
  } catch (e) { return { code, error: String(e.message || e).slice(0, 60), empty: true }; }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  const parallel = Math.min(parseInt(req.query.parallel || '5', 10), 40);
  const delay = parseInt(req.query.delay || '0', 10);
  const q = req.query.q || '의자';  // 실제 매물 있는 키워드
  const codes = DONGS.slice(0, parallel);

  const t0 = Date.now();
  const results = [];
  let idx = 0;
  const workers = Array.from({ length: Math.min(parallel, codes.length) }, async () => {
    while (idx < codes.length) {
      const c = codes[idx++];
      results.push(await fetchOne(c, q));
      if (delay) await new Promise(r => setTimeout(r, delay));
    }
  });
  await Promise.all(workers);

  // 단일 진단 모드
  if (req.query.single === '1') {
    const one = await fetchOne(DONGS[0], q);
    return res.status(200).json({ mode: 'single', q, ...one });
  }
  const empty = results.filter(r => r.empty).length;
  const ok = results.length - empty;
  const avgMs = Math.round(results.reduce((s, r) => s + (r.ms || 0), 0) / results.length);
  return res.status(200).json({
    parallel, delay, requested: codes.length,
    ok, empty, emptyRate: (empty / codes.length * 100).toFixed(0) + '%',
    totalMs: Date.now() - t0, avgMs,
    detail: results.map(r => r.empty ? (r.error ? 'ERR' : `∅${Math.round((r.bytes||0)/1000)}k${r.numItems!=null?'n'+r.numItems:''}`) : r.items).join(' '),
  });
}
