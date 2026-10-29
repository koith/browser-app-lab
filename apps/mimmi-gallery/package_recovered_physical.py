#!/usr/bin/env python3
"""Package only new Mimmi album-number slots from already captured Actions ZIPs.

Never fetch source websites and never publish image files to GitHub Pages.
Inputs are existing temporary Actions wrapper ZIPs. Verify all candidate
image bytes, hashes and decoded dimensions; compare both public physical
stored files and owner-only Drive backed-up photo slot checkpoint.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

from PIL import Image
from missing_candidates import archived_positions, saved_positions

ROOT = Path(__file__).resolve().parent
SHA = re.compile(r"[a-f0-9]{64}\Z")
PHOTO = re.compile(r"photos/([a-f0-9]{64})\.(jpg|jpeg|png|webp)\Z", re.I)


def pack(archive_paths: list[Path], public: dict, checkpoint: dict, target: Path) -> dict:
    if not archive_paths or public.get("model") != "mimmi":
        raise ValueError("A real Mimmi source wrapper and public physical index are required")
    occupied = {(a, n) for a, n, *_ in saved_positions(public)}
    private = archived_positions(checkpoint)
    occupied.update(private)
    candidates = {}
    source_rows = 0
    duplicates = 0
    for wrapper_path in archive_paths:
        if not wrapper_path.is_file():
            raise ValueError("Missing source Actions artifact: " + wrapper_path.name)
        with zipfile.ZipFile(wrapper_path) as wrapper:
            nested = [n for n in wrapper.namelist() if n.endswith("-private-import.zip")]
            if not nested:
                raise ValueError("No verified nested private photos in " + wrapper_path.name)
            for nested_name in sorted(nested):
                with zipfile.ZipFile(io.BytesIO(wrapper.read(nested_name))) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    if manifest.get("model") != "mimmi":
                        raise ValueError("Unexpected source model")
                    if manifest.get("physical_verified_image_count") != sum(
                        len(a.get("images", [])) for a in manifest.get("albums", [])
                    ):
                        raise ValueError("Unverified nested physical photo count")
                    for album in manifest["albums"]:
                        aid = album.get("id")
                        if not isinstance(aid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", aid):
                            raise ValueError("Unsafe source album identifier")
                        for photo in album["images"]:
                            number = photo.get("number")
                            sha = photo.get("sha256")
                            location = photo.get("url")
                            if (type(number) is not int or number < 1 or not isinstance(sha, str)
                                    or not SHA.fullmatch(sha) or not isinstance(location, str)
                                    or not PHOTO.fullmatch(location)
                                    or PHOTO.fullmatch(location).group(1) != sha):
                                raise ValueError("Invalid source photo index or SHA")
                            # Only existing, verified real physical files are considered.
                            data = archive.read(location)
                            if len(data) != photo.get("bytes") or hashlib.sha256(data).hexdigest() != sha:
                                raise ValueError("Source photo bytes are corrupted: " + aid)
                            with Image.open(io.BytesIO(data)) as probe:
                                probe.verify()
                            with Image.open(io.BytesIO(data)) as probe:
                                probe.load()
                                if (probe.width, probe.height) != (photo.get("width"), photo.get("height")):
                                    raise ValueError("Source image dimensions disagree with decoded bytes")
                            source_rows += 1
                            slot = (aid, number)
                            if slot in occupied:
                                duplicates += 1
                                continue
                            previous = candidates.get(slot)
                            if previous:
                                if previous["image"]["sha256"] != sha:
                                    raise ValueError("Conflicting new image SHA for same album and number")
                                duplicates += 1
                                continue
                            candidates[slot] = {"image": photo, "data": data, "title": str(album.get("title") or aid)}
    if not candidates:
        raise ValueError("All candidate photo positions are already physically saved")
    albums = defaultdict(list)
    for (aid, number), entry in candidates.items():
        albums[aid].append(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "schema_version": 1, "model": "mimmi", "real_saved_bytes_only": True,
        "previous_public_photo_positions": len(occupied - private),
        "previous_private_photo_positions": len(private),
        "input_wrapper_count": len(archive_paths), "input_verified_photo_rows": source_rows,
        "existing_or_duplicate_rows": duplicates, "new_verified_photo_positions": len(candidates),
        "complete_photobooks_claimed": 0,
        "albums": {aid: sorted(p["image"]["number"] for p in photos) for aid, photos in sorted(albums.items())}
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as outer:
        for aid, entries in sorted(albums.items()):
            entries.sort(key=lambda row: row["image"]["number"])
            # Old teaser collector incorrectly assumed expected=len(previews).
            # A recovered subset cannot certify a publisher's entire edition.
            manifest = {
                "version": 1, "model": "mimmi",
                "physical_verified_image_count": len(entries),
                "albums": [{"id": aid, "title": entries[0]["title"], "expected": None,
                            "status": "partial_downloaded", "images": [x["image"] for x in entries]}]
            }
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w", zipfile.ZIP_STORED) as z:
                z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
                written = set()
                for row in entries:
                    sha = row["image"]["sha256"]
                    if sha not in written:
                        z.writestr(row["image"]["url"], row["data"])
                        written.add(sha)
            outer.writestr(aid + "-private-import.zip", inner.getvalue())
        outer.writestr("audit.json", json.dumps(audit, ensure_ascii=False, indent=2))
    # The exact output ZIP must be readable, not merely a successful file write.
    with zipfile.ZipFile(target) as outer:
        for name in outer.namelist():
            if name.endswith("-private-import.zip"):
                with zipfile.ZipFile(io.BytesIO(outer.read(name))) as z:
                    m = json.loads(z.read("manifest.json"))
                    for a in m["albums"]:
                        for p in a["images"]:
                            raw = z.read(p["url"])
                            if hashlib.sha256(raw).hexdigest() != p["sha256"] or len(raw) != p["bytes"]:
                                raise ValueError("Output ZIP readback failed")
    audit["zip_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    audit["zip_bytes"] = target.stat().st_size
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", nargs="+", type=Path, required=True)
    parser.add_argument("--public-index", type=Path, default=ROOT / "stored-albums.json")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "private-archive-checkpoint.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    public = json.loads(args.public_index.read_text(encoding="utf-8"))
    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    audit = pack(args.archives, public, checkpoint, args.out)
    print("MIMMI_RECOVERED_STRICTLY_NEW_PHYSICAL_PHOTOS", audit["new_verified_photo_positions"],
          "rechecked input", audit["input_verified_photo_rows"],
          "excluded duplicates", audit["existing_or_duplicate_rows"],
          "SHA256", audit["zip_sha256"], flush=True)


if __name__ == "__main__":
    main()
