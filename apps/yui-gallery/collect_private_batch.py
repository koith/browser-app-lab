#!/usr/bin/env python3
"""Download publicly linked Yui photos as actual unchanged bytes into PRIVATE ZIP files.

Read source URLs only as *acquisition inputs*. Never hotlink them in the gallery,
publish these copies to Pages, evade a 451, or count URLs as saved images.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import re
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
MAX_FILE = 24_000_000
ALLOWED_EXACT = {
    "cdn.imgcup.com", "lh5.ggpht.com", "bis.misskon.com",
    "s.wujituku.com", "cdn1.thismore.fun", "cdn.v2ph.com",
    "pic1.imgdb.cn", "image.huantuji.com", "pbs.twimg.com",
    "pub-376e2756f81341f087a414464f9a25ec.r2.dev",
    "djawaphoto.com", "blog.hacosta.co.jp",
    "img1.gamersky.com", "upload3.inven.co.kr",
    "cdn.imweb.me", "image.ajunews.com", "t1.daumcdn.net",
    "img-jp-a.cdnimg.vip",
    "public-files.gumroad.com", "assets.gumroad.com", "static-2.gumroad.com",
}
ALLOWED_PIXIBB = re.compile(r"(?:imgx\d{3}|images\d{2})\.pixibb\.com\Z", re.I)
BLOCKED_ORIGINS = {"cdn.jliji.com"}
HOST_LOCKS = defaultdict(threading.Lock)
HOST_LAST = defaultdict(float)
PACING_SECONDS = 0.65


def allowed_url(raw: str) -> tuple[bool, str]:
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").lower()
        if host in BLOCKED_ORIGINS:
            return False, "origin_451_not_retried"
        if (url.scheme != "https" or not host
                or url.username or url.password or url.port not in (None, 443)
                or not (host in ALLOWED_EXACT or ALLOWED_PIXIBB.fullmatch(host))):
            return False, "unapproved_public_source"
        return True, host
    except ValueError:
        return False, "invalid_source_url"


def verify_one(item: dict, source: str, timeout_seconds: int = 18) -> tuple[tuple[dict, bytes] | None, dict | None]:
    number = item.get("number")
    if (not isinstance(number, int) or number < 1
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256") or ""))
            or not isinstance(item.get("bytes"), int) or item["bytes"] < 5000 or item["bytes"] > MAX_FILE):
        return None, {"number": number, "reason": "invalid_source_integrity_metadata"}
    alternatives = item.get("alternate_source_urls") or []
    if not isinstance(alternatives, list):
        alternatives = []
    # Unmodified explicitly published alternate URLs are allowed only if they
    # produce the *same expected SHA, bytes and decoded dimensions*.
    # We do not rewrite URL hosts, use proxy access, retry a blocked origin or
    # accept a visually similar but different response as an original.
    urls = list(dict.fromkeys([item.get("url") or ""] +
                              [v for v in alternatives[:4] if isinstance(v, str)]))
    errors = []
    for url in urls:
        approved, host = allowed_url(url)
        if not approved:
            errors.append(host)
            continue
        with HOST_LOCKS[host]:
            delay = PACING_SECONDS - (time.monotonic() - HOST_LAST[host])
            if delay > 0:
                time.sleep(delay)
            HOST_LAST[host] = time.monotonic()
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PersonalImageArchive/1.0)",
                   "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*"}
        if isinstance(source, str) and source.startswith("https://"):
            headers["Referer"] = source
        try:
            with requests.get(url, headers=headers, timeout=(8, timeout_seconds),
                              stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    errors.append("http_" + str(response.status_code))
                    continue
                payload = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    payload.extend(chunk)
                    if len(payload) > MAX_FILE:
                        raise ValueError("source_file_exceeds_limit")
            raw = bytes(payload)
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("sha256_or_byte_length_mismatch")
            with Image.open(io.BytesIO(raw)) as check:
                check.verify()
            with Image.open(io.BytesIO(raw)) as decoded:
                decoded.load()
                if [decoded.width, decoded.height] != [item.get("width"), item.get("height")]:
                    raise ValueError("decoded_dimensions_mismatch")
                ext = {"JPEG": "jpg", "WEBP": "webp", "PNG": "png"}.get(decoded.format)
                if not ext:
                    raise ValueError("image_format_not_supported")
            p = {"number": number, "url": "photos/" + item["sha256"] + "." + ext,
                 "sha256": item["sha256"], "bytes": len(raw),
                 "width": item["width"], "height": item["height"]}
            return (p, raw), None
        except (requests.RequestException, ValueError, OSError) as exc:
            errors.append(str(exc)[:120])
    return None, {"number": number,
                  "reason": errors[-1] if errors else "missing_public_source",
                  "attempts": len(urls)}

def archive(album: dict, out: Path, workers: int = 2, timeout: int = 18, model: str = "yui") -> dict:
    aid = album["id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", aid):
        raise ValueError("invalid_album_id")
    images = album.get("images") or []
    reported = album.get("expected")
    expected = reported if type(reported) is int and reported > 0 else None
    if len(images) > 15000 or len(images) != len({p.get("number") for p in images}):
        raise ValueError("duplicate_or_oversized_album_sequence")
    saved, rejected = [], []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 3))) as pool:
        futures = [pool.submit(verify_one, image, album.get("source") or "", timeout) for image in images]
        for index, future in enumerate(as_completed(futures), 1):
            actual, issue = future.result()
            if actual is not None:
                saved.append(actual)
            else:
                rejected.append(issue)
            if index % 40 == 0 or index == len(images):
                print("CHECKED", aid, index, "of", len(images), "verified", len(saved), flush=True)
    saved.sort(key=lambda record: record[0]["number"])
    complete = expected is not None and len(images) == expected and len(saved) == expected
    manifest = {
        "version": 1, "updated": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "storage": "unchanged physically downloaded public source bytes, private import only",
        "physical_verified_image_count": len(saved),
        "albums": [{
            "id": aid, "title": album.get("title") or aid,
            "expected": expected, "status": "complete_downloaded" if complete else "partial_downloaded",
            "images": [p for p, _ in saved],
        }] if saved else [],
    }
    report = {"album": aid, "source_indexed": len(images), "expected": expected,
              "physically_saved": len(saved),
              "distinct_sha256": len({p["sha256"] for p, _ in saved}),
              "failed": sorted(rejected, key=lambda p: p.get("number") or 0),
              "complete": complete}
    if saved:
        path = out / (aid + "-private-import.zip")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as zip_out:
            zip_out.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            written = set()
            for p, raw in saved:
                if p["sha256"] in written:
                    continue
                zip_out.writestr(p["url"], raw)
                written.add(p["sha256"])
        with zipfile.ZipFile(path) as check:
            for p, _ in saved:
                raw = check.read(p["url"])
                assert len(raw) == p["bytes"] and hashlib.sha256(raw).hexdigest() == p["sha256"]
        report["private_zip_bytes"] = path.stat().st_size
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--albums", required=True, help="Comma-separated exact album IDs, never wildcard")
    parser.add_argument("--out", default="/tmp/yui-private-photo-batches")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=18)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    indexed = json.loads((ROOT / "additional-source-albums.json").read_text(encoding="utf-8"))
    albums_by_id = {a["id"]: a for a in indexed["albums"]}
    targets = [x.strip() for x in args.albums.split(",") if x.strip()]
    if not targets or len(targets) != len(set(targets)) or any(x not in albums_by_id for x in targets):
        parser.error("Only unique IDs already present in the verified source index are accepted")
    results = []
    for aid in targets:
        results.append(archive(albums_by_id[aid], out, args.workers, args.timeout))
    audit = {"generated_at": datetime.now(timezone.utc).isoformat(), "real_files_only": True,
             "albums": results, "verified_saved_photo_rows": sum(x["physically_saved"] for x in results),
             "missing_rows": sum(x["source_indexed"] - x["physically_saved"] for x in results)}
    (out / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PRIVATE_ARCHIVE_PHYSICAL_BYTES_SAVED", audit["verified_saved_photo_rows"],
          "missing", audit["missing_rows"], flush=True)


if __name__ == "__main__":
    main()
