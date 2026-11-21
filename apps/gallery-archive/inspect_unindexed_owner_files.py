#!/usr/bin/env python3
"""Read and decode existing unindexed owner objects, without changing storage.

Reports aggregate-only evidence. Never uploads, logs keys, hashes, account
details, file names, signed source URLs or any image bytes. A novel SHA is a
candidate, NOT proven to be a new photo/cut or eligible for publication.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from PIL import Image, ImageFile, UnidentifiedImageError

from qa_existing_owner_exact_file import read_existing

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".tif", ".tiff")
VALID_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
Image.MAX_IMAGE_PIXELS = 50_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = False


def candidates(listing, catalog, maximum):
    if not isinstance(listing, list) or maximum < 1:
        raise ValueError("BAD_OWNER_LIST_OR_BUDGET")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("albums"), list):
        raise ValueError("BAD_OWNER_CATALOG")
    known = {a["id"] for a in catalog["albums"]}
    occupied = {p["key"] for a in catalog["albums"] for p in a["images"]}
    gathered = []
    for row in listing:
        if not isinstance(row, dict):
            continue
        key, size = row.get("Path"), row.get("Size")
        if not isinstance(key, str) or not key.startswith("originals/"):
            continue
        if key in occupied or not key.casefold().endswith(EXTS):
            continue
        parts = key.split("/")
        if (len(parts) != 3 or not VALID_ID.fullmatch(parts[1])
                or not parts[2] or parts[2] in (".", "..")
                or any(x in key for x in ("\\", "\n", "\r", "\0"))
                or type(size) is not int or size < 200 or size > 10_000_000):
            continue
        gathered.append((key, size, parts[1] in known, parts[1]))
    # Investigate unregistered album IDs first, then existing album assets.
    gathered.sort(key=lambda r: (r[2], -r[1], r[3]))
    return gathered[:maximum], len(gathered)


def summarize(model, listing, catalog, saved, remote, budget):
    if model not in ("mimmi", "yui") or catalog.get("model") != model:
        raise ValueError("OWNER_MODEL_MISMATCH")
    queue, eligible = candidates(listing, catalog, budget)
    hashes = {p.get("sha256") for a in catalog["albums"] for p in a["images"]}
    for album in saved.get("albums", []):
        hashes.update(p.get("sha256") for p in album.get("images", []))
    seen = set()
    stat = Counter()
    by_work = Counter()
    failures = Counter()
    sizes = Counter()
    dims = Counter()
    with tempfile.TemporaryDirectory(prefix="gallery-owner-inspect-") as folder:
        target = Path(folder) / "owner-image"
        env = os.environ.copy()
        for key, declared_size, is_known, album_id in queue:
            stat["attempted"] += 1
            target.unlink(missing_ok=True)
            ok, method = read_existing(remote, key, target, env)
            if not ok:
                failures[method] += 1
                continue
            try:
                if target.stat().st_size != declared_size:
                    failures["storage_size_changed"] += 1
                    continue
                with target.open("rb") as source:
                    raw_hash = hashlib.file_digest(source, "sha256").hexdigest()
                with Image.open(target) as image:
                    if image.format not in ("JPEG", "PNG", "WEBP", "TIFF"):
                        raise ValueError("UNSUPPORTED_DECODE_FORMAT")
                    image.load()
                    w, h = image.size
                    if w < 160 or h < 160 or w * h > 50_000_000:
                        raise ValueError("INVALID_IMAGE_DIMENSIONS")
                stat["valid_decoded"] += 1
                sizes["under_500kb" if declared_size < 500_000 else
                      "500kb_to_2mb" if declared_size < 2_000_000 else
                      "at_least_2mb"] += 1
                dims["under_2mp" if w*h < 2_000_000 else
                     "2_to_8mp" if w*h < 8_000_000 else
                     "at_least_8mp"] += 1
                if raw_hash in hashes:
                    stat["exact_sha_already_indexed"] += 1
                elif raw_hash in seen:
                    stat["duplicate_sha_within_unindexed"] += 1
                else:
                    stat["sha_not_in_known_indexes"] += 1
                    if is_known:
                        stat["known_album_novel_sha"] += 1
                        by_work[album_id] += 1
                    else:
                        stat["unmapped_album_novel_sha"] += 1
                seen.add(raw_hash)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
                failures["invalid_or_undecodable"] += 1
            finally:
                target.unlink(missing_ok=True)
    return {
        "model": model,
        "unindexed_candidate_scope": "existing_originals_prefix_only",
        "eligible_in_storage_listing": eligible,
        "selected_to_inspect": len(queue),
        "metrics": dict(sorted(stat.items())),
        "image_byte_sizes": dict(sorted(sizes.items())),
        "decoded_resolution": dict(sorted(dims.items())),
        "read_failures": dict(sorted(failures.items())),
        "known_album_candidate_counts": dict(by_work.most_common(25)),
        "no_file_modifications": True,
        "novel_shas_not_proven_distinct_photos": True,
        "actual_new_photos_published": 0
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=("mimmi", "yui"), required=True)
    p.add_argument("--listing", required=True, type=Path)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--saved", required=True, type=Path)
    p.add_argument("--max", type=int, default=100)
    a = p.parse_args()
    if not 1 <= a.max <= 700:
        raise SystemExit("BOUNDED_READ_LIMIT_REQUIRED")
    remote = "archive:MimmiArchive" if a.model == "mimmi" else "archive:YuiArchive"
    catalog=json.loads(a.catalog.read_text(encoding="utf-8"))
    listing=json.loads(a.listing.read_text(encoding="utf-8"))
    saved=json.loads(a.saved.read_text(encoding="utf-8"))
    report=summarize(a.model, listing, catalog, saved, remote, a.max)
    print("OWNER_UNINDEXED_PHYSICAL_READ_REPORT", json.dumps(
        report, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
