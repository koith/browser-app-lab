// /api/daangn-regions.js — 지역 코드 수집기 (1회성)
// GET /api/daangn-regions?seed=서초4동-366[&debug=1]
// 일반 페이지(주변 동 링크) + 검색 페이지 /s/ (구/시 breadcrumb)를 모두 읽어 링크 통합

export const config = { maxDuration: 30 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const seed = (req.query.seed || '').trim();
  const debug = req.query.debug === '1';
  if (!seed && !req.query.probe) return res.status(400).json({ error: 'seed 또는 probe 파라미터 필요' });


  // ID 단독 조회 가능 여부 프로브: ?probe=362,363,364
  const probe = (req.query.probe || '').trim();
  if (probe) {
    const ids = probe.split(',').map(x=>x.trim()).filter(Boolean).slice(0,20);
    const out = [];
    for (const id of ids) {
      for (const form of ['x-'+id, id]) {
        try {
          const r = await fetch('https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(form), {
            headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' }, redirect: 'follow' });
          const h = await r.text();
          const t = h.match(/<title>([^<]*)<\/title>/);
          out.push({ id, form, status: r.status, finalUrl: r.url, title: t ? t[1].slice(0,80) : '' });
        } catch (e) { out.push({ id, form, error: String(e.message||e).slice(0,80) }); }
      }
    }
    return res.status(200).json({ probe: out });
  }

  const inQ = encodeURIComponent(seed);
  const urls = [
    'https://www.daangn.com/kr/buy-sell/?in=' + inQ,
    'https://www.daangn.com/kr/buy-sell/s/?in=' + inQ + '&search=' + encodeURIComponent('의자'),
  ];

  let pageRegion = '';
  const links = new Map();
  const perUrl = [];
  const fails = [];

  for (const url of urls) {
    let html;
    try {
      const r = await fetch(url, {
        headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' },
        redirect: 'follow',
      });
      if (!r.ok) { fails.push(`${url}: HTTP ${r.status}`); continue; }
      html = await r.text();
    } catch (e) {
      fails.push(`${url}: ${String(e.message || e).slice(0, 100)}`);
      continue;
    }

    if (!pageRegion) {
      const t = html.match(/<title>([^<]*)<\/title>/);
      if (t) pageRegion = t[1].replace(/중고거래.*$/, '').trim();
    }

    const local = [];
    const linkRe = /[?&](?:amp;)?in=([^"&#\s]+)/g;
    let m;
    while ((m = linkRe.exec(html)) !== null) {
      let code;
      try { code = decodeURIComponent(m[1]); } catch { continue; }
      if (/^[가-힣0-9]+-\d+$/.test(code)) { links.set(code, true); local.push(code); }
    }
    if (debug) perUrl.push({ url, bytes: html.length, found: [...new Set(local)] });
  }

  if (!pageRegion && fails.length === urls.length)
    return res.status(502).json({ error: 'daangn fetch 실패', fails });

  const out = { seed, pageRegion, links: [...links.keys()], fails };
  if (debug) out.perUrl = perUrl;
  return res.status(200).json(out);
}
