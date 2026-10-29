#!/usr/bin/env python3
"""Extract genuinely present image bytes into owner-private, numbered TeraBox files.

Input = already completed GitHub Actions private-import ZIPs and Mimmi's actual
committed public media. Never requests an external photo URL or claims that
research-only entries are backed up. Every output image is SHA-256 checked.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
VALID = __import__("re").compile(r"[a-z0-9][a-z0-9-]{1,100}\Z")
SHA = __import__("re").compile(r"[a-f0-9]{64}\Z")
EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_BYTES = 35 * 1024 * 1024


def validate(raw: bytes, image: dict) -> tuple[str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    if (len(raw) < 1024 or len(raw) > MAX_BYTES
            or image.get("sha256") != digest
            or image.get("bytes") != len(raw)
            or not SHA.fullmatch(digest)):
        raise ValueError("Image SHA/size mismatch")
    try:
        with Image.open(io.BytesIO(raw)) as picture:
            picture.load()
            if (picture.width, picture.height) != (image.get("width"), image.get("height")):
                raise ValueError("Decoded image dimension mismatch")
            fmt = EXT.get(picture.format)
            if not fmt:
                raise ValueError("Unsupported image format")
            return fmt, digest
    except OSError as error:
        raise ValueError("Unreadable image bytes") from error


def prepare(model: str, folder: Path, wrappers: Path, include_public: bool):
    if model not in ("yui", "mimmi"):
        raise ValueError("Unknown model")
    selected = {}
    processed = 0
    conflicts = 0
    duplicate = 0
    previous = set()
    seen_sha = set()

    def consider(aid: str, title: str, photo: dict, raw: bytes, source: str):
        nonlocal processed, conflicts, duplicate
        if not VALID.fullmatch(aid):
            raise ValueError("Unsafe album identifier")
        number = photo.get("number")
        if type(number) is not int or not 1 <= number <= 20000:
            raise ValueError("Missing original photo number")
        fmt, sha = validate(raw, photo)
        processed += 1
        slot = (aid, number)
        existing = selected.get(slot)
        record = {"model": model, "album": aid, "number": number,
                  "title": title[:220], "sha256": sha, "bytes": len(raw),
                  "width": photo["width"], "height": photo["height"],
                  "format": fmt, "data": raw, "origin_type": source}
        if existing is not None:
            if existing["sha256"] == sha:
                duplicate += 1
            else:
                conflicts += 1
                # Retain a stronger physically verified file for this slot.
                # The alternate stays uncounted; it is not silently promoted
                # to a new numbered photograph.
                if (record["width"] * record["height"], len(raw)) > (
                    existing["width"] * existing["height"], existing["bytes"]):
                    selected[slot] = record
            return
        selected[slot] = record

    if include_public and model == "mimmi":
        base = REPO / "apps/mimmi-gallery"
        index = json.loads((base / "stored-albums.json").read_text(encoding="utf-8"))
        if index.get("model") != model:
            raise ValueError("Wrong committed public gallery")
        for album in index["albums"]:
            for i, photo in enumerate(album["images"], 1):
                img = dict(photo)
                img.setdefault("number", i)
                name = img.get("url", "")
                if not name.startswith("stored-albums/") or ".." in Path(name).parts:
                    raise ValueError("Unsafe committed public photo path")
                path = (base / name).resolve()
                if not path.is_relative_to((base / "stored-albums").resolve()):
                    raise ValueError("Photo outside committed archive")
                consider(album["id"], album.get("title") or album["id"], img,
                         path.read_bytes(), "public-physically-committed")

    inputs = sorted(p for p in wrappers.rglob("*-private-import.zip") if p.is_file())
    if not inputs:
        raise ValueError("No Actions private photo ZIP contents found")
    for source_path in inputs:
        with ZipFile(source_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("model") != model:
                raise ValueError("Wrong model in private image archive")
            album_rows = manifest.get("albums")
            if not isinstance(album_rows, list) or not album_rows:
                raise ValueError("Missing physical ZIP album rows")
            for album in album_rows:
                aid = album["id"]
                photos = album.get("images", [])
                if manifest.get("physical_verified_image_count") != sum(
                        len(a.get("images", [])) for a in album_rows):
                    raise ValueError("ZIP manifest physical count disagrees")
                for image in photos:
                    name = image.get("url", "")
                    if (not isinstance(name, str) or not name.startswith("photos/")
                            or ".." in Path(name).parts):
                        raise ValueError("Unsafe source ZIP photo path")
                    consider(aid, album.get("title") or aid, image,
                             archive.read(name), "private-actions-verified")
        previous.add(source_path.name)

    if not selected:
        raise ValueError("No real saved photo data")
    by_album = defaultdict(list)
    for slot, record in sorted(selected.items()):
        by_album[slot[0]].append(record)

    media = []
    catalog_albums = []
    stage_files = 0
    for aid, records in sorted(by_album.items()):
        entry = {"id": aid, "title": records[0]["title"],
                 "expected": None, "complete": False, "images": []}
        for r in records:
            suffix = f'{r["number"]:05d}-{r["sha256"][:16]}'
            original = f'originals/{aid}/{suffix}.{r["format"]}'
            opath = folder / original
            opath.parent.mkdir(parents=True, exist_ok=True)
            if not opath.exists():
                opath.write_bytes(r["data"])
            with Image.open(io.BytesIO(r["data"])) as picture:
                picture.thumbnail((520, 520), Image.Resampling.LANCZOS)
                if picture.mode not in ("RGB", "RGBA"):
                    picture = picture.convert("RGB")
                preview_buffer = io.BytesIO()
                picture.save(preview_buffer, format="WEBP", quality=78, method=4)
            preview_data = preview_buffer.getvalue()
            preview_hash = hashlib.sha256(preview_data).hexdigest()
            preview = f'previews/{aid}/{suffix}.webp'
            ppath = folder / preview
            ppath.parent.mkdir(parents=True, exist_ok=True)
            if not ppath.exists():
                ppath.write_bytes(preview_data)
            entry["images"].append({
                "number": r["number"], "key": original, "sha256": r["sha256"],
                "bytes": r["bytes"], "width": r["width"], "height": r["height"],
                "preview": preview, "preview_sha256": preview_hash,
                "preview_bytes": len(preview_data),
            })
            media.append((original, r["bytes"], r["sha256"]))
            media.append((preview, len(preview_data), preview_hash))
            stage_files += 2
        catalog_albums.append(entry)
    (folder / "metadata").mkdir(parents=True, exist_ok=True)
    catalog = {"schema_version": 1, "model": model,
               "storage": "owner-private-terabox-sha-verified-bytes",
               "expected_is_known": False,
               "albums": catalog_albums,
               "summary": {"physical_photo_positions": len(selected),
                           "albums": len(by_album),
                           "media_files": stage_files,
                           "known_complete_photobooks": 0,
                           "photo_url_evidence_only_not_counted": True}}
    report = {"model": model, "physical_positions": len(selected),
              "decoded_and_sha_verified_input_rows": processed,
              "duplicate_photo_positions": duplicate,
              "same_slot_different_image_conflicts": conflicts,
              "verified_private_zip_inputs": len(previous),
              "media_files": stage_files, "albums": len(by_album)}
    (folder / "metadata/catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (folder / "metadata/stage-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "metadata/verify-list.txt").write_text(
        "\n".join(f"{sha} {length} {path}" for path, length, sha in media) + "\n")
    print("REAL_PHOTOGRAPHS_STAGED", json.dumps(report), flush=True)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=("yui", "mimmi"), required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--include-public", action="store_true")
    p.add_argument("--minimum", type=int, default=None)
    a = p.parse_args()
    report = prepare(a.model, a.out, a.inputs, a.include_public)
    minimum = a.minimum if a.minimum is not None else (2500 if a.model == "yui" else 2200)
    if minimum < 1 or report["physical_positions"] < minimum:
        raise ValueError("Unexpectedly incomplete original byte archive: " + str(report))


if __name__ == "__main__":
    main()
