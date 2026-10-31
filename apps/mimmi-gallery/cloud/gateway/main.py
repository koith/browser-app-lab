"""Private media gateway: TeraBox originals, optional private R2 previews.

Sensitive storage cookies stay in server env, never in the GitHub Pages client.
Every user API request requires the private gallery bearer token. Full size media
is proxied on-demand, so TeraBox's unofficial backend can be slow.

The container does not keep originals on its ephemeral disk. They live remotely.
"""
from __future__ import annotations

import asyncio
import httpx
import hashlib
import json
import re
import os
import secrets
import tempfile
import time
from collections import OrderedDict
from io import BytesIO
import jwt
from pathlib import Path, PurePosixPath
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
try:
    from gateway.portal import COOKIE_NAME, install_portal, session_valid
    from gateway.media_cache import VerifiedMediaCache, read_media_with_transport_recovery
    from gateway.cookie_format import cookie_header
    from gateway.catalog_view import gallery_catalog
    from gateway.sealed_session import restore as restore_storage_state, seal as seal_storage_state
except ModuleNotFoundError:
    from portal import COOKIE_NAME, install_portal, session_valid
    from media_cache import VerifiedMediaCache, read_media_with_transport_recovery
    from cookie_format import cookie_header
    from catalog_view import gallery_catalog
    from sealed_session import restore as restore_storage_state, seal as seal_storage_state
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

app = FastAPI(title="Mimmi Private Archive Media Gateway", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://koith.github.io", "http://localhost:8765"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition", "X-Archive-Source"],
)
REMOTE = os.environ.get("ARCHIVE_REMOTE", "archive:MimmiArchive").rstrip("/")
# The optional R2 preview cache is private: never upload originals to R2.
R2_PREVIEW_REMOTE = os.environ.get("R2_PREVIEW_REMOTE", "").rstrip("/")
R2_READY = bool(
    R2_PREVIEW_REMOTE.startswith("previewcache:")
    and os.environ.get("RCLONE_CONFIG_PREVIEWCACHE_ACCESS_KEY_ID")
    and os.environ.get("RCLONE_CONFIG_PREVIEWCACHE_SECRET_ACCESS_KEY")
    and os.environ.get("RCLONE_CONFIG_PREVIEWCACHE_ENDPOINT", "").startswith("https://")
    and os.environ.get("RCLONE_CONFIG_PREVIEWCACHE_TYPE") == "s3"
    and os.environ.get("RCLONE_CONFIG_PREVIEWCACHE_PROVIDER") == "Cloudflare"
)
TOKEN = os.environ.get("GALLERY_ACCESS_TOKEN", "")
COOKIE = os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE", "")
if os.environ.get('ARCHIVE_STORAGE_STATE_SEALED'):
    try:
        COOKIE=restore_storage_state(os.environ['ARCHIVE_STORAGE_STATE_SEALED'],TOKEN)
        os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']=COOKIE
        print('OWNER_STORAGE_CONNECTION_RESTORED',flush=True)
    except ValueError:
        print('OWNER_STORAGE_CONNECTION_STATE_INVALID',flush=True)
_cache = {"time": 0.0, "catalog": None}
_cache_lock = asyncio.Lock()
# Measured usage was about 200 MiB with the 48 MiB cache on the existing
# 512 MiB free service. Retain exact originals across cover/detail/popup traffic
# without changing worker count, read deadlines or the service plan.
_media_cache = VerifiedMediaCache(max_bytes=128*1024*1024)


def safe_remote_diagnostic(error: str) -> str:
    # rclone errors include signed download URLs. Remove the entire URL before
    # truncation so the useful trailing failure reason survives without tokens.
    value = re.sub(r'https?://[^\s"<>]+', '[remote URL]', error)
    value = re.sub(r'(?i)(cookie|authorization|ndus|token)[=:]\s*[^\s]+', r'\1=[redacted]', value)
    lines = [line for line in value.splitlines() if 'Config file' not in line]
    return ' '.join(lines)[-600:]


async def verified_remote_media(key: str, size: int, digest: str, remote: str):
    if (type(size) is not int or not 1 <= size <= 140_000_000
            or not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)):
        raise HTTPException(status_code=502, detail='Invalid private media integrity metadata')
    async def load():
        async def read():return await rclone_bytes(key, size + 1, remote=remote)
        return await read_media_with_transport_recovery(read)
    try:
        return await _media_cache.get(remote, key, size, digest, load)
    except ValueError:
        raise HTTPException(status_code=502, detail='Cloud media SHA-256 integrity check failed')


