#!/usr/bin/env python3
"""Read-only live user-facing test of all 56 already-owned incident originals.

This checks the ACTUAL deployed Render gateway, not a staged FastAPI instance,
a metadata-only owner index, cached preview or the GitHub runner's TeraBox login.
No secrets, photo publication, filesystem archive, or new collection.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image

BASE = "https://mimmi-private-gallery-free.onrender.com"
ORIGIN = "https://koith.github.io"
TARGET = {
    "mimmi": (("djawa-janus-scary-lantern-night", 15),
              ("mimmi-indie-sana-sopmod2-2019", 7)),
    "yui": (("djawa-privaty-public-samples", 30),
            ("yui-chinokun-illustar-2026-public", 4)),
}
MAX_IMAGE_BYTES = 12 * 1024 * 1024
VALID_SHA = re.compile(r"[0-9a-f]{64}\Z")


def get(path, limit):
    request = Request(BASE + path, headers={
        "Origin": ORIGIN,
        "Accept": "application/json, image/*",
        "Cache-Control": "no-cache",
        "User-Agent": "Gallery-Incident-Real-Original-SHA-Readback/1",
    })
    try:
        with urlopen(request, timeout=38) as reply:
            if reply.status != 200:
                raise ValueError("HTTP " + str(reply.status))
            return dict(reply.headers), reply.read(limit + 1)
    except HTTPError as exc:
        raise ValueError("HTTP " + str(exc.code)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError("network unavailable") from exc


def work(model, album_id, photo):
    number = photo["number"]
    expected_hash = photo["sha256"]
    expected_size = photo["bytes"]
    if (type(number) is not int or not 1 <= number <= 10000
        or type(expected_size) is not int
        or not 0 < expected_size <= MAX_IMAGE_BYTES
        or not isinstance(expected_hash, str)
        or not VALID_SHA.fullmatch(expected_hash)):
        raise ValueError("invalid archived SHA/size/number")
    base_route = "/api/yui" if model == "yui" else "/api"
    path = (base_route + "/media/" + quote(album_id, safe="") + "/" +
            str(number) + "/original?v=" + expected_hash)
    headers, payload = get(path, MAX_IMAGE_BYTES)
    if len(payload) != expected_size:
        raise ValueError("original byte length mismatch")
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise ValueError("original SHA-256 mismatch")
    if not headers.get("Content-Type", "").lower().startswith("image/"):
        raise ValueError("original not returned as image")
    if headers.get("Access-Control-Allow-Origin") != ORIGIN:
        raise ValueError("browser CORS origin not permitted")
    try:
        with Image.open(io.BytesIO(payload)) as im:
            im.load()
            dimensions = im.size
    except Exception as exc:
        raise ValueError("image pixel decode failed") from exc
    if (dimensions != (photo.get("width"), photo.get("height"))):
        raise ValueError("image dimensions differ from archived manifest")
    return len(payload)


def main(model):
    route = "/api/yui/catalog" if model == "yui" else "/api/catalog"
    _, data = get(route, 5 * 1024 * 1024)
    catalog = json.loads(data)
    if catalog.get("schema_version") != 1 or catalog.get("model") != model:
        raise ValueError("unexpected owner model/schema")
    albums = catalog.get("albums")
    if not isinstance(albums, list):
        raise ValueError("missing owner catalog albums")
    matches = []
    for album_id, count in TARGET[model]:
        found = [item for item in albums if item.get("id") == album_id]
        if len(found) != 1 or not isinstance(found[0].get("images"), list):
            raise ValueError(model + " exact target album missing/duplicated: " + album_id)
        images = found[0]["images"]
        if len(images) != count or len({p.get("number") for p in images}) != count:
            raise ValueError(model + " wrong real incident album count: " + album_id)
        matches.extend((album_id, photo) for photo in images)
    errors = []
    total_bytes = 0
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(work, model, aid, photo): (aid, photo["number"])
                for aid, photo in matches}
        for job in as_completed(jobs):
            album_id, number = jobs[job]
            try:
                total_bytes += job.result()
            except Exception as exc:
                # No bearer token, cookie, secret, remote path or raw response body.
                errors.append({"album": album_id, "number": number, "reason": str(exc)[:110]})
    result = {
        "model": model, "expected": len(matches),
        "http_200_independent_sha_and_pixel_pass": len(matches)-len(errors),
        "read_bytes": total_bytes, "elapsed_seconds": round(time.monotonic()-start, 1),
        "failures": errors[:20], "fail_count": len(errors),
        "durable_restart_verified": False, "real_iphone_hardware_verified": False,
    }
    print("LIVE_56_OWNER_ORIGINAL_ACCEPTANCE", json.dumps(result, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=("mimmi", "yui"), required=True)
    main(p.parse_args().model)
