"""First-party, authenticated gallery pages for the existing private archive.

The public GitHub Pages site contains only the gallery application and already
publicly committed images. TeraBox originals never pass through GitHub Pages.
On iPhone Safari the whole viewer, API and HttpOnly session cookie use the SAME
Render origin, avoiding cross-site cookie restrictions. No import UI is needed.
"""
from __future__ import annotations

import hashlib
import time
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
    r"^(?:stored-albums/[a-z0-9-]{2,110}/[a-zA-Z0-9._-]+\.(?:jpg|jpeg|png|webp|avif)"
    r"|publisher-logos/[a-zA-Z0-9._-]+\.(?:jpg|jpeg|png|webp|svg))$"
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


_public_asset_cache: dict[tuple[str, str], tuple[float, bytes, str]] = {}

async def public_asset(model: str, asset_path: str) -> tuple[bytes, str]:
    # The HTML, JS, and metadata are immutable for a short period. Avoid a
    # GitHub Pages round-trip on every iPhone refresh and album navigation.
    key = (model, asset_path)
    cached = _public_asset_cache.get(key)
    if cached and time.monotonic() - cached[0] < (90 if asset_path.endswith('.json') else 240):
        return cached[1], cached[2]
    url = f"{SOURCE_BASE}/{model}-gallery/{asset_path}"
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        result = await client.get(url, headers={"User-Agent": "ArchiveFirstPartyViewer/1.0"})
    if result.status_code != 200:
        raise HTTPException(status_code=502, detail="Gallery static asset unavailable")
    if len(result.content) > 3_000_000:
        raise HTTPException(status_code=502, detail="Gallery metadata too large")
    content_type = "application/json" if asset_path.endswith(".json") else (
        "application/javascript" if asset_path.endswith(".js") else "text/html")
    if len(result.content) <= 1_500_000:
        _public_asset_cache[key] = (time.monotonic(), result.content, content_type)
    return result.content, content_type


def install_portal(app, *, token_getter, configured, catalog_for_model):
    async def serve_gallery(model: str, request: Request):
        if model not in ("yui", "mimmi"):
            raise HTTPException(status_code=404)
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

    @app.get("/gallery/{model}/{asset_path:path}")
    async def gallery_asset(model: str,asset_path: str,request: Request):
        if model in ("yui-gallery","mimmi-gallery"):
            destination=model.split("-")[0]
            return RedirectResponse(f"/gallery/{destination}/{asset_path}",status_code=307)
        if model not in ("yui","mimmi"):
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
