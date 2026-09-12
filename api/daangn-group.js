// /api/daangn-group.js — 당근 모임 검색
export const config = { maxDuration: 60 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const CONCURRENCY = 3, MAX_REGIONS = 45, BLOCK_PAGE_MAX = 220000, MAX_ATTEMPTS = 3;
const BLOCK_RETRY_MS = [1500, 5000];

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();
  const q = (req.query.q || '').trim();
  const debug = req.query.debug === '1';
  const regions = (req.query.regions || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!q) return res.status(400).json({ error: 'q 파라미터 필요' });
  if (!regions.length) return res.status(400).json({ error: 'regions 파라미터 필요' });
  if (regions.length > MAX_REGIONS) return res.status(400).json({ error: `지역은 최대 ${MAX_REGIONS}개` });

  const t0 = Date.now(), results = [], errors = [];
  let snippet = null, idx = 0;
  async function worker() {
    while (idx < regions.length) {
      const region = regions[idx++];
      try {
        const html = await fetchHtml(q, region);
        if (debug && !snippet) {
          const i = html.search(/<a\b[^>]*href="\/kr\/group\/(?!s\/)[^"]+"/);
          snippet = i > 0 ? html.slice(i, i + 1400) : 'anchor-not-found';
        }
        results.push(...parse(html, region));
      } catch (e) {
        errors.push({ region, type: e && e.code ? e.code : 'fetch_error', attempts: e && e.attempts ? e.attempts : 1, lastBytes: e && Number.isFinite(e.lastBytes) ? e.lastBytes : null, error: String(e && (e.message || e) || e).slice(0, 150) });
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, regions.length) }, worker));

  const seen = new Set(), items = [];
  for (const it of results) { if (seen.has(it.url)) continue; seen.add(it.url); items.push(it); }
  const blockedCount = errors.filter(e => e.type === 'blocked_page').length;
  res.setHeader('Cache-Control', 'no-store');
  const out = { query: q, regionCount: regions.length, count: items.length, tookMs: Date.now() - t0, blockedCount, okRegionCount: regions.length - errors.length, errors, items };
  if (debug) out.snippet = snippet;
  return res.status(200).json(out);
}

async function fetchHtml(q, region) {
  const url = 'https://www.daangn.com/kr/group/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q);
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' }, redirect: 'follow' });
    if (!r.ok) {
      if (attempt === MAX_ATTEMPTS - 1) { const e = new Error('HTTP ' + r.status); e.code = 'http_error'; e.attempts = attempt + 1; throw e; }
      await sleep(500 * (attempt + 1)); continue;
    }
    const html = await r.text();
    if (html.length < BLOCK_PAGE_MAX) {
      if (attempt === MAX_ATTEMPTS - 1) { const e = new Error(`차단성 빈 페이지 (${html.length} bytes)`); e.code = 'blocked_page'; e.attempts = attempt + 1; e.lastBytes = html.length; throw e; }
      await sleep(BLOCK_RETRY_MS[attempt] || 5000); continue;
    }
    return html;
  }
  const e = new Error('검색 실패'); e.code = 'fetch_error'; throw e;
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const dec = s => String(s || '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\u0000/g, '');
function parse(html, region) {
  const items = [];
  const re = /<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/group\/(?!s\/)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const path = m[1], inner = m[2];
    const img = inner.match(/<img[^>]*src="([^"]+)"/);
    const parts = inner.replace(/<(script|style)[\s\S]*?<\/\1>/g, '').split(/<\/(?:div|span|p|h\d|li)>/)
      .map(t => t.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim()).filter(Boolean);
    if (!parts.length) continue;
    const title = parts[0]; if (!title || title.length > 80) continue;
    const rest = parts.slice(1), flat = inner.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
    const memMatch = flat.match(/멤버\s*(\d[\d,]*)\s*명?|(\d[\d,]*)\s*명/);
    const members = memMatch ? (memMatch[1] || memMatch[2]) : null;
    const memberTxt = memMatch ? memMatch[0] : null;
    const place = rest.find(t => /(동|읍|면|가|구|시)$/.test(t) && t.length <= 12) || null;
    const desc = rest.find(t => t !== memberTxt && t !== place && t.length > 6) || null;
    items.push({ url: 'https://www.daangn.com' + path, title: dec(title), members: members ? parseInt(members.replace(/,/g, ''), 10) : null, place, desc: desc ? dec(desc).slice(0, 140) : null, thumb: img ? dec(img[1]) : null, region });
  }
  return items;
}
