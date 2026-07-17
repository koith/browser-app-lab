// /api/pricelens/identify — 이미지로 상품 매치(이미지+판매링크) 순위화
// 필수 env: SERPER_KEY

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

async function litterboxUpload(b64) {
  const buf = Buffer.from(b64, 'base64');
  const fd = new FormData();
  fd.append('reqtype', 'fileupload');
  fd.append('time', '1h');
  fd.append('fileToUpload', new Blob([buf], { type: 'image/jpeg' }), 'p.jpg');
  const r = await fetch('https://litterbox.catbox.moe/resources/internals/api.php', { method: 'POST', body: fd });
  const text = (await r.text()).trim();
  if (!r.ok || !text.startsWith('http')) throw new Error('upload: ' + text.slice(0, 80));
  return text;
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
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64 } = req.body || {};
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required', step: 'input' });
  if (!process.env.SERPER_KEY) return res.status(500).json({ error: 'SERPER_KEY 미설정', step: 'config' });

  let step = 'upload';
  try {
    const imageUrl = await litterboxUpload(imageBase64);
    step = 'lens';
    const r = await fetch('https://google.serper.dev/lens', {
      method: 'POST',
      headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: imageUrl, gl: 'kr', hl: 'ko' })
    });
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
