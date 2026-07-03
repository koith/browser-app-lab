// Vercel Serverless Function — Serper(Google) 검색 프록시
// 경로: /api/search
//
// 역할: 앱에서 검색어를 받아 Serper(google.serper.dev)에 대신 요청하고,
//       결과에서 제목·URL·플랫폼·설명만 뽑아 돌려준다.
// 키는 코드에 없다. Vercel 환경변수 SERPER_KEY 에서 읽는다.
// (구버전 BRAVE_KEY가 남아있어도 무시된다.)
//
// 요청:  POST /api/search   { "q": "검색어", "count": 10, "verified": true }
//        또는 GET /api/search?q=검색어&verified=true
// 응답:  { "results": [ { "title", "url", "platform", "description" }, ... ] }

const ALLOWED_ORIGINS = [
  "https://koith.github.io",
  "https://browser-app-lab.vercel.app",
  "http://localhost",
];

function setCors(req, res) {
  const origin = req.headers.origin || "";
  // 등록된 origin이면 그대로 허용. 그 외 koith.github.io / *.vercel.app 도 허용(자기 프로젝트).
  let allow = ALLOWED_ORIGINS[0];
  if (ALLOWED_ORIGINS.includes(origin)) allow = origin;
  else if (/^https:\/\/([a-z0-9-]+\.)*koith\.github\.io$/.test(origin)) allow = origin;
  else if (/^https:\/\/browser-app-lab[a-z0-9-]*\.vercel\.app$/.test(origin)) allow = origin;
  res.setHeader("Access-Control-Allow-Origin", allow);
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Max-Age", "86400");
}

function platformOf(u) {
  try { return new URL(u).hostname.replace(/^www\./, ""); }
  catch (e) { return ""; }
}

export default async function handler(req, res) {
  setCors(req, res);

  if (req.method === "OPTIONS") { res.status(204).end(); return; }

  // 입력 파싱 (GET/POST 둘 다 허용)
  let q = "", count = 10, verified = false;
  if (req.method === "POST") {
    const b = typeof req.body === "string" ? safeParse(req.body) : (req.body || {});
    q = (b.q || "").trim();
    count = clampInt(b.count, 10);
    verified = b.verified === true;
  } else if (req.method === "GET") {
    q = ((req.query.q) || "").trim();
    count = clampInt(req.query.count, 10);
    verified = req.query.verified === "true";
  } else {
    res.status(405).json({ error: "method_not_allowed" }); return;
  }

  // 게이트: 신원확인된 케이스에서만 검색 허용
  if (!verified) { res.status(403).json({ error: "case_not_verified", results: [] }); return; }
  if (!q)        { res.status(400).json({ error: "empty_query", results: [] }); return; }

  const key = process.env.SERPER_KEY;
  if (!key)      { res.status(500).json({ error: "missing_api_key" }); return; }

  // Serper(Google) 호출: POST + X-API-KEY
  try {
    const r = await fetch("https://google.serper.dev/search", {
      method: "POST",
      headers: {
        "X-API-KEY": key,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ q, num: count }),
    });
    if (!r.ok) {
      const txt = await r.text();
      res.status(502).json({ error: "serper_error", status: r.status, detail: txt.slice(0, 200) });
      return;
    }
    const data = await r.json();
    // organic 배열: { title, link, snippet, position }
    const items = ((data.organic) || []).map(x => ({
      title: x.title || "",
      url: x.link || "",
      platform: platformOf(x.link || ""),
      description: x.snippet || "",
    })).filter(x => x.url);
    res.status(200).json({ query: q, count: items.length, results: items });
  } catch (e) {
    res.status(502).json({ error: "fetch_failed", detail: String(e).slice(0, 200) });
  }
}

function clampInt(v, d) {
  const n = parseInt(v, 10);
  if (isNaN(n)) return d;
  return Math.min(Math.max(n, 1), 20);
}
function safeParse(s) { try { return JSON.parse(s); } catch (e) { return {}; } }

// redeploy trigger 20260703T154917Z
