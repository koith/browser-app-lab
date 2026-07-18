// /api/pricelens/prices — 최저가 자동 선정
// 1순위: Serper Google Shopping(구조화 가격) → 용량/묶음 조건 필터 → 최저액
// 폴백: 네이버 카탈로그 / 쿠팡 링크
// 필수 env: SERPER_KEY

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(label + ': timeout')), ms))
  ]);
}

async function serper(endpoint, q, ms) {
  const r = await withTimeout(fetch('https://google.serper.dev/' + endpoint, {
    method: 'POST',
    headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, gl: 'kr', hl: 'ko', num: 20 })
  }), ms, endpoint);
  if (!r.ok) throw new Error(endpoint + ': ' + r.status);
  return r.json();
}

const VOL_RE = /(\d+(?:\.\d+)?)\s*(ml|l|g|kg|매|정|캡슐|포|환)\b/gi;
const PACK_RE = /(\d+\s*(개|팩|묶음|박스|입))|세트|더블|1\s*\+\s*1|2\s*\+\s*1/i;
const VARIANT_RE = /리필|대용량|미니|휴대용|증정|기획/;

function norm(s) { return (s || '').toLowerCase().replace(/\s+/g, ''); }

function volumes(s) {
  const out = [];
  let m; const re = new RegExp(VOL_RE.source, 'gi');
  while ((m = re.exec(s || ''))) out.push((m[1] + m[2]).toLowerCase());
  return out;
}

function priceNum(s) {
  const m = (s || '').replace(/[₩,\s]/g, '').match(/(\d{3,})/);
  return m ? parseInt(m[1], 10) : null;
}

// 배송 문구 → 배송비. 무료면 0, 금액이 있으면 그 값, 알 수 없으면 null
function shipNum(s) {
  const t = (s || '').replace(/\s/g, '');
  if (!t) return null;
  if (/무료배송|무료|free/i.test(t)) return 0;
  const m = t.replace(/[₩,]/g, '').match(/(\d{3,})/);
  return m ? parseInt(m[1], 10) : null;
}

// 쿼리 정제: 묶음/사은품/옵션 꼬리 제거 (용량은 보존 — 매칭 조건으로 사용)
function sanitize(q) {
  return q.split(',')[0]
    .replace(/[\[\(][^\]\)]*[\]\)]/g, ' ')
    .replace(/\+\S+/g, ' ')
    .replace(/\b\d+\s*(개|팩|묶음|박스|입|세트)\b/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function acceptable(title, q) {
  const t = norm(title);
  const qVols = volumes(q);
  if (qVols.length && !qVols.some(v => t.includes(v))) return false; // 용량 불일치 제외
  if (!PACK_RE.test(q) && PACK_RE.test(title)) return false;         // 쿼리에 없는 묶음 제외
  for (const w of ['리필', '대용량', '미니', '휴대용']) {              // 변형 상품 제외
    if (!q.includes(w) && title.includes(w)) return false;
  }
  return true;
}

async function shoppingBest(q) {
  const j = await serper('shopping', q, 6000);
  const items = (j.shopping || j.shopping_results || [])
    .map(o => ({
      title: o.title || '',
      link: o.link || '',
      source: o.source || '',
      price: o.price || '',
      n: priceNum(o.price),
      delivery: o.delivery || ''
    }))
    .filter(it => it.title && it.link && it.n && it.n >= 100)
    .filter(it => !/품절|sold\s?out/i.test(it.title))
    .filter(it => acceptable(it.title, q))
    .map(it => {
      const ship = shipNum(it.delivery);
      return { ...it, ship, total: it.n + (ship === null ? 3000 : ship) }; // 배송비 미상은 3000원으로 보수적 가정
    })
    .sort((a, b) => a.total - b.total); // 배송비 포함 총액 기준
  return items;
}

async function fallbackPool(q) {
  const j = await serper('search', q + ' site:search.shopping.naver.com', 6000);
  const cat = (j.organic || []).find(o => /search\.shopping\.naver\.com\/catalog\//.test(o.link || '') && acceptable(o.title || '', q));
  if (cat) return { title: cat.title, link: cat.link, price: null, source: '네이버 가격비교' };
  const c = await serper('search', q + ' site:coupang.com', 6000);
  const cp = (c.organic || []).find(o => /coupang\.com\/vp\/products/.test(o.link || '') && acceptable(o.title || '', q));
  if (cp) return { title: cp.title, link: cp.link, price: null, source: '쿠팡' };
  return null;
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  let { query } = req.body || {};
  if (!query || !query.trim()) return res.status(400).json({ error: 'query required', step: 'input' });
  if (!process.env.SERPER_KEY) return res.status(500).json({ error: 'SERPER_KEY 미설정', step: 'config' });
  const q = sanitize(query);

  try {
    let best = null, alts = [];
    try {
      const items = await shoppingBest(q);
      const fmt = it => {
        const base = it.n.toLocaleString('ko-KR') + '원';
        if (it.ship === 0) return base + ' · 무료배송';
        if (it.ship) return base + ' + 배송 ' + it.ship.toLocaleString('ko-KR') + '원';
        return base + ' · 배송비 별도';
      };
      if (items.length) {
        const b = items[0];
        best = { title: b.title, link: b.link, source: b.source, price: fmt(b), total: b.total };
        alts = items.slice(1, 5).map(it => ({ title: it.title, link: it.link, source: it.source, price: fmt(it), total: it.total }));
      }
    } catch (e) { /* shopping 실패 시 폴백 */ }

    if (!best) best = await fallbackPool(q);
    return res.status(200).json({ best, alts, query: q });
  } catch (e) {
    return res.status(500).json({ error: e.message, step: 'search' });
  }
};
