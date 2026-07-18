// /api/daangn-group.js — 당근 모임 검색
// GET /api/daangn-group?q=등산&regions=서초동-6128,...[&debug=1]
export const config = { maxDuration: 60 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const CONCURRENCY = 8, MAX_REGIONS = 45;

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const q = (req.query.q || '').trim();
  const debug = req.query.debug === '1';
  const regions = (req.query.regions || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!q) return res.status(400).json({ error: 'q 파라미터 필요' });
  if (!regions.length) return res.status(400).json({ error: 'regions 파라미터 필요' });
  if (regions.length > MAX_REGIONS) return res.status(400).json({ error: `지역은 최대 ${MAX_REGIONS}개` });

  const t0 = Date.now();
  const results = [], errors = [];
  let snippet = null, idx = 0;

  async function worker() {
    while (idx < regions.length) {
      const region = regions[idx++];
      const url = 'https://www.daangn.com/kr/group/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q);
      try {
        const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' }, redirect: 'follow' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const html = await r.text();
        if (debug && !snippet) {
          const i = html.search(/<a\b[^>]*href="\/kr\/group\/(?!s\/)[^"]+"/);
          snippet = i > 0 ? html.slice(i, i + 1400) : 'anchor-not-found';
        }
        results.push(...parse(html, region));
      } catch (e) { errors.push({ region, error: String(e.message || e).slice(0, 150) }); }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  const seen = new Set(), items = [];
  for (const it of results) { if (seen.has(it.url)) continue; seen.add(it.url); items.push(it); }

  res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=300');
  const out = { query: q, regionCount: regions.length, count: items.length, tookMs: Date.now() - t0, errors, items };
  if (debug) out.snippet = snippet;
  return res.status(200).json(out);
}

function parse(html, region) {
  const items = [];
  const re = /<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/group\/(?!s\/)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const path = m[1], inner = m[2];
    const img = inner.match(/<img[^>]*src="([^"]+)"/);
    // 블록 단위 텍스트 조각 확보
    const parts = inner
      .replace(/<(script|style)[\s\S]*?<\/\1>/g, '')
      .split(/<\/(?:div|span|p|h\d|li)>/)
      .map(t => t.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    if (!parts.length) continue;

    const title = parts[0];
    if (!title || title.length > 80) continue;
    const rest = parts.slice(1);
    const memberTxt = rest.find(t => /멤버|명/.test(t)) || null;
    const members = memberTxt ? (memberTxt.match(/(\d[\d,]*)\s*명/) || [])[1] : null;
    const place = rest.find(t => /(동|읍|면|가|구|시)$/.test(t) && t.length <= 12) || null;
    const desc = rest.find(t => t !== memberTxt && t !== place && t.length > 6) || null;

    items.push({
      url: 'https://www.daangn.com' + path,
      title,
      members: members ? parseInt(members.replace(/,/g, ''), 10) : null,
      place, desc: desc ? desc.slice(0, 120) : null,
      thumb: img ? img[1] : null,
      region,
    });
  }
  return items;
}
