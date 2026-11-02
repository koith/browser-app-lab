#!/usr/bin/env python3
"""Read-only, bounded verification of the already-deployed gallery gateway.

Never changes the storage session, performs account auth, accepts an unverified
catalog, or treats a provider success-shaped JSON error as a photo collection.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

ORIGIN = "https://mimmi-private-gallery-free.onrender.com"
RETRY_HTTP = {502, 503, 504}
MAX_CATALOG = 6_000_000
MAX_COVER = 1_000_000


def read_gateway(path, max_bytes, *, opener=None, pause=None, attempts=3):
    """Retry only transient transport failures; keep exact target and deadline."""
    if not isinstance(path, str) or not (path in ("/api/catalog", "/api/yui/catalog") or
        re.fullmatch(r"/api/cover/(?:mimmi|yui)/[a-z0-9][a-z0-9-]{1,100}/[0-9]{1,5}\?v=[a-f0-9]{24}", path)):
        raise ValueError("Unapproved gallery read-only path")
    if not 1 <= attempts <= 3 or not 200 <= max_bytes <= MAX_CATALOG:
        raise ValueError("Invalid bounded read")
    if opener is None:
        opener = urllib.request.urlopen
    if pause is None:
        pause = time.sleep
    for attempt in range(1, attempts+1):
        try:
            with opener(ORIGIN+path, timeout=35) as response:
                if getattr(response, 'status', 200) != 200:
                    raise ValueError("Gallery read HTTP status not 200")
                payload = response.read(max_bytes+1)
                if len(payload)>max_bytes:
                    raise ValueError("Gateway payload exceeds permitted bound")
                return payload, response.headers
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_HTTP or attempt == attempts:
                raise RuntimeError("Gallery gateway HTTP read failed: "+str(error.code)) from None
            print("GALLERY_GATEWAY_TRANSIENT_HTTP_RETRY",error.code,attempt,flush=True)
        except (urllib.error.URLError,TimeoutError) as error:
            if attempt == attempts:
                raise RuntimeError("Gallery gateway transport read unavailable") from None
            print("GALLERY_GATEWAY_TRANSIENT_TRANSPORT_RETRY",attempt,flush=True)
        pause(min(2**(attempt-1), 4))
    raise AssertionError("Unreachable gallery read retries")


def verify_catalog(model, raw, minimum):
    try:
        catalog=json.loads(raw)
    except (TypeError,ValueError):
        raise ValueError("Gallery catalog is not JSON") from None
    if (not isinstance(catalog,dict) or catalog.get("model") != model
            or not isinstance(catalog.get("albums"),list)):
        raise ValueError("Gallery catalog model/schema mismatch")
    count=0
    for album in catalog["albums"]:
        if not isinstance(album,dict) or not isinstance(album.get("images"),list):
            raise ValueError("Malformed gallery album")
        count+=len(album["images"])
    if count<minimum:
        raise ValueError("Gallery catalog under published baseline")
    return catalog,count


def verify_cover(raw, headers):
    content_type=headers.get("Content-Type","")
    cache_control=headers.get("Cache-Control","")
    signature=raw.startswith(b"\xff\xd8\xff") or raw.startswith(b"\x89PNG\r\n\x1a\n") or (
        raw.startswith(b"RIFF") and raw[8:12]==b"WEBP")
    if (not 200<len(raw)<=MAX_COVER
            or not content_type.lower().startswith("image/")
            or "max-age=604800" not in cache_control
            or not signature):
        raise ValueError("Gallery cover payload invalid")
    return len(raw)


def verify_models():
    for model,path,minimum in (
        ("yui","/api/yui/catalog",2700),
        ("mimmi","/api/catalog",2600)):
        raw,_=read_gateway(path,MAX_CATALOG)
        catalog,count=verify_catalog(model,raw,minimum)
        print("CONNECTED_GALLERY",model,"albums",len(catalog["albums"]),"images",count,flush=True)
        choice=next(((a,p) for a in catalog["albums"] for p in a["images"]
            if p.get("preview") is True and
            isinstance(p.get("preview_sha256"),str) and
            re.fullmatch("[a-f0-9]{64}",p["preview_sha256"]) and
            isinstance(p.get("number"),int) and 1<=p["number"]<=99999 and
            isinstance(a.get("id"),str) and
            re.fullmatch("[a-z0-9][a-z0-9-]{1,100}",a["id"])),None)
        if choice is None:
            raise ValueError("Gallery has no verified preview")
        album,photo=choice
        cover_path=f"/api/cover/{model}/{album['id']}/{photo['number']}?v={photo['preview_sha256'][:24]}"
        image,headers=read_gateway(cover_path,MAX_COVER)
        size=verify_cover(image,headers)
        print("LIVE_COVER_CACHED",model,"bytes",size,flush=True)


if __name__ == "__main__":
    verify_models()