def media_key_valid(key: str) -> bool:
    if not key or len(key) > 700 or "\\" in key or "%" in key:
        return False
    if key.startswith("/") or "\x00" in key:
        return False
    parts = PurePosixPath(key).parts
    return bool(parts) and all(p not in ("..", ".", "") for p in parts) and parts[0] in ("originals", "previews")


async def authenticated(request: Request, authorization: str | None = Header(default=None)):
    if not TOKEN or not COOKIE:
        raise HTTPException(status_code=503, detail="Cloud gateway is not connected")
    expected = "Bearer " + TOKEN
    bearer_ok = bool(authorization) and secrets.compare_digest(authorization, expected)
    first_party_ok = session_valid(TOKEN, request.cookies.get(COOKIE_NAME))
    if not (bearer_ok or first_party_ok):
        raise HTTPException(status_code=401, detail="Authorization required", headers={"WWW-Authenticate": "Bearer"})



async def read_owner_media_via_copyto(path: str, limit: int, client_env: dict,
                                      remote: str | None = None) -> bytes:
    """Read an existing own-account original by a proven alternative rclone method.

    Exact SHA verification remains mandatory in verified_remote_media().
    This doesn't alter source credentials, any remote object or access controls.
    """
    if not media_key_valid(path) or not 1 <= limit <= 140_000_001:
        raise HTTPException(status_code=502,detail='Invalid owner media read request')
    with tempfile.TemporaryDirectory(prefix='gallery-media-copyto-') as tmp:
        destination=Path(tmp)/'owner-media'
        proc=await asyncio.create_subprocess_exec(
            'rclone','copyto',f"{remote or REMOTE}/{path}",str(destination),
            '--timeout=50s','--retries=1',
            stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE,
            env=client_env)
        try:
            _,stderr=await asyncio.wait_for(proc.communicate(),timeout=110)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(status_code=504,detail='Owner media alternate read timed out')
        if proc.returncode:
            print('OWNER_MEDIA_COPYTO_READ_FAILED',
                  safe_remote_diagnostic(stderr.decode('utf-8','replace')),flush=True)
            raise HTTPException(status_code=502,detail='Cloud media unavailable')
        if not destination.is_file() or not 0 < destination.stat().st_size <= limit:
            raise HTTPException(status_code=502,detail='Owner media alternate read invalid size')
        raw=await asyncio.to_thread(destination.read_bytes)
        if len(raw)<=512:
            try: response=json.loads(raw)
            except (ValueError,TypeError):response={}
            if isinstance(response,dict) and type(response.get('errno')) is int:
                raise HTTPException(status_code=502,detail='Owner media still unavailable')
        print('OWNER_MEDIA_COPYTO_FALLBACK_FULL_SHA_CHECK_REQUIRED',flush=True)
        return raw



