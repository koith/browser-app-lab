#!/usr/bin/env python3
"""Keep only 18 original numbered Yui images absent from existing private archive.

Input is a separately downloaded, fully verified public web album. This never
publishes the files to GitHub Pages and never substitutes an adjacent photo.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from PIL import Image
from io import BytesIO

MISSING = {
    "teddy-bear97": (26, 27, 28, 35, 36, 37, 38, 40, 64, 72, 73, 80, 84, 91, 95, 96, 97),
    "wet-yui80": (2,),
}
EXPECTED = {"teddy-bear97": 97, "wet-yui80": 80}
EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def run(source: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    status = {"model": "yui", "archived": [], "real_new_candidate_positions": 0}
    for aid, missing in MISSING.items():
        folder = source / aid
        album = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        expected = EXPECTED[aid]
        original = album.get("images", [])
        if album.get("id") != aid or album.get("advertised_count") != expected:
            raise ValueError("Unexpected public photobook identity")
        if len(original) != expected:
            raise ValueError("Public photobook incomplete")
        by_number = {p.get("n"): p for p in original}
        if len(by_number) != expected or set(by_number) != set(range(1, expected + 1)):
            raise ValueError("Public photo numbering inconsistent")
        photo_rows, saved = [], {}
        for number in missing:
            p = by_number[number]
            raw = (folder / p["file"]).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != p["sha256"] or len(raw) != p["bytes"]:
                raise ValueError("Original byte or SHA mismatch")
            with Image.open(BytesIO(raw)) as img:
                img.load()
                ext = EXT.get(img.format)
                if ext is None or (img.width, img.height) != (p["width"], p["height"]):
                    raise ValueError("Original image not decodable or dimensions changed")
            name = "photos/" + digest + "." + ext
            saved[name] = raw
            photo_rows.append({
                "number": number, "url": name, "sha256": digest,
                "bytes": len(raw), "width": p["width"], "height": p["height"]
            })
        manifest = {
            "version": 1, "model": "yui",
            "physical_verified_image_count": len(photo_rows),
            "storage": "owner-private actual public image bytes",
            "albums": [{
                "id": aid, "title": album.get("title") or aid, "expected": expected,
                "status": "missing-numbered-slots-only", "images": photo_rows
            }],
        }
        archive_path = out / (aid + "-private-import.zip")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            for name, payload in saved.items():
                z.writestr(name, payload)
        with zipfile.ZipFile(archive_path) as z:
            assert z.testzip() is None
            for p in photo_rows:
                assert hashlib.sha256(z.read(p["url"])).hexdigest() == p["sha256"]
        status["archived"].append({"album": aid, "original_positions": list(missing),
                                   "actual_verified_files": len(photo_rows)})
        status["real_new_candidate_positions"] += len(photo_rows)
    if status["real_new_candidate_positions"] != 18:
        raise ValueError("Missing numbered positions are not all recovered")
    (out / "audit.json").write_text(json.dumps(status, indent=2) + "\n")
    print("YUI_PUBLIC_KNOWN_18_REAL_NUMBERED_BYTES", status["real_new_candidate_positions"], flush=True)
    return status


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=Path("yui-jliji-full-private"))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run(args.source, args.out)
