"""First-party, authenticated gallery pages for the existing private archive.

The public GitHub Pages site contains only the gallery application and already
publicly committed images. TeraBox originals never pass through GitHub Pages.
On iPhone Safari the whole viewer, API and HttpOnly session cookie use the SAME
Render origin, avoiding cross-site cookie restrictions. No import UI is needed.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import re
import secrets
import time
from urllib.parse import parse_qs, quote

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

COOKIE_NAME = "__Host-gallery-viewer"
COOKIE_AGE = 28 * 24 * 60 * 60
SOURCE_BASE = "https://koith.github.io/browser-app-lab/apps"
SAFE_ASSET = re.compile(r"^[a-zA-Z0-9._/-]{1,220}$")
SAFE_IMAGE = re.compile(
    r"^(?:stored-albums/[a-z0-9-]{2,110}/[a-zA-Z0-9._-]+\\.(?:jpg|jpeg|png|webp|avif)"
    r"|publisher-logos/[a-zA-Z0-9._-]+\\.(?:jpg|jpeg|png|webp|svg))$"
)
ALLOWED_ASSETS = {
    "owner-media.js", "photo-vault.js", "gallery-labels.js",
    "publishers.js", "stored-albums.json", "identity-exclusions.json",
    "album-covers.json", "album-aliases.json", "publishers.json",
}
PORTAL_CSP = (
    "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https://koith.github.io data: blob:; "
    "connect-src 'self'; object-src 'none'"
)


def session_sign(token: str, expiry: int) -> str:
    key = hashlib.sha256(token.encode("utf-8")).digest()
    mac = hmac.new(key, f"gallery-session-v1:{expiry}".encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{mac}"


def session_valid(token: str, value: str | None) -> bool:
    if not token or not value or len(value) > 100:
        return False
    try:
        expires, mac = value.split(".", 1)
        if not expires.isdecimal() or len(expires) > 12 or not re.fullmatch(r"[a-f0-9]{64}", mac):
            return False
        when = int(expires)
        now = int(time.time())
        if when <= now or when > now + COOKIE_AGE + 60:
            return False
        return secrets.compare_digest(session_sign(token, when), value)
    except (ValueError, TypeError):
        return False


def secure_headers() -> dict[str, str]:
    return {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": PORTAL_CSP}


def login_page(model: str, message: str = "") -> HTMLResponse:
    label = "심유이" if model == "yui" else "밈미"
    failure = f'<p class="error" role="alert">{html.escape(message)}</p>' if message else ""
    body = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow"><title>{label} 갤러리</title>
<style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;color-scheme:dark;background:#101114;color:#f0f1f4}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:410px;margin:0 auto;padding:clamp(36px,11vh,105px) 22px}}
small{{font-size:11px;letter-spacing:.17em;color:#90909b}}h1{{font-size:28px;letter-spacing:-.04em;margin:18px 0 9px}}
p{{color:#a2a3ae;font-size:13px;line-height:1.7}}label{{display:block;margin:32px 0 9px;font-size:13px}}
input{{width:100%;padding:15px;border:1px solid #4a4a54;background:#1d1d23;border-radius:8px;color:#fff;font-size:16px}}
button{{background:#e7e7ec;color:#111;border:0;border-radius:8px;padding:14px;width:100%;font-size:15px;font-weight:700;margin-top:16px}}
.error{{color:#ffc5c5}}
</style></head><body><main><small>PRIVATE PHOTO ARCHIVE</small><h1>{label} 갤러리</h1>
<p>보관한 사진은 비공개로 유지됩니다. 최초 인증 후 이 기기에서 자동으로 열립니다.</p>
<form method="post" action="/gallery/login" autocomplete="off">
<input name="model" type="hidden" value="{model}">
<label for="code">개인 갤러리 접근 코드</label>
<input name="code" id="code" type="password" autocomplete="current-password" required maxlength="2048">
<button type="submit">갤러리 열기</button></form>{failure}</main></body></html>"""
    return HTMLResponse(body, headers=secure_headers())


async def public_asset(model: str, asset_path: str) -> tuple[bytes, str]:
    url = f"{SOURCE_BASE}/{model}-gallery/{asset_path}"
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        result = await client.get(url, headers={"User-Agent": "ArchiveFirstPartyViewer/1.0"})
    if result.status_code != 200:
        raise HTTPException(status_code=502, detail="Gallery static asset unavailable")
    if len(result.content) > 3_000_000:
        raise HTTPException(status_code=502, detail="Gallery metadata too large")
    content_type = "application/json" if asset_path.endswith(".json") else (
        "application/javascript" if asset_path.endswith(".js") else "text/html")
    return result.content, content_type