async def rclone_bytes(path: str, limit: int, *, remote: str | None = None) -> bytes:
    """Drain the *entire* remote stream, with size/timeout bounds.

    A single StreamReader.read(limit) may return only the first network chunk.
    Never treat such a partial read as a successfully fetched photograph.
    """
    client_env=os.environ.copy()
    try:
        configured=client_env.get('RCLONE_CONFIG_ARCHIVE_COOKIE','')
        client_env['RCLONE_CONFIG_ARCHIVE_COOKIE']=cookie_header(configured)
    except ValueError:
        raise HTTPException(status_code=503,detail='Invalid storage session configuration')
    if client_env['RCLONE_CONFIG_ARCHIVE_COOKIE']!=configured:
        print('OWNER_STORAGE_COOKIE_HEADER_NORMALIZED',flush=True)
    proc = await asyncio.create_subprocess_exec(
        "rclone", "cat", f"{remote or REMOTE}/{path}", "--timeout=50s", "--retries=2",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=client_env
    )

    async def drain_stderr() -> str:
        # Drain in parallel so a noisy rclone process cannot block on stderr.
        prefix = bytearray()
        while chunk := await proc.stderr.read(4096):
            if len(prefix) < 3000:
                prefix.extend(chunk[:3000 - len(prefix)])
        return prefix.decode("utf-8", errors="replace")

    stderr_task = asyncio.create_task(drain_stderr())
    try:
        async def read_all() -> bytes:
            content = bytearray()
            while chunk := await proc.stdout.read(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise HTTPException(status_code=413, detail="Remote asset larger than supported")
            rc = await proc.wait()
            error = await stderr_task
            if rc:
                print("RCLONE_REMOTE_READ_FAILED", path, safe_remote_diagnostic(error), flush=True)
                if 'Failed to login' in error:
                    raise HTTPException(status_code=503, detail="Storage session unavailable", headers={"Retry-After":"30"})
                retryable=bool(re.search(r'i/o timeout|connection reset|unexpected EOF',error,re.I))
                raise HTTPException(status_code=502, detail="Cloud media unavailable",
                    headers={'X-Archive-Read-Cause':'transport_interruption'} if retryable else None)
            raw=bytes(content)
            if path.startswith(('originals/','previews/')) and len(raw)<=512:
                try: body=json.loads(raw)
                except (ValueError,TypeError):body={}
                if isinstance(body,dict) and body.get('errno')==400141:
                    # Full SHA remains mandatory in verified_remote_media().
                    return await read_owner_media_via_copyto(path,limit,client_env,remote)
            return raw

        return await asyncio.wait_for(read_all(), timeout=115)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Cloud read timed out")
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        if not stderr_task.done():
            await stderr_task


async def get_catalog():
    if _cache["catalog"] and (time.time()-_cache["time"]) < 180:
        return _cache["catalog"]
    async with _cache_lock:
        if _cache["catalog"] and (time.time()-_cache["time"]) < 180:
            return _cache["catalog"]
        blob = await rclone_bytes("metadata/catalog.json", 4_000_000)
        catalog = json.loads(blob)
        if catalog.get("schema_version") != 1 or catalog.get("model") != "mimmi":
            raise HTTPException(status_code=502, detail="Unsupported catalogue version")
        _cache["catalog"] = catalog
        _cache["time"] = time.time()
        return catalog


async def catalog_photo(loader, cache, album_id, number, kind, version):
    """Never cache an older photo under a newly published SHA-pinned URL."""
    if version and not re.fullmatch(r'[a-f0-9]{24,64}', version):
        raise HTTPException(status_code=400, detail='Invalid media version', headers={'Cache-Control':'no-store'})
    for attempt in range(2 if version else 1):
        catalog = await loader()
        album = next((a for a in catalog['albums'] if a.get('id') == album_id), None)
        photo = next((p for p in (album or {}).get('images', []) if p.get('number') == number), None)
        digest_field = 'preview_sha256' if kind == 'preview' and photo and photo.get('preview') else 'sha256'
        if photo and (not version or str(photo.get(digest_field, '')).startswith(version)):
            return photo
        if not version:
            raise HTTPException(status_code=404, detail='Unknown stored photo')
        # Invalidate this snapshot only. The loader's existing lock coalesces
        # concurrent requests and prevents replacing a newer catalogue.
        if attempt == 0 and cache['catalog'] is catalog:
            cache['time'] = 0
    raise HTTPException(status_code=409, detail='Stored photo version is not published yet',
                        headers={'Cache-Control':'no-store'})


@app.get("/api/health")
async def health():
    # Never disclose credentials or confirm account identity through health.
    return {"service": "Mimmi private archive", "configured": bool(TOKEN and COOKIE),
            "data_connected": bool(_cache["catalog"]), "r2_preview_cache_configured": R2_READY}


@app.get("/api/catalog")
async def catalog():
    return JSONResponse(gallery_catalog(await get_catalog()), headers={
        "Cache-Control": "private, max-age=180, stale-while-revalidate=300"
    })


@app.get("/api/media/{album_id}/{image_num}/{kind}")
async def media(album_id: str, image_num: int, kind: str, download: bool = Query(False), v: str = Query("")):
    if not (2 <= len(album_id) <= 100 and album_id.replace("-", "").isalnum()) or image_num < 1:
        raise HTTPException(status_code=400, detail="Invalid media ID")
    if kind not in ("preview", "original"):
        raise HTTPException(status_code=404, detail="Unknown media type")
    img = await catalog_photo(get_catalog, _cache, album_id, image_num, kind, v)
    has_separate_preview = (kind == "preview" and bool(img.get("preview")))
    key_field = "preview" if has_separate_preview else "key"
    digest_field = "preview_sha256" if has_separate_preview else "sha256"
    size_field = "preview_bytes" if has_separate_preview else "bytes"
    key = img.get(key_field)
    if not isinstance(key, str) or not media_key_valid(key):
        raise HTTPException(status_code=502, detail="Invalid private media path")
    # Older TeraBox catalogs stored one physical full-size file only; new ones
    # contain a separate small thumbnail with its own verified digest.
    expected_prefix = "previews" if has_separate_preview else "originals"
    if not key.startswith(expected_prefix + "/" + album_id + "/"):
        raise HTTPException(status_code=502, detail="Manifest media path mismatch")
    limit = 35_000_000 if has_separate_preview else 140_000_000
    declared_digest = img.get(digest_field)
    declared_bytes = img.get(size_field)

    def integrity_ok(data: bytes) -> bool:
        return (isinstance(declared_digest, str)
                and bool(re.fullmatch(r"[0-9a-f]{64}", declared_digest))
                and type(declared_bytes) is int
                and declared_bytes == len(data)
                and hashlib.sha256(data).hexdigest() == declared_digest)

    source = "terabox"
    blob = None
    if kind == "preview" and R2_READY and not has_separate_preview:
        try:
            cached = await rclone_bytes(key, limit, remote=R2_PREVIEW_REMOTE)
            if integrity_ok(cached):
                blob, source = cached, "r2-preview-cache"
            else:
                print("R2_PREVIEW_CACHE_HASH_MISMATCH", album_id, image_num, flush=True)
        except (HTTPException, OSError) as exc:
            # A cache outage must not break access to a verified origin preview.
            print("R2_PREVIEW_CACHE_UNAVAILABLE", album_id, image_num, type(exc).__name__, flush=True)
    if blob is None:
        try:
            blob = await verified_remote_media(key, declared_bytes, declared_digest, REMOTE)
        except HTTPException as error:
            if not has_separate_preview or error.status_code not in (502, 504):
                raise
            fallback = await media(album_id, image_num, 'original', download=download, v="")
            fallback.headers['X-Archive-Variant'] = 'verified-original-fallback'
            return fallback
    extension = key.rsplit(".", 1)[-1].lower()
    content_type = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp","avif":"image/avif"}.get(extension,"application/octet-stream")
    headers={"Cache-Control":"private, max-age=600","ETag":'"'+declared_digest+'"',"X-Content-Type-Options":"nosniff",
             "Content-Length":str(len(blob)), "X-Archive-Source":source}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{album_id}-{image_num:04d}.{extension}"'
    return StreamingResponse(iter([blob]),media_type=content_type,headers=headers)


# One already deployed FREE Render gateway serves two *separate* personal
# TeraBox folders. A GitHub Actions secret does not automatically appear in
# Render; the owner must configure its RCLONE_CONFIG_ARCHIVE_COOKIE separately.
YUI_REMOTE = "archive:YuiArchive"
_yui_cache = {"catalog": None, "time": 0.0}
_yui_cache_lock = asyncio.Lock()


async def yui_catalog_bytes():
    if _yui_cache["catalog"] and time.time() - _yui_cache["time"] < 180:
        return _yui_cache["catalog"]
    async with _yui_cache_lock:
        if _yui_cache["catalog"] and time.time() - _yui_cache["time"] < 180:
            return _yui_cache["catalog"]
        data = await rclone_bytes("metadata/catalog.json", 6_000_000, remote=YUI_REMOTE)
        d = json.loads(data)
        if d.get("schema_version") != 1 or d.get("model") != "yui" or not isinstance(d.get("albums"), list):
            raise HTTPException(status_code=502, detail="Incorrect Yui private catalog")
        _yui_cache.update(catalog=d, time=time.time())
        return d


@app.get("/api/yui/catalog")
async def yui_catalog():
    return JSONResponse(gallery_catalog(await yui_catalog_bytes()), headers={
        "Cache-Control": "private, max-age=180, stale-while-revalidate=300"
    })


@app.get("/api/yui/media/{album_id}/{image_num}/{kind}")
async def yui_media(album_id: str, image_num: int, kind: str, download: bool = Query(False), v: str = Query("")):
    if (not 2 <= len(album_id) <= 100
            or not re.fullmatch("[a-z0-9][a-z0-9-]{1,99}", album_id)
            or image_num < 1 or kind not in ("preview", "original")):
        raise HTTPException(status_code=400, detail="Invalid private photo")
    img = await catalog_photo(yui_catalog_bytes, _yui_cache, album_id, image_num, kind, v)
    key_field, sha_field, size_field = (
        ("preview", "preview_sha256", "preview_bytes") if kind == "preview"
        else ("key", "sha256", "bytes"))
    key = img.get(key_field)
    digest = img.get(sha_field)
    size = img.get(size_field)
    prefix = "previews" if kind == "preview" else "originals"
    if (not isinstance(key, str) or not media_key_valid(key)
            or not key.startswith(prefix + "/" + album_id + "/")
            or not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest)
            or type(size) is not int or not 1 <= size <= 35 * 1024 * 1024):
        raise HTTPException(status_code=502, detail="Invalid private media manifest")
    try:
        payload = await verified_remote_media(key, size, digest, YUI_REMOTE)
    except HTTPException as error:
        if kind != 'preview' or error.status_code not in (502, 504):
            raise
        fallback = await yui_media(album_id, image_num, 'original', download=download, v="")
        fallback.headers['X-Archive-Variant'] = 'verified-original-fallback'
        return fallback
    ext = key.rsplit(".", 1)[-1]
    mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(ext)
    if not mime:
        raise HTTPException(status_code=502, detail="Unsupported private photo format")
    headers = {"Cache-Control":"private, max-age=300",
               "ETag":'"'+digest+'"',
               "X-Content-Type-Options":"nosniff", "Content-Length":str(size)}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{album_id}-{image_num:05d}.{ext}"'
    return StreamingResponse(iter([payload]), media_type=mime, headers=headers)




