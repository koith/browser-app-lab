// /api/pricelens/identify — 이미지로 제품 식별
// 필수 env: SERPER_KEY (기존 보유)
// 선택 env: ANTHROPIC_API_KEY (비전 폴백), GH_UPLOAD_TOKEN + GH_UPLOAD_REPO (litterbox 장애 시 폴백)

const ALLOW_ORIGIN = 'https://koith.github.io';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

// 1순위: litterbox 익명 업로드 (1시간 후 자동 삭제 — 별도 계정/토큰 불필요)
async function litterboxUpload(b64) {
  const buf = Buffer.from(b64, 'base64');
  const fd = new FormData();
  fd.append('reqtype', 'fileupload');
  fd.append('time', '1h');
  fd.append('fileToUpload', new Blob([buf], { type: 'image/jpeg' }), 'p.jpg');
  const r = await fetch('https://litterbox.catbox.moe/resources/internals/api.php', {
    method: 'POST', body: fd
  });
  const text = (await r.text()).trim();
  if (!r.ok || !text.startsWith('http')) throw new Error('litterbox: ' + text.slice(0, 80));
  return { rawUrl: text, cleanup: null };
}

// 2순위: GitHub 임시 repo (환경변수 설정된 경우만)
async function ghUpload(b64) {
  const repo = process.env.GH_UPLOAD_REPO || 'koith/pricelens-tmp';
  const path = 'tmp/' + Date.now() + '-' + Math.random().toString(36).slice(2, 8) + '.jpg';
  const hdrs = {
    Authorization: `Bearer ${process.env.GH_UPLOAD_TOKEN}`,
    'Content-Type': 'application/json', 'User-Agent': 'pricelens'
  };
  const r = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
    method: 'PUT', headers: hdrs,
    body: JSON.stringify({ message: 'tmp', content: b64 })
  });
  if (!r.ok) throw new Error('gh upload: ' + r.status);
  const j = await r.json();
  return {
    rawUrl: j.content.download_url,
    cleanup: () => fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
      method: 'DELETE', headers: hdrs,
      body: JSON.stringify({ message: 'cleanup', sha: j.content.sha })
    }).catch(() => {})
  };
}

async function uploadImage(b64) {
  try { return await litterboxUpload(b64); }
  catch (e) {
    if (process.env.GH_UPLOAD_TOKEN) return await ghUpload(b64);
    throw e;
  }
}

async function lensSearch(imageUrl) {
  const r = await fetch('https://google.serper.dev/lens', {
    method: 'POST',
    headers: { 'X-API-KEY': process.env.SERPER_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: imageUrl, gl: 'kr', hl: 'ko' })
  });
  if (!r.ok) throw new Error('lens: ' + r.status + ' ' + (await r.text()).slice(0, 80));
  const j = await r.json();
  const rawTitles = (j.organic || []).map(o => o.title).filter(Boolean);
  if (j.knowledgeGraph && j.knowledgeGraph.title) rawTitles.unshift(j.knowledgeGraph.title);
  return await buildCandidates(rawTitles);
}

// 커뮤니티 게시글 제목 등 노이즈에서 제품명 후보를 만든다
const SITE_TAIL = /\s*[-|:\u2013]\s*(쿠팡|11번가|G마켓|옥션|네이버\S*|다나와|번개장터|중고나라|당근\S*|더쿠\S*|뽐뿌\S*|클리앙\S*|루리웹\S*|에펨코리아\S*|인벤\S*|디시\S*|자유게시판|블로그|티스토리|브런치|인스타\S*|유튜브|Amazon|eBay|AliExpress|YouTube).*$/i;
const SITE_HEAD = /^(더쿠|뽐뿌|클리앙|루리웹|에펨코리아|디시인사이드|인벤)\s*[-|:\u2013]\s*/;
// 판매처는 제품명이 아니다 — 검색어에 들어가면 카탈로그 매칭을 방해
const RETAILER = new Set(['다이소','올리브영','올영','이마트','코스트코','홈플러스','롯데마트','편의점','GS25','CU','세븐일레븐','무인양품']);
const REVIEWISH = /리뷰|후기|추천|비교|사용기|사용\s?후기|내돈내산|언박싱|신상|발림|성분|근황|난리/;
const STOPWORD = new Set(['현재','근황','리뷰','후기','추천','추천템','추천드려요','신상','신상템','사용','사용중','잘','쓰는','중','난리났다는','이렇게','아무튼','하나만','골라보자','내돈내산','정보','공유','이것','이겁니다','최강자','화장품','비교','JPG','PNG','GIF','jpg','png']);

