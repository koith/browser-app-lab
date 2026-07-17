// /api/pricelens/identify — 이미지로 상품 매치(이미지+판매링크) 순위화
// 필수 env: SERPER_KEY

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

async function fetchT(url, opts, ms) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try { return await fetch(url, { ...opts, signal: ctrl.signal }); }
  finally { clearTimeout(t); }
}

// 업로드 호스트 다중화: 하나가 죽어도 다음으로 (둘 다 1시간 내 자동 삭제/만료)
async function upLitterbox(buf) {
  const fd = new FormData();
  fd.append('reqtype', 'fileupload');
  fd.append('time', '1h');
  fd.append('fileToUpload', new Blob([buf], { type: 'image/jpeg' }), 'p.jpg');
  const r = await fetchT('https://litterbox.catbox.moe/resources/internals/api.php', { method: 'POST', body: fd }, 8000);
  const text = (await r.text()).trim();
  if (!r.ok || !text.startsWith('http')) throw new Error('litterbox: ' + text.slice(0, 60));
  return text;
}

async function upTmpfiles(buf) {
  const fd = new FormData();
  fd.append('file', new Blob([buf], { type: 'image/jpeg' }), 'p.jpg');
  const r = await fetchT('https://tmpfiles.org/api/v1/upload', { method: 'POST', body: fd }, 8000);
  if (!r.ok) throw new Error('tmpfiles: ' + r.status);
  const j = await r.json();
  const url = j && j.data && j.data.url;
  if (!url) throw new Error('tmpfiles: no url');
  return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/'); // 직접 다운로드 URL
}

async function uploadImage(b64) {
  const buf = Buffer.from(b64, 'base64');
  const errors = [];
  for (const up of [upLitterbox, upTmpfiles]) {
    try { return await up(buf); }
    catch (e) { errors.push(e.message); }
  }
  throw new Error('업로드 전체 실패: ' + errors.join(' / '));
}

const SHOP_RANK = [
  { re: /coupang\.com\/(vp\/products|products)/i, w: 100, name: '쿠팡' },
  { re: /smartstore\.naver\.com|brand\.naver\.com/i, w: 92, name: '네이버 스토어' },
  { re: /search\.shopping\.naver\.com\/catalog/i, w: 90, name: '네이버 가격비교' },
  { re: /ssg\.com|11st\.co\.kr|gmarket\.co\.kr|auction\.co\.kr|lotteon\.com/i, w: 82, name: '오픈마켓' },
  { re: /oliveyoung\.co\.kr|musinsa\.com|kurly\.com/i, w: 80, name: '전문몰' },
];

function siteTail(t) {
  return (t || '').replace(/\s*[-|:\u2013]\s*(쿠팡!?|11번가|G마켓|옥션|SSG.*|네이버.*|올리브영.*|무신사.*|마켓컬리.*|다나와|Coupang).*$/i, '').trim();
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method === 'GET') {
    // 진단: 사파리 주소창에서 .../identify?diag=1 로 접속
    const diag = { serperKey: !!process.env.SERPER_KEY, hosts: {} };
    const tiny = Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q==', 'base64');
    for (const [name, up] of [['litterbox', upLitterbox], ['tmpfiles', upTmpfiles]]) {
      const t0 = Date.now();
      try { const u = await up(tiny); diag.hosts[name] = { ok: true, ms: Date.now() - t0, url: u.slice(0, 50) }; }
      catch (e) { diag.hosts[name] = { ok: false, ms: Date.now() - t0, error: e.message }; }
    }
    return res.status(200).json(diag);
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64 } = req.body || {};
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required', step: 'input' });
  if (!process.env.SERPER_KEY) return res.status(500).json({ error: 'SERPER_KEY 미설정', step: 'config' });

  let step = 'upload';
  try {
    const imageUrl = await uploadImage(imageBase64);
    step = 'lens';
    const r = await fetchT('https://google.serper.dev/lens', {
      method: 'POST',
      headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: imageUrl, gl: 'kr', hl: 'ko' })
    }, 12000);
    if (!r.ok) throw new Error('lens: ' + r.status);
    const j = await r.json();

    const matches = (j.organic || [])
      .map(o => {
        const link = o.link || '';
        const shop = SHOP_RANK.find(s => s.re.test(link));
        const image = o.imageUrl || o.thumbnailUrl || o.thumbnail || null;
        let score = (shop ? shop.w : 10) + (image ? 15 : 0);
        return {
          title: siteTail(o.title),
          link,
          image,
          source: shop ? shop.name : (o.source || ''),
          isShop: !!shop,
          score
        };
      })
      .filter(m => m.title && m.link && m.image) // 이미지 없는 매치는 확인 UX가 성립 안 함
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map(({ score, ...m }) => m);

    return res.status(200).json({ matches });
  } catch (e) {
    return res.status(500).json({ error: e.message, step });
  }
};
