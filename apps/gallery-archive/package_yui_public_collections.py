#!/usr/bin/env python3
"""Turn truly downloaded Yui public web albums into private, SHA-verified ZIP inputs.

Never packages image URLs or publishes originals to GitHub Pages. Input must be
the physical files and manifests produced by download_jliji_collections.py.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from PIL import Image
from io import BytesIO

TARGETS = ("yuis-present33", "athletic-club104")
ALBUM = re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
FORMATS = {"JPEG": "jpg", "WEBP": "webp", "PNG": "png"}


def package(source: Path, dest: Path, ids: tuple[str, ...] = TARGETS) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    report = {"model": "yui", "attempted_albums": list(ids), "archived": []}
    for aid in ids:
        if not ALBUM.fullmatch(aid):
            raise ValueError("Unsafe album ID")
        folder = source / aid
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest.get("id") != aid or not isinstance(manifest.get("images"), list):
            raise ValueError("Wrong physical collection manifest")
        expected = manifest.get("advertised_count")
        if type(expected) is not int or expected <= 0:
            raise ValueError("Expected number is not known")
        if len(manifest["images"]) != expected:
            raise ValueError("Incomplete physical photo album")
        rows, contents, numbers = [], {}, set()
        for p in manifest["images"]:
            number = p.get("n")
            name = p.get("file")
            if type(number) is not int or number < 1 or number in numbers:
                raise ValueError("Duplicate or invalid number")
            numbers.add(number)
            if not isinstance(name, str) or not re.fullmatch(r"[0-9]{1,5}\.(?:jpe?g|png|webp)", name):
                raise ValueError("Unsafe source photo name")
            original = (folder / name).read_bytes()
            digest = hashlib.sha256(original).hexdigest()
            if digest != p.get("sha256") or len(original) != p.get("bytes"):
                raise ValueError("Image SHA/byte mismatch")
            with Image.open(BytesIO(original)) as im:
                im.load()
                ext = FORMATS.get(im.format)
                if ext is None or (im.width, im.height) != (p.get("width"), p.get("height")):
                    raise ValueError("Decoded image format/dimension mismatch")
            archive_path = f"photos/{digest}.{ext}"
            contents[archive_path] = original
            rows.append({"number": number, "url": archive_path,
                         "sha256": digest, "bytes": len(original),
                         "width": p["width"], "height": p["height"]})
        if numbers != set(range(1, expected + 1)):
            raise ValueError("Incomplete numbered sequence")
        photo_album = {"id": aid, "title": manifest.get("title") or aid,
                       "expected": expected, "images": sorted(rows, key=lambda x:x["number"])}
        payload = {"model": "yui", "version": 1,
                   "storage": "real public photo bytes held privately",
                   "physical_verified_image_count": len(rows),
                   "albums": [photo_album]}
        zip_path = dest / (aid + "-private-import.zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", json.dumps(payload, ensure_ascii=False))
            for name, data in contents.items():
                archive.writestr(name, data)
        with zipfile.ZipFile(zip_path) as archive:
            assert archive.testzip() is None
            for row in rows:
                data = archive.read(row["url"])
                assert hashlib.sha256(data).hexdigest() == row["sha256"]
        report["archived"].append({"album": aid, "photos": len(rows),
                                   "original_bytes": sum(len(b) for b in contents.values())})
    report["total_actual_photos"] = sum(x["photos"] for x in report["archived"])
    (dest / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print("YUI_PUBLIC_PHYSICAL_PRIVATE_BACKFILL", json.dumps(report), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("yui-jliji-full-private"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package(args.source, args.out)


if __name__ == "__main__":
    main()
