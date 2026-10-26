#!/usr/bin/env python3
"""Prove that every privately uploaded image can be read back byte-for-byte.

Unlike rclone check --size-only, this hashes the remote bytes returned by
rclone cat. Do not publish a catalogue until this verification succeeds.
Credentials stay in the rclone process environment; none are logged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def remote_digest(remote: str, key: str, limit: int) -> tuple[int, str]:
    """Stream remote bytes to a scratch file, then hash with bounded RAM."""
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                ["rclone", "cat", f"{remote.rstrip('/')}/{key}",
                 "--timeout=50s", "--retries=2"],
                stdout=output, stderr=subprocess.DEVNULL, timeout=130,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(f"Remote read failed ({result.returncode}): {key}")
            length = output.tell()
            if length > limit:
                raise ValueError(f"Remote asset larger than allowed: {key}")
            output.seek(0)
            digest = hashlib.sha256()
            while chunk := output.read(256 * 1024):
                digest.update(chunk)
            return length, digest.hexdigest()
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Remote read timed out: {key}") from error


def file_specs(catalog: dict) -> list[tuple[str, int, str]]:
    specs = []
    keys = set()
    for album in catalog["albums"]:
        aid = album["id"]
        for image in album["images"]:
            for kind, key_field, size_field, sha_field in (
                ("original", "key", "bytes", "sha256"),
                ("preview", "preview", "preview_bytes", "preview_sha256"),
            ):
                key = image[key_field]
                size = image[size_field]
                digest = image[sha_field]
                prefix = ("originals" if kind == "original" else "previews") + "/" + aid + "/"
                if (not isinstance(key, str) or not key.startswith(prefix)
                        or ".." in Path(key).parts or "\\" in key or key in keys
                        or type(size) is not int or size < 1
                        or not isinstance(digest, str) or not SHA256.fullmatch(digest)):
                    raise ValueError(f"Invalid or duplicate manifest entry: {kind} / {aid}")
                keys.add(key)
                specs.append((key, size, digest))
    if not specs:
        raise ValueError("No images to verify")
    return specs


def verify_media(stage: Path, remote: str, workers: int) -> dict:
    catalog = json.loads((stage / "metadata/catalog.json").read_text(encoding="utf-8"))
    specs = file_specs(catalog)
    for key, size, digest in specs:
        local = (stage / key).resolve()
        if not local.is_relative_to(stage.resolve()) or not local.is_file():
            raise ValueError(f"Missing local image: {key}")
        if local.stat().st_size != size or hashlib.sha256(local.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Local image integrity check failed: {key}")

    def verify_one(spec: tuple[str, int, str]) -> dict:
        key, size, digest = spec
        length, observed = remote_digest(remote, key, limit=size + 1)
        if length != size or observed != digest:
            raise ValueError(f"Remote byte/hash mismatch: {key}")
        return {"key": key, "remote_sha256": observed, "bytes": length}

    verified = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(verify_one, spec): spec[0] for spec in specs}
        for future in as_completed(futures):
            verified.append(future.result())
    report = {
        "schema_version": 1,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "remote rclone cat + SHA256 of all original/preview bytes",
        "albums": len(catalog["albums"]),
        "originals": len(specs) // 2,
        "media_files": len(specs),
        "remote_retrievals": sorted(verified, key=lambda item: item["key"]),
    }
    report_path = stage / "metadata/remote-verification.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REMOTE_BYTES_AND_SHA256_VERIFIED", report["albums"], report["originals"], report["media_files"], flush=True)
    return report


def verify_catalog(stage: Path, remote: str) -> None:
    local = (stage / "metadata/catalog.json").read_bytes()
    size, retrieved_digest = remote_digest(remote, "metadata/catalog.json", limit=len(local) + 1)
    if size != len(local) or hashlib.sha256(local).hexdigest() != retrieved_digest:
        raise ValueError("Remote catalogue differs from the local validated catalogue")
    print("REMOTE_CATALOG_SHA256_VERIFIED", retrieved_digest, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=Path)
    ap.add_argument("remote", help="Private rclone remote; e.g. archive:YuiArchive")
    ap.add_argument("--mode", choices=("media", "catalog"), required=True)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if not 1 <= args.workers <= 8:
        ap.error("--workers must be between 1 and 8")
    if args.mode == "media":
        verify_media(args.stage, args.remote, args.workers)
    else:
        verify_catalog(args.stage, args.remote)


if __name__ == "__main__":
    main()
