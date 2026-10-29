#!/usr/bin/env python3
"""Read-only, source-wide Yui/Mimmi photo slot audit.

Research evidence is NEVER gallery inventory. Public files must exist on disk
and pass SHA-256. Owner catalog rows are counted separately as registered
private originals (cloud readback is the uploader's responsibility).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{64}$")
SOURCE_FILES = {
    "yui": ("additional-source-albums.json", "source-viewer-albums.json"),
    "mimmi": (
        "source-viewer-albums.json", "xiutu-public-previews.json",
        "v2ph-actor-previews.json", "v2ph-public-previews.json",
        "pixibb-public-previews.json", "official-previews.json",
        "gumroad-public-previews.json", "social-public-previews.json",
    ),
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def photo_number(photo: dict, index: int) -> int:
    value = photo.get("number")
    return value if type(value) is int and value > 0 else index


def valid_photo(photo: dict) -> bool:
    return (isinstance(photo, dict)
            and isinstance(photo.get("sha256"), str)
            and bool(SHA.fullmatch(photo["sha256"]))
            and type(photo.get("bytes")) is int and photo["bytes"] > 0)


def rows(root: Path, model: str, owner: Path | None = None) -> dict:
    base = root / "apps" / f"{model}-gallery"
    physical = read_json(base / "stored-albums.json")
    if not isinstance(physical.get("albums"), list):
        raise ValueError(f"{model}: invalid public inventory")
    if physical.get("model", model) != model:
        raise ValueError("Public inventory wrong model")

    saved = defaultdict(dict)
    stored_sha = set()
    public_count = 0
    public_albums = 0
    for album in physical["albums"]:
        album_has_file = False
        for index, p in enumerate(album.get("images", []), 1):
            if not valid_photo(p):
                raise ValueError("Public metadata is not SHA-verified")
            name = p.get("url", "")
            if (not isinstance(name, str) or not name.startswith("stored-albums/")
                    or ".." in name):
                raise ValueError("Invalid public image path")
            full = (base / name).resolve()
            if not full.is_relative_to(base.resolve()) or not full.is_file():
                raise ValueError(f"Missing public file: {model}/{name}")
            data = full.read_bytes()
            if len(data) != p["bytes"] or hashlib.sha256(data).hexdigest() != p["sha256"]:
                raise ValueError(f"Public byte integrity failure: {model}/{name}")
            pos = photo_number(p, index)
            if pos in saved[album["id"]] and saved[album["id"]][pos] != p["sha256"]:
                raise ValueError("Conflicting public photo position")
            saved[album["id"]][pos] = p["sha256"]
            stored_sha.add(p["sha256"])
            public_count += 1
            album_has_file = True
        public_albums += int(album_has_file)
    manifest_count = physical.get("physical_verified_image_count")
    if manifest_count is not None and manifest_count != public_count:
        raise ValueError("Public manifest count mismatch")

    owner_count = 0
    owner_albums = 0
    if owner is not None and owner.is_file():
        o = read_json(owner)
        if o.get("model") != model or o.get("schema_version") != 1:
            raise ValueError("Private catalog schema/model mismatch")
        for album in o.get("albums", []):
            if not album.get("images"):
                continue
            owner_albums += 1
            for i, p in enumerate(album["images"], 1):
                if not valid_photo(p):
                    raise ValueError("Private catalog missing SHA-256/size")
                position = photo_number(p, i)
                old = saved[album["id"]].get(position)
                if old is not None and old != p["sha256"]:
                    raise ValueError(f"Physical/public position conflict in {album['id']}")
                saved[album["id"]][position] = p["sha256"]
                stored_sha.add(p["sha256"])
                owner_count += 1

    seen_sources = set()
    known_source_sha = set()
    per_album = defaultdict(lambda: {"sha": set(), "numbers": set(), "expected": None})
    invalid_entries = 0
    work_ids = set()
    for filename in SOURCE_FILES[model]:
        path = base / filename
        if not path.exists():
            continue
        document = read_json(path)
        for album in document.get("albums", []):
            aid = str(album.get("id", ""))
            if not aid:
                continue
            work_ids.add(aid)
            record = per_album[aid]
            expected = album.get("expected")
            if type(expected) is int and 1 <= expected <= 20000:
                record["expected"] = max(record["expected"] or 0, expected)
            for ix, p in enumerate(album.get("images") or album.get("samples") or [], 1):
                if not valid_photo(p):
                    invalid_entries += 1
                    continue
                n = photo_number(p, ix)
                key = (aid, n, p["sha256"])
                if key in seen_sources:
                    continue
                seen_sources.add(key)
                record["sha"].add(p["sha256"])
                record["numbers"].add(n)
                known_source_sha.add(p["sha256"])

    # SHA equality is objective evidence across mirrored IDs. Identical titles
    # alone never justify merging distinct editions or filling a paid set.
    unarchived_shas = known_source_sha - stored_sha
    missing = []
    known_missing = 0
    advertised_missing = 0
    for aid, info in per_album.items():
        absent = info["sha"] - stored_sha
        known_missing += len(absent)
        expected = info["expected"]
        filled_positions = set(saved.get(aid, {}))
        if expected is not None:
            advertised_missing += len(set(range(1, expected + 1)) - filled_positions)
        if absent or (expected is not None and len(filled_positions) < expected):
            missing.append({
                "id": aid,
                "source_sha_not_yet_stored": len(absent),
                "stored_numbered_positions": len(filled_positions),
                "source_known_numbers": len(info["numbers"]),
                "web_expected_numbered_positions": expected,
                "missing_numbered_positions": (
                    len(set(range(1, expected + 1)) - filled_positions)
                    if expected is not None else None
                ),
            })
    missing.sort(key=lambda a: (
        -(a["source_sha_not_yet_stored"]),
        -(a["missing_numbered_positions"] or 0), a["id"]
    ))
    saved_positions = sum(len(x) for x in saved.values())
    return {
        "model": model,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "public_sha_verified_files": public_count,
        "public_albums": public_albums,
        "private_catalog_entries": owner_count if owner is not None and owner.exists() else None,
        "private_catalog_albums": owner_albums if owner is not None and owner.exists() else None,
        "combined_unique_album_number_positions": saved_positions,
        "research_album_ids": len(work_ids),
        "research_distinct_sha_candidates": len(known_source_sha),
        "research_distinct_sha_not_in_saved_catalog": len(unarchived_shas),
        "missing_source_sha_album_observations": known_missing,
        "advertised_numbered_positions_not_in_matching_id": advertised_missing,
        "research_records_skipped_without_valid_sha": invalid_entries,
        "albums_needing_review": missing,
        "caution": "Research, advertised totals, and private-catalog entries are not newly downloaded images. Missing positions can include equivalent cross-site albums with different IDs. Paid-edition completeness and publisher masters are not certified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--owner-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"schema_version": 1, "models": {}}
    for model in ("yui", "mimmi"):
        owner = args.owner_dir / f"{model}.json" if args.owner_dir else None
        item = rows(args.root, model, owner)
        result["models"][model] = item
        print("COMPREHENSIVE_ARCHIVE_AUDIT", json.dumps({
            key: value for key, value in item.items()
            if key not in ("albums_needing_review", "caution")
        }, ensure_ascii=False), flush=True)
        print("MISSING_PRIORITY", model, json.dumps(
            item["albums_needing_review"][:12], ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
