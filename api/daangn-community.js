// /api/daangn-community.js — 당근 동네생활 검색 (JSON-LD 우선)
export const config = { maxDuration: 60 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const CONCURRENCY = 8, MAX_REGIONS = 45;
const dec = s => String(s || '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\u0000/g, '');

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();
  const q = (req.query.q || '').trim();
  const debug = req.query.debug === '1';
  const regions = (req.query.regions || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!q) return res.status(400).json({ error: 'q 파라미터 필요' });
  if (!regions.length) return res.status(400).json({ error: 'regions 파라미터 필요' });
  if (regions.length > MAX_REGIONS) return res.status(400).json({ error: `지역은 최대 ${MAX_REGIONS}개` });

  const t0 = Date.now(); const results = [], errors = []; let idx = 0, ldTypes = null;
  async function worker() {
    while (idx < regions.length) {
      const region = regions[idx++];
      const url = 'https://www.daangn.com/kr/community/?in=' + encodeURIComponent(region) + '&search=' + encodeURIComponent(q);
      try {
        const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' }, redirect: 'follow' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const html = await r.text();
        const { items, types } = parse(html, region);
        if (debug && !ldTypes) ldTypes = types;
        results.push(...items);
      } catch (e) { errors.push({ region, error: String(e.message || e).slice(0, 150) }); }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  const seen = new Set(), items = [];
  for (const it of results) { if (seen.has(it.url)) continue; seen.add(it.url); items.push(it); }
  res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=300');
  const out = { query: q, regionCount: regions.length, count: items.length, tookMs: Date.now() - t0, errors, items };
  if (debug) out.ldTypes = ldTypes;
  return res.status(200).json(out);
}

function parse(html, region) {
  const items = []; const types = [];
  for (const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    let data; try { data = JSON.parse(m[1]); } catch { continue; }
    if (!data || data['@type'] !== 'ItemList' || !Array.isArray(data.itemListElement)) continue;
    for (const e of data.itemListElement) {
      const p = e && e.item; if (!p || !p.url) continue;
      types.push(p['@type']);
      const when = p.datePublished || p.dateCreated || p.dateModified || null;
      const t = when ? Date.parse(when + (/[Z+]/.test(when) ? '' : '+09:00')) : null;
      items.push({
        url: p.url,
        title: dec(p.headline || p.name || '').slice(0, 120),
        desc: dec(p.articleBody || p.text || p.description || '').slice(0, 160) || null,
        thumb: typeof p.image === 'string' ? dec(p.image) : (p.image && p.image.url ? dec(p.image.url) : null),
        author: p.author && p.author.name ? dec(p.author.name) : null,
        sortTime: t || null,
        region,
      });
    }
    break;
  }

  // JSON-LD에 없는 본문/썸네일/동네를 앵커에서 보강
  if (items.length) {
    const extra = {};
    for (const a of html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/community\/(?!s\/)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g)) {
      const url = 'https://www.daangn.com' + a[1];
      const inner = a[2];
      const img = inner.match(/<img[^>]*src="([^"]+)"/);
      const parts = inner
        .replace(/<(script|style)[\s\S]*?<\/\1>/g, '')
        .split(/<\/(?:div|span|p|h\d|li)>/)
        .map(t => dec(t.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim())
        .filter(Boolean);
      if (!parts.length) continue;
      const title = parts[0];
      const body = parts.slice(1).filter(t => t !== title && t.length > 8
        && !/^\d+$/.test(t) && !/(분|시간|일|개월|년)\s*전$/.test(t)
        && !/^(댓글|공감|관심|조회)/.test(t));
      const dong = parts.find(t => /(동|읍|면|가)$/.test(t) && t.length <= 10) || null;
      const prev = extra[url] || {};
      extra[url] = {
        desc: prev.desc || (body.sort((x, y) => y.length - x.length)[0] || null),
        thumb: prev.thumb || (img ? dec(img[1]) : null),
        dong: prev.dong || dong,
      };
    }
    for (const it of items) {
      const e = extra[it.url];
      if (!e) continue;
      if (!it.desc && e.desc) it.desc = e.desc.slice(0, 160);
      if (!it.thumb && e.thumb) it.thumb = e.thumb;
      if (e.dong) it.dong = e.dong;
    }
  }

  if (!items.length) {
    for (const a of html.matchAll(/<a\b[^>]*href="(?:https?:\/\/www\.daangn\.com)?(\/kr\/community\/(?!s\/)[^"?#]+\/)"[^>]*>([\s\S]*?)<\/a>/g)) {
      const parts = a[2].split(/<\/(?:div|span|p|h\d)>/).map(t => dec(t.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim()).filter(Boolean);
      if (!parts.length || parts[0].length > 120) continue;
      items.push({ url: 'https://www.daangn.com' + a[1], title: parts[0], desc: parts[1] || null, thumb: null, author: null, sortTime: null, region });
    }
  }
  return { items, types: [...new Set(types)] };
}
