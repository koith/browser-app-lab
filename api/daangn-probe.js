// /api/daangn-probe.js — 세션당 '서로 다른 지역 수' 임계점 측정
// 서로 다른 동을 순차로 1개씩 조회하며, 몇 번째부터 빈 페이지가 시작되는지 확인
export const config = { maxDuration: 300 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

// 서로 다른 동 60개 (검증된 유효 코드 위주 + 확장)
const DONGS = [
  '서초동-6128','잠원동-367','반포동-6126','방배동-6127','서초3동-365','양재동-6130','서초4동-366',
  '역삼동-6035','논현동-6031','삼성동-6034','청담동-386','신사동-382','압구정동-385','대치동-6032',
  '개포동-6030','도곡동-6033','일원동-6037','수서동-403','세곡동-399','논현2동-384','역삼1동-392',
  '천호동-451','성내동-448','길동-455','둔촌동-457','암사동-445','명일동-449','고덕동-452','상일동-453',
  '방배본동-359','방배4동-361','양재1동-379','내곡동-383','반포본동-352','반포1동-353','서초1동-363',
  '서초2동-364','반포4동-357','역삼2동-393','논현1동-383','대치1동-389','자곡동-6038','삼성2동-388',
  '대치4동-391','삼성1동-387','개포4동-398','개포1동-396','도곡1동-394','대치2동-390','개포2동-397',
  '개포3동-402','도곡2동-395','일원본동-400','일원1동-401','율현동-6036','신원동-6039','우면동-6131',
  '양재2동-380','서초본동-6132','반포2동-354',
];

async function fetchOne(code, q) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q);
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' } });
    const html = await r.text();
    const items = [...new Set([...html.matchAll(/href="(?:https?:\/\/www\.daangn\.com)?\/kr\/buy-sell\/(?!s\/)(?!\?)[^"?#]+\//g)])].length;
    return items === 0 ? 0 : items;
  } catch { return -1; }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  const q = req.query.q || '브루더';
  const n = Math.min(parseInt(req.query.n || '40', 10), DONGS.length);
  const chunk = parseInt(req.query.chunk || '0', 10);
  const pause = parseInt(req.query.pause || '0', 10);

  const seq = [];
  let firstEmptyAt = null;
  for (let i = 0; i < n; i++) {
    const items = await fetchOne(DONGS[i], q);
    seq.push(items);
    if (items === 0 && firstEmptyAt === null) firstEmptyAt = i + 1;
    if (chunk && pause && (i + 1) % chunk === 0) await new Promise(r => setTimeout(r, pause));
  }
  const emptyCount = seq.filter(x => x === 0).length;
  return res.status(200).json({
    q, delay, tested: n,
    firstEmptyAt,                       // 몇 번째 지역부터 빈 페이지 시작?
    emptyCount,
    emptyRate: (emptyCount / n * 100).toFixed(0) + '%',
    seq: seq.map(x => x === 0 ? '∅' : x === -1 ? 'E' : x).join(' '),
  });
}
