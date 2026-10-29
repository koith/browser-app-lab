#!/usr/bin/env python3
"""Bulk-archive creator-owned, publicly visible social media photographs.

gallery-dl provides ordinary-site pagination. This process retains only
real decoded image bytes, rejects account mismatches in available metadata,
deduplicates against the owner's existing SHA-backed private catalog, and
exports numbered ZIPs understood by the existing private TeraBox importer.

This is a *separate* acquisition path from PixiBB, V2PH, Xiutu, and HTML
photographer crawlers. No logins, paid content, proxy or geo restrictions bypass,
third-party repost galleries, public Pages photo publication, or fake inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parent
EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,100}\Z")
MAX_BYTES = 35 * 1024 * 1024
ZIP_PHOTOS = 160
ZIP_MAX_BYTES = 100 * 1024 * 1024


def sources_for(config: dict, model: str) -> list[dict]:
    if config.get("schema_version") != 1 or model not in ("yui", "mimmi"):
        raise ValueError("Invalid sources or model")
    output = config[model]
    if not isinstance(output, list) or not output:
        raise ValueError("No public creator source entries")
    ids = set()
    for item in output:
        aid, url, account, kind = (item.get(k, "") for k in ("id", "url", "account", "kind"))
        if not isinstance(aid, str) or not ID.fullmatch(aid) or aid in ids:
            raise ValueError("Duplicate or unsafe album ID")
        ids.add(aid)
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        allowed = ((kind == "twitter" and host == "x.com"
                    and parsed.path == "/" + account + "/media") or
                   (kind == "instagram" and host == "www.instagram.com"
                    and parsed.path == "/" + account + "/"))
        if (not allowed or parsed.scheme != "https" or parsed.username
                or parsed.password or parsed.port or parsed.query or parsed.fragment
                or not re.fullmatch(r"[a-zA-Z0-9_]{3,30}", account)):
            raise ValueError("Unsafe or non-creator timeline URL")
    return output


def previous_photos(catalog: dict, model: str):
    if (catalog.get("schema_version") != 1 or catalog.get("model") != model
            or not isinstance(catalog.get("albums"), list)):
        raise ValueError("Private SHA-verified catalog missing or wrong model")
    hashes = set()
    next_numbers = {}
    for album in catalog["albums"]:
        if not ID.fullmatch(album["id"]):
            raise ValueError("Unsafe private album identifier")
        numbers = []
        for p in album["images"]:
            sha = p.get("sha256", "")
            if not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise ValueError("Invalid private SHA")
            hashes.add(sha)
            n = p.get("number")
            if type(n) is not int or n < 1:
                raise ValueError("Invalid private photo number")
            numbers.append(n)
        next_numbers[album["id"]] = max(numbers, default=0)
    return hashes, next_numbers


def verify_bytes(path: Path):
    if path.stat().st_size < 1024 or path.stat().st_size > MAX_BYTES:
        raise ValueError("Out-of-range file size")
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        fmt = EXT.get(image.format)
        if not fmt or min(image.size) < 200:
            raise ValueError("Not a supported full image")
        return raw, hashlib.sha256(raw).hexdigest(), image.width, image.height, fmt


def account_from_metadata(path: Path):
    """Return known account when the extractor emits an author identity.

    A missing identity is inconclusive; never infer identity from image pixels.
    Retweets and quoted tweets are separately disabled in extractor config.
    """
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return None
    try:
        d = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    author = d.get("author")
    if isinstance(author, dict):
        for key in ("name", "screen_name", "username"):
            if isinstance(author.get(key), str) and author[key]:
                return author[key].lstrip("@")
    for parent in (d.get("user"), d.get("owner")):
        if isinstance(parent, dict):
            for key in ("screen_name", "username"):
                if isinstance(parent.get(key), str) and parent[key]:
                    return parent[key].lstrip("@")
    for key in ("username", "screen_name"):
        if isinstance(d.get(key), str) and d[key]:
            return d[key].lstrip("@")
    return None


def zip_batch(out: Path, model: str, source: dict, batch: list, batch_index: int):
    if not batch:
        return None
    album = {"id": source["id"], "title": source["title"],
             "expected": None, "images": [p for p, _ in batch]}
    manifest = {"schema_version": 1, "model": model,
                "physical_verified_image_count": len(batch), "albums": [album]}
    dest = out / (source["id"] + "-" + str(batch_index).zfill(4) + "-private-import.zip")
    with ZipFile(dest, "w", compression=ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for p, raw in batch:
            archive.writestr(p["url"], raw)
    with ZipFile(dest) as archive:
        for p, _ in batch:
            raw = archive.read(p["url"])
            if len(raw) != p["bytes"] or hashlib.sha256(raw).hexdigest() != p["sha256"]:
                raise ValueError("Private social ZIP physical SHA mismatch")
    return dest


def package_source(directory: Path, out: Path, model: str,
                   source: dict, existing: set, numbers: dict):
    files = sorted(p for p in directory.rglob("*") if p.is_file()
                   and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    count = 0
    rejected = defaultdict(int)
    batches = []
    current, size = [], 0
    for path in files:
        author = account_from_metadata(path)
        if author and author.casefold() != source["account"].casefold():
            rejected["different_account"] += 1
            continue
        try:
            raw, digest, width, height, ext = verify_bytes(path)
        except (OSError, ValueError):
            rejected["bad_file"] += 1
            continue
        if digest in existing:
            rejected["already_sha_archived"] += 1
            continue
        n = numbers.get(source["id"], 0) + 1
        if n > 20000:
            rejected["number_limit"] += 1
            break
        numbers[source["id"]] = n
        existing.add(digest)
        row = {"number": n, "url": "photos/" + digest + "." + ext,
               "sha256": digest, "bytes": len(raw),
               "width": width, "height": height}
        if current and (len(current) >= ZIP_PHOTOS or size + len(raw) > ZIP_MAX_BYTES):
            batches.append(zip_batch(out, model, source, current, len(batches) + 1))
            current, size = [], 0
        current.append((row, raw))
        size += len(raw)
        count += 1
    if current:
        batches.append(zip_batch(out, model, source, current, len(batches) + 1))
    return {"source": source["id"], "image_files_considered": len(files),
            "new_verified_real_images": count,
            "rejected_or_previously_saved": dict(rejected),
            "private_zip_parts": len(batches)}


def downloader_config(directory: Path) -> Path:
    config = {
        "extractor": {
            "twitter": {"retweets": False, "quoted": False, "videos": False,
                        "text-tweets": False, "include": ["media"],
                        "timeline": {"strategy": "media"}},
            "instagram": {"videos": False}
        },
        "downloader": {"mtime": False}
    }
    dest = directory / "gallery-dl-public-only.json"
    dest.write_text(json.dumps(config), encoding="utf-8")
    return dest


def collect(model: str, config: dict, previous: dict, out: Path,
            runner=None):
    sources = sources_for(config, model)
    old, numbers = previous_photos(previous, model)
    out.mkdir(parents=True, exist_ok=True)
    stage = out / "download-stage"
    stage.mkdir(exist_ok=True)
    settings = downloader_config(out)
    report = []
    for s in sources:
        folder = stage / s["id"]
        folder.mkdir(exist_ok=True)
        command = [sys.executable, "-m", "gallery_dl", "--config-ignore",
                   "--config-json", str(settings), "--no-input",
                   "--directory", str(folder), "--write-metadata",
                   "--sleep-request", "0.7", "--sleep-429", "exp=60",
                   "--sleep", "0.5", "--retries", "3", "--http-timeout", "35",
                   s["url"]]
        status = "unknown"
        try:
            if runner:
                code = runner(command, s, folder)
            else:
                process = subprocess.run(command, capture_output=True,
                                         text=True, timeout=2700, check=False)
                code = process.returncode
            status = "completed" if code == 0 else "source_unavailable_or_partial"
        except (OSError, subprocess.TimeoutExpired):
            status = "source_unavailable_or_partial"
        details = package_source(folder, out, model, s, old, numbers)
        details["extractor_status"] = status
        report.append(details)
        print("GALLERY_BULK_SOCIAL_REAL_PHOTOS",
              json.dumps(details, ensure_ascii=False), flush=True)
    results = {"model": model, "generated_at": datetime.now(timezone.utc).isoformat(),
               "owner_catalog_sha_position_dedup": True,
               "actual_new_physical_images": sum(r["new_verified_real_images"] for r in report),
               "real_private_import_zip_parts": sum(r["private_zip_parts"] for r in report),
               "sources": report,
               "notes": "Only ZIP-contained decoded SHA-verified photo bytes are acquired. No public gallery count is increased until authenticated remote import verifies readback."}
    (out / "social-bulk-audit.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GALLERY_BULK_SOCIAL_TOTAL", json.dumps({
        "model": model, "new_real_images": results["actual_new_physical_images"],
        "parts": results["real_private_import_zip_parts"]}), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["yui", "mimmi"], required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=ROOT / "public_social_bulk_sources.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.model, json.loads(args.sources.read_text(encoding="utf-8")),
            json.loads(args.previous.read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()
