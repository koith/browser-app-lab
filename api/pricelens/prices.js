// /api/pricelens/prices — 제품명으로 네이버 + 쿠팡 가격 수집
// 필요 env: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, SERPER_KEY

const ALLOW_ORIGIN = 'https://koith.github.io';
const NOISE = /중고|리퍼|렌탈|해외직구|해외배송|구성품|단품만|부속|호환용/;
const ACC_WORDS = ['케이스', '필름', '거치대', '파우치', '커버'];

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function stripTags(s) { return (s || '').replace(/<[^>]+>/g, ''); }

async function naverSearch(query) {
  const url = 'https://openapi.naver.com/v1/search/shop.json?display=30&sort=sim&query=' + encodeURIComponent(query);
  const r = await fetch(url, {
    headers: {
      'X-Naver-Client-Id': process.env.NAVER_CLIENT_ID,
      'X-Naver-Client-Secret': process.env.NAVER_CLIENT_SECRET
    }
  });
  if (!r.ok) throw new Error('naver failed ' + r.status);
  const j = await r.json();
  let items = (j.items || []).map(it => ({
    title: stripTags(it.title),
    link: it.link,
    lprice: parseInt(it.lprice, 10) || 0,
    mallName: it.mallName,
    productType: parseInt(it.productType, 10),
    productId: it.productId
  }));

  // 쿼리에 액세서리 단어가 없으면 액세서리 결과 제외 (본품 검색 시 케이스/필름 노이즈 차단)
  const accInQuery = ACC_WORDS.some(w => query.includes(w));
  items = items.filter(it => {
    if (NOISE.test(it.title)) return false;
    if (it.productType >= 4) return false; // 중고/렌탈/리퍼 계열
    if (!accInQuery && ACC_WORDS.some(w => it.title.includes(w))) return false;
    return it.lprice > 0;
  });

  // 카탈로그(가격비교 매칭, productType=1) 우선
  const catalog = items.filter(it => it.productType === 1);
  const pool = catalog.length ? catalog : items;

  // 최저가 이상치 제거: 중앙값의 30% 미만은 의심 (구성품/낚시)
  const sorted = [...pool].sort((a, b) => a.lprice - b.lprice);
  const median = sorted[Math.floor(sorted.length / 2)]?.lprice || 0;
  const clean = sorted.filter(it => median === 0 || it.lprice >= median * 0.3);

  // productId 기준 중복 제거 후 최저가순 상위 5개
  const seen = new Set();
  const out = [];
  for (const it of clean) {
    if (seen.has(it.productId)) continue;
    seen.add(it.productId);
    out.push({ ...it, isCatalog: it.productType === 1 });
    if (out.length >= 5) break;
  }
  return out;
}

async function coupangViaSerper(query) {
  const r = await fetch('https://google.serper.dev/search', {
    method: 'POST',
    headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ q: query + ' site:coupang.com', gl: 'kr', hl: 'ko', num: 10 })
  });
  if (!r.ok) throw new Error('serper failed ' + r.status);
  const j = await r.json();
  return (j.organic || [])
    .filter(o => /coupang\.com\/vp\/products/.test(o.link || ''))
    .slice(0, 4)
    .map(o => {
      const m = (o.snippet || '').match(/([0-9][0-9,]{2,})\s*원/);
      return {
        title: (o.title || '').replace(/\s*[-|]\s*쿠팡.*$/, '').trim(),
        link: o.link,
        price: m ? m[1] + '원 (스니펫 기준)' : null
      };
    });
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { query } = req.body || {};
  if (!query || !query.trim()) return res.status(400).json({ error: 'query required' });

  try {
    const [naver, coupang] = await Promise.allSettled([
      naverSearch(query.trim()),
      coupangViaSerper(query.trim())
    ]);
    return res.status(200).json({
      naver: naver.status === 'fulfilled' ? naver.value : [],
      coupang: coupang.status === 'fulfilled' ? coupang.value : [],
      errors: {
        naver: naver.status === 'rejected' ? naver.reason.message : null,
        coupang: coupang.status === 'rejected' ? coupang.reason.message : null
      }
    });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};
