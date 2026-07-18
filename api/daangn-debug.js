export const config = { maxDuration: 40 };
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const H = { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9', Accept: 'text/html' };

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const q = req.query.q || '브루더';

  // 1) /kr/regions/ 에서 서울 구 코드 확보
  const regHtml = await (await fetch('https://www.daangn.com/kr/regions/', { headers: H })).text();
  const codes = new Set();
  for (const m of regHtml.matchAll(/[?&](?:amp;)?in=([^"&#\s]+)/g)) {
    try { const c = decodeURIComponent(m[1]); if (/^[가-힣0-9]+(?:-[가-힣0-9]+)*-\d+$/.test(c)) codes.add(c); } catch {}
  }
  const seoulGu = [...codes].filter(c => /^(종로|중|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|마포|양천|강서|구로|금천|영등포|동작|관악|서초|강남|송파|강동)구-\d+$/.test(c));

  // 2) 코드별로 실제 해석 지역과 결과 수 확인
  const targets = [];
  const seocho = seoulGu.find(c => c.startsWith('서초구'));
  if (seocho) targets.push(seocho);
  targets.push('서초구-362');           // 기존에 쓰던 코드
  const gm = [...codes].find(c => c.startsWith('광명시'));
  if (gm) targets.push(gm);

  const out = [];
  for (const code of targets) {
    const url = 'https://www.daangn.com/kr/buy-sell/?in=' + encodeURIComponent(code) + '&search=' + encodeURIComponent(q);
    const r = await fetch(url, { headers: H });
    const html = await r.text();
    const raw = r.headers.getSetCookie ? r.headers.getSetCookie() : [r.headers.get('set-cookie')].filter(Boolean);
    let resolved = null;
    for (const c of raw) {
      const m = c.match(/search_region=([^;]+)/);
      if (m) { try { resolved = JSON.parse(decodeURIComponent(escape(atob(decodeURIComponent(m[1]))))); } catch { try { resolved = JSON.parse(Buffer.from(decodeURIComponent(m[1]), 'base64').toString('utf8')); } catch {} } }
    }
    const t = html.match(/<title>([^<]*)<\/title>/);
    const n = html.match(/"numberOfItems"\s*:\s*(\d+)/);
    out.push({ code, title: t ? t[1] : '', resolvedRegion: resolved, numberOfItems: n ? +n[1] : null });
  }

  return res.status(200).json({ seoulGuCount: seoulGu.length, seoulGu, out });
}
