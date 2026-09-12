// /api/daangn-probe.js — distinct-region threshold/reset diagnostics
// GET /api/daangn-probe?q=아이폰&n=40&chunk=3&pause=2500
export const config = { maxDuration: 300 };

const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const BLOCK_PAGE_MAX = 220000;

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

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function fetchOne(code, q) {
  const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q);
  const started = Date.now();
  try {
    const r = await fetch(url, {
      headers: {
        'User-Agent': UA,
        'Accept-Language': 'ko-KR,ko;q=0.9',
        Accept: 'text/html',
      },
      redirect: 'follow',
    });
    const html = await r.text();
    const blocked = r.ok && html.length < BLOCK_PAGE_MAX;
    const hasItemList = /<script type="application\/ld\+json">[\s\S]*?"@type"\s*:\s*"ItemList"/.test(html);
    return {
      code,
      http: r.status,
      bytes: html.length,
      blocked,
      hasItemList,
      ms: Date.now() - started,
    };
  } catch (e) {
    return {
      code,
      http: null,
      bytes: 0,
      blocked: false,
      hasItemList: false,
      ms: Date.now() - started,
      error: String(e && (e.message || e) || 'fetch error').slice(0, 160),
    };
  }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');

  const q = String(req.query.q || '아이폰').trim();
  const n = Math.max(1, Math.min(parseInt(req.query.n || '40', 10) || 40, DONGS.length));
  const chunk = Math.max(0, parseInt(req.query.chunk || '0', 10) || 0);
  const pause = Math.max(0, Math.min(parseInt(req.query.pause || '0', 10) || 0, 30000));
  const startAt = Math.max(0, Math.min(parseInt(req.query.start || '0', 10) || 0, DONGS.length - 1));
  const selected = DONGS.slice(startAt, Math.min(startAt + n, DONGS.length));

  const t0 = Date.now();
  const seq = [];
  let firstBlockedAt = null;

  for (let i = 0; i < selected.length; i++) {
    const r = await fetchOne(selected[i], q);
    seq.push(r);
    if (r.blocked && firstBlockedAt === null) firstBlockedAt = i + 1;
    if (chunk && pause && (i + 1) % chunk === 0 && i + 1 < selected.length) await sleep(pause);
  }

  const blockedCount = seq.filter(x => x.blocked).length;
  const httpErrors = seq.filter(x => x.error || (x.http != null && (x.http < 200 || x.http >= 300))).length;
  return res.status(200).json({
    query: q,
    requested: n,
    tested: seq.length,
    startAt,
    chunk,
    pauseMs: pause,
    tookMs: Date.now() - t0,
    firstBlockedAt,
    blockedCount,
    blockedRate: seq.length ? Math.round(blockedCount / seq.length * 100) : 0,
    httpErrors,
    classification: 'blocked means HTTP 2xx with HTML smaller than 220000 bytes; zero search results are not treated as blocked',
    seq,
  });
}
