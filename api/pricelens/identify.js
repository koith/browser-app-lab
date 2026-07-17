// /api/pricelens/identify — 이미지로 제품 식별
// 필요 env: SERPER_KEY, GH_UPLOAD_TOKEN(공개 repo Contents write), GH_UPLOAD_REPO(예: koith/pricelens-tmp), ANTHROPIC_API_KEY(비전 폴백용)

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

async function ghUpload(b64) {
  const repo = process.env.GH_UPLOAD_REPO || 'koith/pricelens-tmp';
  const path = 'tmp/' + Date.now() + '-' + Math.random().toString(36).slice(2, 8) + '.jpg';
  const r = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${process.env.GH_UPLOAD_TOKEN}`,
      'Content-Type': 'application/json',
      'User-Agent': 'pricelens'
    },
    body: JSON.stringify({ message: 'tmp upload', content: b64 })
  });
  if (!r.ok) throw new Error('upload failed ' + r.status);
  const j = await r.json();
  return { rawUrl: j.content.download_url, path, sha: j.content.sha, repo };
}

async function ghDelete(up) {
  try {
    await fetch(`https://api.github.com/repos/${up.repo}/contents/${up.path}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${process.env.GH_UPLOAD_TOKEN}`,
        'Content-Type': 'application/json',
        'User-Agent': 'pricelens'
      },
      body: JSON.stringify({ message: 'tmp cleanup', sha: up.sha })
    });
  } catch (e) { /* 정리 실패는 무시 */ }
}

async function lensSearch(imageUrl) {
  const r = await fetch('https://google.serper.dev/lens', {
    method: 'POST',
    headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: imageUrl, gl: 'kr', hl: 'ko' })
  });
  if (!r.ok) throw new Error('lens failed ' + r.status);
  const j = await r.json();
  const titles = (j.organic || []).map(o => o.title).filter(Boolean);
  // 노이즈 제거: 사이트명 꼬리 자르기, 중복 제거, 너무 짧은 것 제외
  const cleaned = [...new Set(titles.map(t =>
    t.replace(/\s*[-|–:]\s*(쿠팡|11번가|G마켓|옥션|네이버|다나와|번개장터|중고나라|당근|Amazon|eBay|AliExpress).*$/i, '').trim()
  ))].filter(t => t.length >= 6);
  return cleaned;
}

async function visionAnalyze(b64, mime) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-6',
      max_tokens: 400,
      messages: [{
        role: 'user',
        content: [
          { type: 'image', source: { type: 'base64', media_type: mime || 'image/jpeg', data: b64 } },
          { type: 'text', text: '이 사진 속 제품을 식별해서 한국 쇼핑몰 검색용 검색어 후보를 만들어줘. 브랜드/모델명/각인/로고를 최대한 읽고, 확실하지 않으면 "브랜드 미상 + 제품 유형 + 특징" 형태로. JSON만 응답: {"candidates":["가장 구체적인 검색어", "차선 검색어", "일반 검색어"]} 마크다운 금지.' }
        ]
      }]
    })
  });
  if (!r.ok) throw new Error('vision failed ' + r.status);
  const j = await r.json();
  const text = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  const parsed = JSON.parse(text.replace(/```json|```/g, '').trim());
  return parsed.candidates || [];
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64, mime, forceVision } = req.body || {};
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required' });

  try {
    if (!forceVision) {
      const up = await ghUpload(imageBase64);
      try {
        const candidates = await lensSearch(up.rawUrl);
        if (candidates.length >= 2) {
          return res.status(200).json({ source: 'lens', candidates });
        }
      } finally {
        await ghDelete(up); // 프라이버시: 검색 후 즉시 삭제
      }
    }
    // 폴백 또는 강제 비전
    if (!process.env.ANTHROPIC_API_KEY) {
      return res.status(200).json({ source: 'lens', candidates: [], note: 'vision key not set' });
    }
    const candidates = await visionAnalyze(imageBase64, mime);
    return res.status(200).json({ source: 'vision', candidates });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};
