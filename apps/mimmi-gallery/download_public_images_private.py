#!/usr/bin/env python3
"""Save individually SHA-verified, openly reachable Mimmi images into PRIVATE storage.

No ZIP files, re-encoding, scraping login sessions, paid content access, or upload
to public GitHub Pages. This is a private source-photo cache, not a commercial
photobook downloader. The manifest must come from the verified public crawler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
HOSTS = {"djawaphoto.com", "www.djawaphoto.com", "cdn.v2ph.com"}
EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
MAX_BYTES = 30_000_000
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; PersonalMimmiGalleryArchive/1.0)",
    "Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=.7",
})

def permitted(url):
    try:
        p = urlsplit(url)
        h=p.hostname or ""
        pixibb=bool(re.fullmatch(r"(?:imgx[0-9]{2,4}|images[0-9]{1,4}|img|cdn|files)[.]pixibb[.]com",h))
        if not (p.scheme=="https" and (h in HOSTS or pixibb)
                and not p.username and not p.password and not p.port
                and not p.fragment and Path(p.path).suffix.lower() in EXT):
            return False
        if h=="cdn.v2ph.com":return p.path.startswith("/photos/")
        if h in ("djawaphoto.com","www.djawaphoto.com"):
            return p.path.startswith("/wp-content/uploads/")
        return pixibb and p.path.startswith("/")
    except (ValueError, TypeError, AttributeError):
        return False

def digest_of(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def fetch_verified(url, sha256, byte_count):
    if not permitted(url) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Unapproved URL or missing SHA-256 evidence")
    if not isinstance(byte_count, int) or not 5000 <= byte_count <= MAX_BYTES:
        raise ValueError("Invalid expected source byte count")
    with SESSION.get(url, timeout=(10, 40), stream=True, allow_redirects=False) as r:
        r.raise_for_status()
        if r.status_code != 200:
            raise ValueError("Source moved or redirected; no redirect bypass")
        pieces = bytearray()
        for block in r.iter_content(65536):
            pieces.extend(block)
            if len(pieces) > MAX_BYTES:
                raise ValueError("Oversized photo")
    raw = bytes(pieces)
    if len(raw) != byte_count:
        raise ValueError("Original byte size differs from previously verified bytes")
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("Source changed since verification; no substitution allowed")
    with Image.open(BytesIO(raw)) as image:
        image.verify()
    with Image.open(BytesIO(raw)) as image:
        if min(image.size) < 250:
            raise ValueError("Source photo too small")
    return raw

def store_one(photo, album_id, output):
    sha = photo["sha256"]
    url = photo["url"]
    number = photo["number"]
    if not re.fullmatch(r"[a-z0-9-]{2,110}", album_id):
        raise ValueError("Invalid album id")
    if not isinstance(number, int) or not 1 <= number <= 99999:
        raise ValueError("Invalid photo number")
    if not permitted(url):
        raise ValueError("Source host not on verified-public allowlist")
    suffix = Path(urlsplit(url).path).suffix.lower()
    album = output / "albums" / album_id
    album.mkdir(parents=True, exist_ok=True, mode=0o700)
    file = album / f"{number:04d}-{sha[:20]}{suffix}"
    if file.is_file() and file.stat().st_size == photo["bytes"] and digest_of(file) == sha:
        return str(file.relative_to(output)), False
    raw = fetch_verified(url, sha, photo["bytes"])
    # Stage in the same directory, atomically publish only complete verified bytes.
    handle, temp = tempfile.mkstemp(prefix=".incoming-", dir=album)
    try:
        with os.fdopen(handle, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return str(file.relative_to(output)), True

def save(output, album_filter="", limit=0, delay=0.6):
    output = Path(output).expanduser().resolve()
    repo_root = ROOT.parent.parent
    if output == repo_root or repo_root in output.parents or not output.is_absolute():
        raise ValueError("Private image destination must be outside the entire public GitHub Pages repository")
    manifest = json.loads((ROOT / "source-viewer-albums.json").read_text(encoding="utf-8"))
    if manifest.get("model") != "mimmi" or not manifest.get("source_link_only"):
        raise ValueError("Expected an external-source-only Mimmi manifest")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    rows = []
    errors = []
    saved = existing = 0
    exhausted = False
    for album in manifest["albums"]:
        if album_filter and album_filter.casefold() not in (
            album["id"].casefold(), album["title"].casefold()):
            continue
        for photo in album.get("images", []):
            if limit and saved + existing >= limit:
                exhausted = True
                break
            try:
                rel, new = store_one(photo, album["id"], output)
                rows.append({"album_id": album["id"], "album_title": album["title"],
                             "number": photo["number"], "sha256": photo["sha256"],
                             "bytes": photo["bytes"], "path": rel, "source": photo["url"]})
                if new:
                    saved += 1
                    time.sleep(delay)
                else:
                    existing += 1
            except (ValueError, OSError, requests.RequestException) as error:
                errors.append({"album_id": album["id"], "number": photo.get("number"),
                               "error": type(error).__name__ + ": " + str(error)[:170]})
        if exhausted:
            break
    report = {"model": "mimmi", "kind": "individual_private_original_bytes",
              "bytes_are_reencoded": False, "new_saved": saved,
              "previously_verified_on_disk": existing, "failed": len(errors),
              "files": rows, "errors": errors}
    dest = output / "private-archive-index.json"
    staging = output / ".private-archive-index.tmp"
    staging.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    staging.replace(dest)
    print(json.dumps({k: report[k] for k in ("new_saved", "previously_verified_on_disk", "failed")},
                     ensure_ascii=False))
    print("PRIVATE_ARCHIVE_DIRECTORY", output)
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Private persistent directory OUTSIDE the GitHub Pages repository")
    parser.add_argument("--album", default="", help="Optional exact album id/title")
    parser.add_argument("--limit", type=int, default=0, help="0 = all individually verified public photos")
    parser.add_argument("--delay", type=float, default=0.6)
    args = parser.parse_args()
    if args.limit < 0 or args.delay < 0.3:
        parser.error("Limit cannot be negative and delay must be at least 0.3s")
    save(args.output_dir, args.album, args.limit, args.delay)