def install_portal(app, *, token_getter, configured, catalog_for_model):
    def authorized(request: Request) -> bool:
        return session_valid(token_getter(), request.cookies.get(COOKIE_NAME))

    async def serve_gallery(model: str, request: Request):
        if model not in ("yui", "mimmi"):
            raise HTTPException(status_code=404)
        if not authorized(request):
            return login_page(model)
        try:
            document, _ = await public_asset(model, "index.html")
        except (httpx.HTTPError, HTTPException):
            raise HTTPException(status_code=502, detail="Gallery frontend unavailable")
        # The original Yui/Mimmi gallery UI remains authoritative.
        return HTMLResponse(document.decode("utf-8"), headers=secure_headers())

    @app.get("/gallery/")
    async def portal_home():
        return RedirectResponse("/gallery/yui/", status_code=307)

    @app.get("/gallery/{model}")
    async def gallery_no_slash(model: str):
        if model not in ("yui","mimmi"):
            raise HTTPException(status_code=404)
        return RedirectResponse(f"/gallery/{model}/", status_code=307)

    @app.get("/gallery/{model}/")
    async def gallery_home(model: str, request: Request):
        if model=="yui-gallery":
            return RedirectResponse("/gallery/yui/", status_code=307)
        if model=="mimmi-gallery":
            return RedirectResponse("/gallery/mimmi/", status_code=307)
        return await serve_gallery(model,request)

    @app.post("/gallery/login")
    async def gallery_login(request: Request):
        payload=await request.body()
        if len(payload)>4200 or not configured():
            raise HTTPException(status_code=503,detail="Gallery login unavailable")
        data=parse_qs(payload.decode("utf-8",errors="replace"),keep_blank_values=False)
        model=(data.get("model") or [""])[0]
        code=(data.get("code") or [""])[0]
        if model not in ("yui","mimmi"):
            raise HTTPException(status_code=400)
        if not code or not secrets.compare_digest(code,token_getter()):
            return login_page(model,"접근 코드를 확인해 주세요.")
        try:
            remote=await catalog_for_model(model)
            if not isinstance(remote.get("albums"),list) or remote.get("model")!=model:
                raise ValueError("Incorrect model archive")
        except Exception:
            return login_page(model,"원본 보관소와 연결되지 않았습니다.")
        response=RedirectResponse(f"/gallery/{model}/",status_code=303,headers=secure_headers())
        response.set_cookie(COOKIE_NAME,session_sign(code,int(time.time())+COOKIE_AGE),
                            httponly=True,secure=True,samesite="lax",path="/",max_age=COOKIE_AGE)
        return response

    @app.post("/gallery/logout")
    async def gallery_logout(request: Request):
        # Avoid other sites forcing a logout.
        origin=request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403)
        r=RedirectResponse("/gallery/",status_code=303,headers=secure_headers())
        r.delete_cookie(COOKIE_NAME,path="/",secure=True,httponly=True,samesite="lax")
        return r

    @app.get("/gallery/{model}/{asset_path:path}")
    async def gallery_asset(model: str,asset_path: str,request: Request):
        if model in ("yui-gallery","mimmi-gallery"):
            destination=model.split("-")[0]
            return RedirectResponse(f"/gallery/{destination}/{asset_path}",status_code=307)
        if model not in ("yui","mimmi") or not authorized(request):
            raise HTTPException(status_code=401)
        if asset_path=="index.html":
            return await serve_gallery(model,request)
        if not SAFE_ASSET.fullmatch(asset_path) or ".." in asset_path or "//" in asset_path:
            raise HTTPException(status_code=404)
        if SAFE_IMAGE.fullmatch(asset_path):
            return RedirectResponse(
                f"{SOURCE_BASE}/{model}-gallery/{quote(asset_path, safe='/')}",
                status_code=307,
                headers={"Referrer-Policy":"no-referrer"}
            )
        if asset_path not in ALLOWED_ASSETS:
            raise HTTPException(status_code=404)
        try:
            data,content_type=await public_asset(model,asset_path)
        except (httpx.HTTPError,HTTPException):
            raise HTTPException(status_code=502,detail="Gallery app resource unavailable")
        return Response(data,media_type=content_type,headers=secure_headers())
