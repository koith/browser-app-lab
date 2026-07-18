// /api/daangn-dongs.js — 구/시 이름으로 소속 동 목록 조회
// GET /api/daangn-dongs?gu=서초구&province=서울특별시
export const config = { maxDuration: 20 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const gu = (req.query.gu || '').trim();          // "서초구" 또는 "수원시 권선구"
  const province = (req.query.province || '').trim();
  if (!gu) return res.status(400).json({ error: 'gu 파라미터 필요' });

  const parts = gu.split(/\s+/);
  const leaf = parts[parts.length - 1];            // 권선구 / 서초구
  const kw = parts.length > 1 ? parts.join(' ') : gu;

  let data;
  try {
    const r = await fetch('https://www.daangn.com/kr/api/v1/regions/keyword?keyword=' + encodeURIComponent(kw), {
      headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9',
        Accept: 'application/json', Referer: 'https://www.daangn.com/kr/buy-sell/' },
    });
    if (!r.ok) return res.status(502).json({ error: `daangn HTTP ${r.status}` });
    data = await r.json();
  } catch (e) {
    return res.status(502).json({ error: String(e.message || e).slice(0, 150) });
  }

  const locs = Array.isArray(data.locations) ? data.locations : [];
  const list = locs
    .filter(l => l.depth === 3 && l.name3 && l.id)
    .filter(l => !province || l.name1 === province)
    .filter(l => (l.name2 || '').includes(leaf) || (parts.length > 1 && (l.name2 || '').includes(parts[0])))
    .map(l => ({ code: `${l.name3}-${l.id}`, dong: l.name3, gu: l.name2, province: l.name1 }));

  // 중복 제거
  const seen = new Set();
  const uniq = list.filter(x => (seen.has(x.code) ? false : (seen.add(x.code), true)));

  res.setHeader('Cache-Control', 's-maxage=604800, stale-while-revalidate=604800');
  return res.status(200).json({ gu, count: uniq.length, list: uniq });
}