# Safari album-cover fast path.  An album card never needs a full 4K original:
# derive a compact 420px WebP from a SHA-verified stored file, keep a bounded
# in-process LRU, and let the phone reuse its disk cache across refreshes.
_COVER_LIMIT_BYTES = 24 * 1024 * 1024
_cover_cache = OrderedDict()
_cover_cache_size = 0
_cover_pending = {}
_cover_lock = asyncio.Lock()
_cover_workers = asyncio.Semaphore(2)
Image.MAX_IMAGE_PIXELS = 40_000_000


def _encode_cover(data: bytes, original_type: str) -> tuple[bytes, str]:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Source photo too large for cover decoding")
            if source.format == "JPEG":
                source.draft("RGB", (420, 560))
            photo = ImageOps.exif_transpose(source)
            photo.thumbnail((420, 560), Image.Resampling.LANCZOS)
            if photo.mode != "RGB":
                photo = photo.convert("RGB")
            output = BytesIO()
            photo.save(output, format="WEBP", quality=68, method=3)
            return output.getvalue(), "image/webp"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        # Preserve the verified existing image if the optional WebP thumbnail
        # transform cannot decode a particular archived extension.
        return data, original_type


async def _read_cover(model: str, album_id: str, image_num: int,
                      has_preview: bool, version: str) -> tuple[bytes, str]:
    async with _cover_workers:
        kind = "preview" if has_preview else "original"
        async def verified_photo(request_kind: str):
            return await (
                yui_media(album_id, image_num, request_kind, download=False, v=version if request_kind == kind else "")
                if model == "yui" else media(album_id, image_num, request_kind, download=False, v=version if request_kind == kind else "")
            )
        try:
            response = await verified_photo(kind)
        except HTTPException as error:
            if error.detail == 'Storage session unavailable':
                raise
            if not has_preview or error.status_code not in (502, 503, 504):
                raise
            # Some archived preview files no longer match their recorded SHA.
            # A cover can safely use the separately SHA-verified original.
            response = await verified_photo("original")
        chunks = []
        total = 0
        async for chunk in response.body_iterator:
            total += len(chunk)
            if total > 36_000_000:
                raise HTTPException(status_code=413, detail="Cover source too large")
            chunks.append(chunk)
        return await asyncio.to_thread(
            _encode_cover, b"".join(chunks), response.media_type or "application/octet-stream"
        )


