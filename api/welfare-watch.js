/**
 * 지원사업 출처 페이지 변경 감시
 * GET /api/welfare-watch
 *
 * 각 사업의 출처 URL을 가져와 본문 해시를 계산하고,
 * 저장된 해시와 다르면 "바뀌었다"고 보고한다.
 *
 * 자동으로 할 수 있는 것: 페이지가 바뀌었는지 감지
 * 자동으로 할 수 없는 것: 바뀐 요건을 규칙 트리로 변환 (사람 판단 필요)
 *
 * 환경변수: GH_TOKEN (koith/browser-app-lab Contents read/write)
 */

const crypto = require('crypto');

const REPO = 'koith/browser-app-lab';
const DATA_PATH = 'apps/SeniorWelfare/programs-live.json';
const STATE_PATH = 'apps/SeniorWelfare/watch-state.json';

// 감시 대상 — 사업 id와 출처 URL
const SOURCES = {
  'basic-pension':  'https://www.mohw.go.kr/menu.es?mid=a10503010100',
  'ltc-apply':      'https://www.longtermcare.or.kr/npbs/e/b/201/npeb201t02.web',
  'job-public':     'https://www.ydp.go.kr/www/contents.do?key=5720',
  'job-service':    'https://www.ydp.go.kr/www/contents.do?key=5720',
  'job-market':     'https://www.ydp.go.kr/www/contents.do?key=5720',
  'care-custom':    'https://www.silverwelfare.or.kr/',
  'care-ltc':       'https://www.ydp.go.kr/www/contents.do?key=3824',
  'counsel':        'https://www.ydp.go.kr/www/contents.do?key=3809',
};

// 구청 서버가 기본 UA를 막으므로 브라우저처럼 요청
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) ' +
           'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1';

async function fetchText(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': UA,
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'ko-KR,ko;q=0.9',
    },
  });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return await res.text();
}

// 본문만 남기고 해시 — 광고·날짜·세션ID 때문에 오탐이 나지 않도록 정규화
function fingerprint(html) {
  const text = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\d{4}[-.]\d{1,2}[-.]\d{1,2}/g, '')   // 날짜 제거
    .replace(/\s+/g, ' ')
    .trim();
  return {
    hash: crypto.createHash('sha256').update(text).digest('hex').slice(0, 16),
    length: text.length,
  };
}

async function ghGet(path) {
  const res = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
    headers: {
      Authorization: `Bearer ${process.env.GH_TOKEN}`,
      Accept: 'application/vnd.github+json',
    },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('GitHub GET ' + res.status);
  const j = await res.json();
  return { sha: j.sha, data: JSON.parse(Buffer.from(j.content, 'base64').toString('utf8')) };
}

async function ghPut(path, obj, sha, message) {
  const body = {
    message,
    content: Buffer.from(JSON.stringify(obj, null, 2), 'utf8').toString('base64'),
  };
  if (sha) body.sha = sha;
  const res = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${process.env.GH_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('GitHub PUT ' + res.status + ' ' + (await res.text()).slice(0, 200));
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (!process.env.GH_TOKEN) {
    return res.status(500).json({ error: 'GH_TOKEN 환경변수가 없습니다' });
  }

  try {
    const prev = await ghGet(STATE_PATH);
    const state = prev ? prev.data : { checks: {} };
    const changed = [], failed = [], ok = [];

    // 같은 URL은 한 번만 요청
    const urls = [...new Set(Object.values(SOURCES))];
    const fps = {};
    await Promise.all(urls.map(async (u) => {
      try { fps[u] = fingerprint(await fetchText(u)); }
      catch (e) { fps[u] = { error: String(e.message || e) }; }
    }));

    for (const [id, url] of Object.entries(SOURCES)) {
      const fp = fps[url];
      if (fp.error) { failed.push({ id, url, error: fp.error }); continue; }

      const old = state.checks[id];
      if (old && old.hash !== fp.hash) {
        changed.push({
          id, url,
          before: old.hash, after: fp.hash,
          size_delta: fp.length - old.length,
          last_seen: old.at,
        });
      } else {
        ok.push(id);
      }
      state.checks[id] = { hash: fp.hash, length: fp.length, at: new Date().toISOString() };
    }

    state.last_run = new Date().toISOString();
    await ghPut(STATE_PATH, state, prev && prev.sha, 'watch: 출처 페이지 점검');

    // 변경이 감지되면 앱 데이터에 needs_review 표시를 남긴다
    if (changed.length) {
      const dataFile = await ghGet(DATA_PATH);
      if (dataFile) {
        const ids = changed.map((c) => c.id);
        let touched = false;
        dataFile.data.programs.forEach((p) => {
          if (ids.includes(p.id) && !p.needs_review) { p.needs_review = true; touched = true; }
        });
        if (touched) {
          await ghPut(DATA_PATH, dataFile.data, dataFile.sha,
            'watch: 출처 변경 감지 — 검토 필요 표시 (' + ids.join(', ') + ')');
        }
      }
    }

    res.status(200).json({
      ran_at: state.last_run,
      changed_count: changed.length,
      changed,
      unchanged: ok.length,
      failed,
      note: changed.length
        ? '출처가 바뀐 사업이 있습니다. 실제 요건이 달라졌는지 확인하고 programs-live.json을 수정하세요.'
        : '변경 없음.',
    });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
};
