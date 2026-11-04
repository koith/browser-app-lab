#!/usr/bin/env python3
"""Read only an existing owner original, with exact physical-byte integrity.

No discovery, new imports, upload, publishing, account guessing or credential
fallback. Each model uses ONLY its own configured TeraBox account session.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mimmi-gallery" / "cloud" / "gateway"))
from cookie_format import cookie_header


def read_existing(remote: str, key: str, destination: Path, env: dict) -> tuple[bool, str]:
    if not key or ".." in key.split("/") or key.startswith("/"):
        raise ValueError("unsafe owner key")
    for method in ("cat", "copyto"):
        try:
            if method == "cat":
                with destination.open("wb") as out:
                    result = subprocess.run(
                        ["rclone", "cat", remote + "/" + key,
                         "--timeout=35s", "--retries=1"],
                        stdout=out, stderr=subprocess.DEVNULL,
                        env=env, timeout=65, check=False,
                    )
            else:
                destination.unlink(missing_ok=True)
                result = subprocess.run(
                    ["rclone", "copyto", remote + "/" + key, str(destination),
                     "--timeout=35s", "--retries=1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env, timeout=65, check=False,
                )
        except subprocess.TimeoutExpired:
            result = None
        if result and result.returncode == 0 and destination.is_file() and destination.stat().st_size:
            return True, method
    return False, "provider_unavailable"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=("mimmi", "yui"), required=True)
    args = p.parse_args()
    model = args.model
    secret = os.environ.get("MIMMI_COOKIE" if model == "mimmi" else "YUI_COOKIE", "")
    if not secret or len(secret) < 8:
        raise SystemExit("OWNER_FILE_SECRET_MISSING " + model)
    env = os.environ.copy()
    env["RCLONE_CONFIG_ARCHIVE_TYPE"] = "terabox"
    env["RCLONE_CONFIG_ARCHIVE_COOKIE"] = cookie_header(secret)
    remote = "archive:MimmiArchive" if model == "mimmi" else "archive:YuiArchive"
    wanted = "mimmi-indie-sana-sopmod2-2019" if model == "mimmi" else "yuis-present33"
    with tempfile.TemporaryDirectory(prefix="owner-read-only-") as dirname:
        root = Path(dirname)
        catalog_file = root / "catalog.json"
        ok, method = read_existing(remote, "metadata/catalog.json", catalog_file, env)
        if not ok:
            print("OWNER_EXISTING_CATALOG_BYTES_UNAVAILABLE", model, flush=True)
            raise SystemExit(2)
        try:
            catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise SystemExit("OWNER_EXISTING_CATALOG_NOT_JSON")
        if (catalog.get("model") != model or catalog.get("schema_version") != 1
                or not isinstance(catalog.get("albums"), list)):
            raise SystemExit("OWNER_EXISTING_CATALOG_WRONG_MODEL")
        owner = catalog["albums"]
        eligible = [
            (a, row)
            for a in owner if isinstance(a, dict) and isinstance(a.get("images"), list)
            for row in a["images"]
            if isinstance(row, dict)
            and isinstance(row.get("key"), str)
            and re.fullmatch("originals/[a-z0-9][a-z0-9-]{1,100}/[a-zA-Z0-9._-]+",
                             row["key"])
            and row["key"].startswith("originals/" + a["id"] + "/")
            and isinstance(row.get("sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", row["sha256"])
            and type(row.get("bytes")) is int and 0 < row["bytes"] <= 140_000_000
        ]
        preferred = [(a, row) for a, row in eligible if a["id"] == wanted and
                     (row.get("number") == 2 if model == "yui" else row.get("number") == 1)]
        if not eligible:
            raise SystemExit("OWNER_EXISTING_ORIGINAL_MANIFEST_EMPTY")
        album, photo = preferred[0] if preferred else eligible[0]
        print("OWNER_CATALOG_READ_VERIFIED", json.dumps({
            "model":model,"read_method":method,
            "albums":len(owner),"target_album_registered":bool(preferred)
        }),flush=True)
        output = root / "sample-photo"
        ok, method = read_existing(remote, photo["key"], output, env)
        if not ok:
            print("OWNER_EXISTING_ORIGINAL_BYTES_UNAVAILABLE",model,flush=True)
            raise SystemExit(3)
        payload = output.read_bytes()
        correct_sha = hashlib.sha256(payload).hexdigest() == photo["sha256"]
        correct_length = len(payload) == photo["bytes"]
        decoded = False
        try:
            with Image.open(output) as image:
                image.load()
                decoded = image.width >= 160 and image.height >= 160
                if type(photo.get("width")) is int:
                    decoded = decoded and image.width == photo["width"]
                if type(photo.get("height")) is int:
                    decoded = decoded and image.height == photo["height"]
        except (OSError, ValueError):
            pass
        print("OWNER_EXISTING_ORIGINAL_FILE_CHECK",json.dumps({
            "model":model,"same_account_method":method,
            "target_album_registered":bool(preferred),
            "sha256_verified":correct_sha,"byte_count_verified":correct_length,
            "pixel_decoded":decoded
        }),flush=True)
        if not (correct_sha and correct_length and decoded):
            raise SystemExit(4)
        print("OWNER_EXISTING_ORIGINAL_SHA_AND_PIXELS_PASS",model,flush=True)


if __name__ == "__main__":
    main()