function cleanTitle(t) {
  let s = t.replace(/\.(jpe?g|png|gif|webp)/ig, ' ');
  s = s.replace(SITE_TAIL, '').replace(SITE_HEAD, '');
  s = s.replace(/["'「」''\[\]()·,]/g, ' ').replace(/\s+/g, ' ').trim();
  return s;
}

function looksLikeSentence(s) {
  return /습니다|해요|어요|드려요|주세요|았|했|입니다|봤고|사왔|[?!]|쓰는 중|사용 중/.test(s) || s.length > 38;
}

function heuristicCandidates(rawTitles) {
  const cleaned = rawTitles.map(cleanTitle).filter(s => s.length >= 6);
  const count = new Map(), firstPos = new Map();
  cleaned.forEach(s => {
    const seen = new Set();
    s.split(' ').forEach((tok, i) => {
      if (tok.length < 2 || STOPWORD.has(tok) || RETAILER.has(tok) || seen.has(tok)) return;
      seen.add(tok);
      count.set(tok, (count.get(tok) || 0) + 1);
      if (!firstPos.has(tok)) firstPos.set(tok, i);
    });
  });
  const top = [...count.entries()]
    .filter(([, c]) => c >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([tok]) => tok)
    .sort((a, b) => firstPos.get(a) - firstPos.get(b));
  const synthesized = top.length >= 2 ? top.join(' ') : null;

  // 칩에는 제품명처럼 보이는 것만: 리뷰성 단어 포함 시 제외
  const titleCands = [...new Set(cleaned.filter(s => !looksLikeSentence(s) && !REVIEWISH.test(s)))];
  const out = [];
  if (synthesized) out.push(synthesized);
  titleCands.forEach(s => { if (!out.includes(s)) out.push(s); });
  return out.slice(0, 4);
}

// ANTHROPIC_API_KEY가 있으면 저비용 텍스트 모델로 제목들에서 실제 제품명을 증류
async function distillWithHaiku(rawTitles) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5', max_tokens: 300,
      messages: [{ role: 'user', content:
        '아래는 상품 사진을 이미지 검색한 결과 페이지 제목들이다. 이 제목들이 공통으로 가리키는 실제 제품을 추정해, 한국 쇼핑몰 검색용 검색어 후보를 만들어라.\n' +
        '규칙: 브랜드+제품명(+용량) 형태. 다이소/올리브영 같은 판매처 이름 금지. 리뷰/후기/추천 같은 단어 금지. 확신 높은 순서로 최대 3개.\n' +
        'JSON만 응답: {"candidates":["...","..."]} 마크다운 금지.\n\n' +
        rawTitles.slice(0, 10).map((t, i) => (i + 1) + '. ' + t).join('\n')
      }]
    })
  });
  if (!r.ok) throw new Error('distill: ' + r.status);
  const j = await r.json();
  const text = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  const cands = JSON.parse(text.replace(/```json|```/g, '').trim()).candidates || [];
  return cands.filter(c => typeof c === 'string' && c.length >= 4);
}

async function buildCandidates(rawTitles) {
  const heuristic = heuristicCandidates(rawTitles);
  if (!process.env.ANTHROPIC_API_KEY) return heuristic;
  try {
    const distilled = await distillWithHaiku(rawTitles);
    if (distilled.length) {
      // 증류 결과 우선, 휴리스틱 후보로 보강
      const out = [...distilled];
      heuristic.forEach(h => { if (!out.includes(h)) out.push(h); });
      return out.slice(0, 5);
    }
  } catch (e) { /* 증류 실패 시 휴리스틱으로 */ }
  return heuristic;
}

async function visionAnalyze(b64, mime) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-6', max_tokens: 400,
      messages: [{ role: 'user', content: [
        { type: 'image', source: { type: 'base64', media_type: mime || 'image/jpeg', data: b64 } },
        { type: 'text', text: '이 사진 속 제품을 식별해서 한국 쇼핑몰 검색용 검색어 후보를 만들어줘. 브랜드/모델명/각인/로고를 최대한 읽고, 확실하지 않으면 "브랜드 미상 + 제품 유형 + 특징" 형태로. JSON만 응답: {"candidates":["가장 구체적인 검색어","차선 검색어","일반 검색어"]} 마크다운 금지.' }
      ]}]
    })
  });
  if (!r.ok) throw new Error('vision: ' + r.status);
  const j = await r.json();
  const text = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  return JSON.parse(text.replace(/```json|```/g, '').trim()).candidates || [];
}

module.exports = async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64, mime, forceVision } = req.body || {};
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required', step: 'input' });
  if (!process.env.SERPER_KEY) return res.status(500).json({ error: 'SERPER_KEY 미설정', step: 'config' });

  let step = 'init';
  try {
    if (!forceVision) {
      step = 'upload';
      const up = await uploadImage(imageBase64);
      try {
        step = 'lens';
        const candidates = await lensSearch(up.rawUrl);
        if (candidates.length >= 2) return res.status(200).json({ source: 'lens', candidates });
      } finally {
        if (up.cleanup) await up.cleanup();
      }
    }
    step = 'vision';
    if (!process.env.ANTHROPIC_API_KEY) {
      return res.status(200).json({ source: 'lens', candidates: [], note: 'ANTHROPIC_API_KEY 미설정 — AI 폴백 비활성' });
    }
    const candidates = await visionAnalyze(imageBase64, mime);
    return res.status(200).json({ source: 'vision', candidates });
  } catch (e) {
    return res.status(500).json({ error: e.message, step });
  }
};
