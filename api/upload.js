// Vercel Serverless Function — 후보 분석 업로드 프록시
// 경로: /api/upload
//
// 역할: 앱에서 후보 JSON을 받아, 숨겨진 GH_TOKEN으로
//       비공개 저장소(koith/undertaker-analysis)에 커밋한다.
// 토큰은 코드/앱에 없다. Vercel 환경변수 GH_TOKEN 에서만 읽는다.
//
// 요청: POST /api/upload  { caseId, subjectName, candidates:[...], verified:true }
// 응답: { ok:true, path, commit }

const ALLOWED_ORIGINS = [
  "https://koith.github.io",
  "https://browser-app-lab.vercel.app",
  "http://localhost",
];
const ANALYSIS_REPO = "koith/undertaker-analysis"; // 비공개 저장소

function setCors(req, res) {
  const origin = req.headers.origin || "";
  let allow = ALLOWED_ORIGINS[0];
  if (ALLOWED_ORIGINS.includes(origin)) allow = origin;
  else if (/^https:\/\/([a-z0-9-]+\.)*koith\.github\.io$/.test(origin)) allow = origin;
  else if (/^https:\/\/browser-app-lab[a-z0-9-]*\.vercel\.app$/.test(origin)) allow = origin;
  res.setHeader("Access-Control-Allow-Origin", allow);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Max-Age", "86400");
}

function b64utf8(str) {
  return Buffer.from(str, "utf-8").toString("base64");
}
function safeName(s) {
  return (s || "case").replace(/[^\w가-힣.-]+/g, "_").slice(0, 40);
}

export default async function handler(req, res) {
  setCors(req, res);
  if (req.method === "OPTIONS") { res.status(204).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "method_not_allowed" }); return; }

  let body = {};
  try { body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {}); }
  catch (e) { res.status(400).json({ error: "bad_json" }); return; }

  if (body.verified !== true) { res.status(403).json({ error: "case_not_verified" }); return; }
  const candidates = Array.isArray(body.candidates) ? body.candidates : null;
  if (!candidates) { res.status(400).json({ error: "no_candidates" }); return; }

  const token = process.env.GH_TOKEN;
  if (!token) { res.status(500).json({ error: "missing_gh_token" }); return; }

  // 저장 경로: exports/{caseId}-{time}.json
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const path = `exports/${safeName(body.caseId)}-${ts}.json`;
  const payload = JSON.stringify({
    caseId: body.caseId || null,
    subjectName: body.subjectName || null,
    exportedAt: new Date().toISOString(),
    count: candidates.length,
    candidates,
  }, null, 2);

  try {
    const r = await fetch(`https://api.github.com/repos/${ANALYSIS_REPO}/contents/${encodeURIComponent(path)}`, {
      method: "PUT",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "undertaker-app",
      },
      body: JSON.stringify({
        message: `candidate export: ${safeName(body.subjectName)} (${candidates.length})`,
        content: b64utf8(payload),
      }),
    });
    const data = await r.json();
    if (!r.ok) {
      res.status(502).json({ error: "github_error", status: r.status, detail: (data && data.message) || "" });
      return;
    }
    res.status(200).json({ ok: true, path, commit: data.commit && data.commit.sha });
  } catch (e) {
    res.status(502).json({ error: "upload_failed", detail: String(e).slice(0, 200) });
  }
}