@app.get("/api/cover/{model}/{album_id}/{image_num}")
async def album_cover(model: str, album_id: str, image_num: int, request: Request):
    if model not in ("yui", "mimmi") or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{1,99}", album_id
    ) or image_num < 1:
        raise HTTPException(status_code=404, detail="Unknown stored cover")
    photo = await catalog_photo(yui_catalog_bytes if model == "yui" else get_catalog,
        _yui_cache if model == "yui" else _cache, album_id, image_num, 'preview', request.query_params.get('v', ''))
    has_preview = bool(photo.get("preview"))
    digest = photo.get("preview_sha256" if has_preview else "sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise HTTPException(status_code=502, detail="Invalid stored photo digest")
    etag = '"cover-v1-' + digest[:32] + '"'
    cache_headers = {
        "Cache-Control": "private, max-age=604800, immutable",
        "ETag": etag,
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    key = (model, album_id, image_num, digest)
    async with _cover_lock:
        hit = _cover_cache.get(key)
        if hit is not None:
            _cover_cache.move_to_end(key)
            task = None
        else:
            task = _cover_pending.get(key)
            if task is None:
                task = asyncio.create_task(
                    _read_cover(model, album_id, image_num, has_preview, digest)
                )
                _cover_pending[key] = task

    if hit is None:
        try:
            hit = await asyncio.shield(task)
        finally:
            async with _cover_lock:
                if _cover_pending.get(key) is task and task.done():
                    del _cover_pending[key]
        if len(hit[0]) <= 1_000_000:
            async with _cover_lock:
                global _cover_cache_size
                if key not in _cover_cache:
                    _cover_cache[key] = hit
                    _cover_cache_size += len(hit[0])
                    while _cover_cache_size > _COVER_LIMIT_BYTES:
                        _, expired = _cover_cache.popitem(last=False)
                        _cover_cache_size -= len(expired[0])
    return Response(
        content=hit[0], media_type=hit[1],
        headers={**cache_headers, "Content-Length": str(len(hit[0]))}
    )


# A signed GitHub Actions OIDC identity (not a password supplied by visitors)
# allows the same working private TeraBox session used in archive QA to be
# refreshed securely on this Render process. Never store it in Pages or logs.
_SYNC_AUDIENCE = "gallery-archive-terabox-sync"
_SYNC_WORKFLOW = (
    "koith/browser-app-lab/.github/workflows/"
    "gallery-terabox-render-session-sync.yml@refs/heads/main"
)
_SYNC_JWKS = jwt.PyJWKClient(
    "https://token.actions.githubusercontent.com/.well-known/jwks",
    cache_jwk_set=True, lifespan=3600
)
_sync_lock = asyncio.Lock()


def _verify_sync_identity(value: str) -> bool:
    if not value or len(value) > 12000:
        return False
    try:
        header = jwt.get_unverified_header(value)
        if header.get("alg") != "RS256" or any(
            k in header for k in ("jku", "jwk", "x5u")
        ):
            return False
        key = _SYNC_JWKS.get_signing_key_from_jwt(value).key
        claims = jwt.decode(
            value, key, algorithms=["RS256"], audience=_SYNC_AUDIENCE,
            issuer="https://token.actions.githubusercontent.com",
            leeway=30,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        return (
            claims.get("sub") == "repo:koith/browser-app-lab:ref:refs/heads/main"
            and claims.get("repository") == "koith/browser-app-lab"
            and str(claims.get("repository_id")) == "1284121913"
            and claims.get("ref") == "refs/heads/main"
            and claims.get("workflow_ref") == _SYNC_WORKFLOW
        )
    except Exception:
        return False


@app.post("/internal/terabox-session-refresh")
async def sync_archive_session(request: Request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not _verify_sync_identity(
        authorization[len("Bearer "):]
    ):
        raise HTTPException(status_code=403, detail="Invalid workflow identity")
    payload = await request.body()
    if len(payload) > 18000:
        raise HTTPException(status_code=413, detail="Request too large")
    try:
        cookie = json.loads(payload).get("cookie")
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid session payload")
    if (
        not isinstance(cookie, str) or not (8 <= len(cookie) <= 16000)
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie)
    ):
        raise HTTPException(status_code=400, detail="Invalid storage session")
    async with _sync_lock:
        old_cookie = os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE", "")
        os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"] = cookie
        try:
            for model, remote in (("mimmi", REMOTE), ("yui", YUI_REMOTE)):
                catalog_raw = await rclone_bytes(
                    "metadata/catalog.json", 6_000_000, remote=remote
                )
                catalog_data = json.loads(catalog_raw)
                if (
                    catalog_data.get("model") != model
                    or not isinstance(catalog_data.get("albums"), list)
                ):
                    raise ValueError("Incompatible archive")
        except Exception as error:
            # Do not log any cookie, access token, or remote error message.
            # Error class and model identify temporary read failure vs. schema.
            print("TERABOX_SYNC_ERROR", model, type(error).__name__,
                  getattr(error, "status_code", "-"), flush=True)
            os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"] = old_cookie
            raise HTTPException(
                status_code=503 if isinstance(error, (HTTPException, OSError, asyncio.TimeoutError)) else 422,
                detail="TeraBox session validation failed"
            )
        global COOKIE
        COOKIE = cookie
        _cache.update(catalog=None, time=0.0)
        _yui_cache.update(catalog=None, time=0.0)
    return JSONResponse(
        {"synced": True, "models": ["yui", "mimmi"]},
        headers={"Cache-Control": "no-store"},
    )

# Owner-only mobile gallery. It preserves all prior /api/* bearer clients and
# adds an HttpOnly, same-origin session for Safari, not public photo URLs.
async def _portal_catalog_for(model: str):
    return await (yui_catalog_bytes() if model == "yui" else get_catalog())

install_portal(app, token_getter=lambda: TOKEN,
               configured=lambda: bool(TOKEN and COOKIE),
               catalog_for_model=_portal_catalog_for)


# Optional short-lived transfer worker. No account secret is exported, and this
# worker can only append permit-pinned individual bytes plus a private queue.
try:
    from gateway.individual_import import install as install_individual_import,metadata_visibility_write_failure
    from gateway.terabox_web_state import OwnerUploadState, WebStateUnavailable
except ModuleNotFoundError:
    from individual_import import install as install_individual_import,metadata_visibility_write_failure
    from terabox_web_state import OwnerUploadState, WebStateUnavailable

owner_upload_state=OwnerUploadState()


async def _individual_read(model,key,limit):
    return await rclone_bytes(key,limit,remote=YUI_REMOTE if model=='yui' else REMOTE)


async def _individual_put(model,local,key,overwrite):
    remote=YUI_REMOTE if model=='yui' else REMOTE
    if not (media_key_valid(key) or re.fullmatch(r'metadata/pending-individual/(mimmi|yui)/[a-f0-9]{64}\.json',key)):
        raise HTTPException(400,'Invalid individual transfer destination')
    child=os.environ.copy()
    child['RCLONE_CONFIG_ARCHIVE_COOKIE']=cookie_header(child.get('RCLONE_CONFIG_ARCHIVE_COOKIE',''))
    try:
        child['RCLONE_CONFIG_ARCHIVE_JSTOKEN']=await owner_upload_state.get(
            child['RCLONE_CONFIG_ARCHIVE_COOKIE'],child.get('RCLONE_CONFIG_ARCHIVE_DOMAIN','https://www.terabox.com'))
    except (WebStateUnavailable,httpx.RequestError) as error:
        reason=str(error) if isinstance(error,WebStateUnavailable) else type(error).__name__
        print('OWNER_UPLOAD_WEB_STATE_UNAVAILABLE',reason,flush=True)
        raise HTTPException(503,'Owner web upload session is unavailable') from None
    process=await asyncio.create_subprocess_exec('rclone','copyto',str(local),remote+'/'+key,
        '--ignore-existing','--timeout=60s','--retries=1',
        stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE,env=child)
    try:
        _,error=await asyncio.wait_for(process.communicate(),timeout=75)
        if process.returncode:
            detail=error.decode('utf-8','replace')
            print('INDIVIDUAL_REMOTE_WRITE_FAILED',safe_remote_diagnostic(detail),flush=True)
            raise HTTPException(503 if 'Failed to login' in detail else 502,'Owner individual-file write failed',
                headers={'X-Archive-Write-Cause':'metadata_visibility'} if metadata_visibility_write_failure(detail) else None)
    except asyncio.TimeoutError:
        raise HTTPException(504,'Owner individual-file write timed out')
    finally:
        if process.returncode is None:process.kill();await process.wait()


async def _sealed_owner_connection():
    for model,remote in (('mimmi',REMOTE),('yui',YUI_REMOTE)):
        data=json.loads(await rclone_bytes('metadata/catalog.json',6_000_000,remote=remote))
        if data.get('model')!=model:raise HTTPException(502,'Owner connection verification failed')
    return seal_storage_state(os.environ.get('RCLONE_CONFIG_ARCHIVE_COOKIE',''),TOKEN)


individual_transfer=install_individual_import(app,_portal_catalog_for,_individual_put,_individual_read,_sealed_owner_connection)
