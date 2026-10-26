"""Private media gateway over TeraBox rclone backend.

Sensitive storage cookies stay in server env, never in the GitHub Pages client.
Every user API request requires the private gallery bearer token. Full size media
is proxied on-demand, so TeraBox's unofficial backend can be slow.

The container does not keep originals on its ephemeral disk. They live remotely.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from pathlib import PurePosixPath
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Yui Private Archive Media Gateway", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://koith.github.io", "http://localhost:8765"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition", "X-Archive-Source"],
)
REMOTE = os.environ.get("ARCHIVE_REMOTE", "archive:YuiArchive").rstrip("/")
TOKEN = os.environ.get("GALLERY_ACCESS_TOKEN", "")
COOKIE = os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE", "")
_cache = {"time": 0.0, "catalog": None}
_cache_lock = asyncio.Lock()


def media_key_valid(key: str) -> bool:
    if not key or len(key) > 700 or "\\" in key or "%" in key:
        return False
    if key.startswith("/") or "\x00" in key:
        return False
    parts = PurePosixPath(key).parts
    return bool(parts) and all(p not in ("..", ".", "") for p in parts) and parts[0] in ("originals", "previews")


async def authenticated(authorization: str | None = Header(default=None)):
    if not TOKEN or not COOKIE:
        raise HTTPException(status_code=503, detail="Cloud gateway is not connected")
    expected = "Bearer " + TOKEN
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Authorization required", headers={"WWW-Authenticate": "Bearer"})


async def rclone_bytes(path: str, limit: int) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "rclone", "cat", f"{REMOTE}/{path}", "--timeout=50s", "--retries=2",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        result = await asyncio.wait_for(proc.stdout.read(limit + 1), timeout=115)
        if len(result) > limit:
            proc.kill()
            await proc.wait()
            raise HTTPException(status_code=413, detail="Remote asset larger than supported")
        rc = await asyncio.wait_for(proc.wait(), timeout=15)
        if rc:
            err = (await proc.stderr.read(3000)).decode("utf-8", errors="replace")
            print("RCLONE_REMOTE_READ_FAILED", path, err[:300], flush=True)
            raise HTTPException(status_code=502, detail="Cloud media unavailable")
        return result
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="Cloud read timed out")
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def get_catalog():
    if _cache["catalog"] and (time.time()-_cache["time"]) < 180:
        return _cache["catalog"]
    async with _cache_lock:
        if _cache["catalog"] and (time.time()-_cache["time"]) < 180:
            return _cache["catalog"]
        blob = await rclone_bytes("metadata/catalog.json", 4_000_000)
        catalog = json.loads(blob)
        if catalog.get("schema_version") != 1:
            raise HTTPException(status_code=502, detail="Unsupported catalogue version")
        _cache["catalog"] = catalog
        _cache["time"] = time.time()
        return catalog


@app.get("/api/health")
async def health():
    # Never disclose credentials or confirm account identity through health.
    return {"service": "Yui private archive", "configured": bool(TOKEN and COOKIE),
            "data_connected": bool(_cache["catalog"])}


@app.get("/api/catalog", dependencies=[Depends(authenticated)])
async def catalog():
    return await get_catalog()


@app.get("/api/media/{album_id}/{image_num}/{kind}", dependencies=[Depends(authenticated)])
async def media(album_id: str, image_num: int, kind: str, download: bool = Query(False)):
    if not (2 <= len(album_id) <= 100 and album_id.replace("-", "").isalnum()) or image_num < 1:
        raise HTTPException(status_code=400, detail="Invalid media ID")
    if kind not in ("preview", "original"):
        raise HTTPException(status_code=404, detail="Unknown media type")
    catalog = await get_catalog()
    album = next((a for a in catalog["albums"] if a["id"] == album_id), None)
    if album is None:
        raise HTTPException(status_code=404, detail="Unknown album")
    img = next((i for i in album["images"] if i["number"] == image_num), None)
    if img is None:
        raise HTTPException(status_code=404, detail="Unknown photo")
    key = img["preview" if kind == "preview" else "key"]
    if not media_key_valid(key):
        raise HTTPException(status_code=500, detail="Manifest contains unsafe path")
    # The exact media key is read from a verified private manifest, not URL input.
    expected_prefix = "previews" if kind == "preview" else "originals"
    if not key.startswith(expected_prefix + "/" + album_id + "/"):
        raise HTTPException(status_code=500, detail="Manifest media path mismatch")
    limit = 5_000_000 if kind == "preview" else 140_000_000
    blob = await rclone_bytes(key,limit)
    extension = key.rsplit(".", 1)[-1].lower()
    content_type = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp","avif":"image/avif"}.get(extension,"application/octet-stream")
    headers={"Cache-Control":"private, max-age=600","X-Content-Type-Options":"nosniff"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{album_id}-{image_num:04d}.{extension}"'
    return StreamingResponse(iter([blob]),media_type=content_type,headers=headers)
