#!/usr/bin/env python3
"""Validate private R2 previews before upload and by full remote readback.

Never store originals or publish public URLs in the R2 cache. Readback is
mandatory: size-only comparison cannot detect equal-length corruption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from verify_remote import remote_digest

MAX_CACHE_BYTES = 8_000_000_000  # conservative storage guard, NOT a billing cap
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def check_previews(stage: Path, max_bytes: int = MAX_CACHE_BYTES) -> list[tuple[str, int, str]]:
    stage = stage.resolve()
    catalog = json.loads((stage / "metadata/catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1 or not catalog.get("albums"):
        raise ValueError("Invalid or empty catalogue")
    files: list[tuple[str, int, str]] = []
    keys = set()
    total = 0
    for album in catalog["albums"]:
        aid = album["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", aid):
            raise ValueError("Unsafe album ID")
        for image in album["images"]:
            key, size, sha = image["preview"], image["preview_bytes"], image["preview_sha256"]
            if (not isinstance(key, str)
                    or not key.startswith("previews/" + aid + "/")
                    or ".." in Path(key).parts or "\\" in key or "%" in key
                    or key in keys or type(size) is not int or size < 1
                    or not isinstance(sha, str) or not SHA256.fullmatch(sha)):
                raise ValueError("Unsafe or duplicate preview entry")
            local = (stage / key).resolve()
            if not local.is_relative_to(stage) or not local.is_file():
                raise ValueError("Missing preview on disk")
            if local.stat().st_size != size:
                raise ValueError("Preview size mismatch")
            digest = hashlib.sha256()
            with local.open("rb") as src:
                while chunk := src.read(256 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != sha:
                raise ValueError("Preview SHA256 mismatch")
            files.append((key, size, sha))
            keys.add(key)
            total += size
            if total > max_bytes:
                raise ValueError("R2 cache exceeds configured storage budget")
    if not files:
        raise ValueError("No previews to cache")
    print("R2_LOCAL_PREVIEWS_VERIFIED", len(files), total, flush=True)
    return files


def verify_remote_previews(stage: Path, remote: str, max_bytes: int = MAX_CACHE_BYTES) -> dict:
    if not remote.startswith("previewcache:"):
        raise ValueError("R2 remote must use the dedicated previewcache: backend")
    specs = check_previews(stage, max_bytes)
    checked = []
    for key, size, digest in specs:
        observed_size, observed_hash = remote_digest(remote, key, limit=size + 1)
        if observed_size != size or observed_hash != digest:
            raise ValueError("R2 preview byte/hash mismatch: " + key)
        checked.append({"key": key, "bytes": size, "sha256": digest})
    report = {
        "schema_version": 1,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "cloudflare-r2-private-preview-cache",
        "method": "rclone cat all previews and verify SHA256",
        "previews": len(checked),
        "bytes": sum(x["bytes"] for x in checked),
        "objects": checked,
    }
    dest = stage / "metadata/preview-cache-verification.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("R2_REMOTE_PREVIEWS_SHA256_VERIFIED", report["previews"], report["bytes"], flush=True)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=Path)
    ap.add_argument("--verify-remote", default=None, metavar="RCLONE_REMOTE")
    ap.add_argument("--max-bytes", type=int, default=MAX_CACHE_BYTES)
    args = ap.parse_args()
    if args.max_bytes < 1 or args.max_bytes > MAX_CACHE_BYTES:
        ap.error("Cache budget must be between 1 and 8,000,000,000 bytes")
    if args.verify_remote:
        verify_remote_previews(args.stage, args.verify_remote, args.max_bytes)
    else:
        check_previews(args.stage, args.max_bytes)


if __name__ == "__main__":
    main()
