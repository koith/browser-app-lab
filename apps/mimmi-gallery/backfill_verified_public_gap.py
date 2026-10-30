#!/usr/bin/env python3
"""Recover Mimmi's full, independently verified public PixiBB page sequences.

The input images are researched public URL evidence, NEVER a gallery file.
Select by SHA against both GitHub-stored *actual* files and current private
TeraBox catalog; independently fetch SHA/size/dimensions and archive only
real unchanged image bytes. No paywall, CAPTCHA, login, inferred page URL,
third-party proxy, or download of undisclosed publisher originals.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "yui-gallery"))
from collect_private_batch import archive, allowed_url
from mimmi_verified_album_alias import align
from missing_candidates import owner_catalog_positions

HEX = re.compile(r"[a-f0-9]{64}\Z")
# This PixiBB web re-encode is a 61-photo alternate SHA series of an
# already SHA-archived complete 62-photo CreamSoda Neko set on Xiutu.
# Treat it as an alternate VERSION, not 61 missing frame positions.
KNOWN_ALTERNATE_EDITIONS = {
    "pixibb-auto-creamsoda-mimmi-vol-2-neko-mimmi-62-photos-cosplay":
        "xiutu-public-1190160",
}
EXPECTED_MODEL = "mimmi"


def valid_source_photo(item: dict) -> bool:
    url = item.get("url", "")
    allowed, _ = allowed_url(url)
    return (
        allowed and
        isinstance(item.get("sha256"), str) and
        HEX.fullmatch(item["sha256"]) is not None and
        type(item.get("number")) is int and 1 <= item["number"] <= 20000 and
        type(item.get("bytes")) is int and 5000 <= item["bytes"] <= 24000000 and
        type(item.get("width")) is int and type(item.get("height")) is int and
        min(item["width"], item["height"]) >= 300
    )


def known_saved_hashes(public: dict, owner: dict) -> set[str]:
    if public.get("model") != EXPECTED_MODEL or owner.get("model") != EXPECTED_MODEL:
        raise ValueError("Wrong model inventory")
    # It is safer to stop entirely than mistake an empty or malformed
    # TeraBox catalog for zero saved photos.
    owner_catalog_positions(owner)
    hashes = set()
    for document in (public, owner):
        for album in document.get("albums", []):
            for photo in album.get("images", []):
                sha = photo.get("sha256")
                if not isinstance(sha, str) or not HEX.fullmatch(sha):
                    raise ValueError("Saved photo has invalid SHA")
                hashes.add(sha)
    return hashes


def candidates(source: dict, saved_hashes: set[str], batch: int,
               batches: int, skip_alternatives=True) -> tuple[list[dict], dict]:
    if (source.get("model") != EXPECTED_MODEL
            or source.get("summary", {}).get("private_cloud_archived") != 0
            or type(source.get("albums")) is not list
            or batches < 1 or batch not in range(batches)):
        raise ValueError("Wrong model or unsafe source indexing")
    all_new = []
    seen = set(saved_hashes)
    rejected = []
    ignored_version = []
    for ordinal, album in enumerate(source["albums"]):
        aid = album.get("id")
        if not isinstance(aid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", aid):
            rejected.append({"id": str(aid)[:100], "reason": "invalid_public_album_id"})
            continue
        original = album.get("samples") or []
        if aid in KNOWN_ALTERNATE_EDITIONS and skip_alternatives:
            ignored_version.append({"album": aid, "same_work_reference": KNOWN_ALTERNATE_EDITIONS[aid],
                                    "alternate_sha_records": len(original)})
            continue
        select = []
        positions = set()
        for index, item in enumerate(original, 1):
            photo = dict(item)
            if type(photo.get("number")) is not int:
                photo["number"] = index
            if not valid_source_photo(photo):
                rejected.append({"id": aid, "number": photo.get("number"), "reason": "invalid_source_evidence"})
                continue
            if photo["number"] in positions:
                rejected.append({"id": aid, "number": photo["number"], "reason": "duplicate_number"})
                continue
            positions.add(photo["number"])
            if photo["sha256"] in seen:
                continue
            seen.add(photo["sha256"])
            select.append(photo)
        if select:
            claimed = album.get("advertised_photos")
            expected = claimed if type(claimed) is int and 1 <= claimed <= 20000 else None
            all_new.append({
                "id": aid,
                "title": album.get("title", aid),
                "source": album.get("source"),
                "expected": expected,
                "images": select,
            })
    result = [a for n, a in enumerate(all_new) if n % batches == batch]
    report = {
        "model": EXPECTED_MODEL,
        "source": "verified publicly rendered individual photo bytes",
        "source_albums": len(source["albums"]),
        "known_saved_sha_excluded": len(saved_hashes),
        "new_sha_unique_before_download": sum(len(a["images"]) for a in all_new),
        "new_sha_for_this_batch": sum(len(a["images"]) for a in result),
        "new_source_album_count": len(all_new),
        "batch": batch, "batches": batches,
        "excluded_alternate_editions": ignored_version,
        "invalid_source_entries": rejected,
        "targets": [{"id": a["id"], "candidates": len(a["images"]),
                     "advertised": a["expected"]} for a in result],
        "new_original_files_saved": 0,
    }
    return result, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--owner-catalog", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--batch", type=int, default=0)
    p.add_argument("--batches", type=int, default=4)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    source = json.loads((ROOT / "pixibb-public-previews.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "stored-albums.json").read_text(encoding="utf-8"))
    owner = json.loads(args.owner_catalog.read_text(encoding="utf-8"))
    saved = known_saved_hashes(public, owner)
    # Read-only identity diagnostics: show where each real source SHA is
    # already archived, so 10-image preview aliases can be grouped under
    # the corresponding complete album without copying or inventing photos.
    from collections import Counter
    locations = {}
    for document in (public, owner):
        for album in document.get("albums", []):
            for photo in album.get("images", []):
                locations.setdefault(photo["sha256"], set()).add(album["id"])
    if args.batch == 0:
        for album in source["albums"]:
            matches = Counter(aid for p in album.get("samples", [])
                              for aid in locations.get(p.get("sha256"), ()))
            print("MIMMI_PUBLIC_WORK_VERIFIED_SHA_MATCH",
                  json.dumps({"id": album["id"], "verified": len(album.get("samples", [])),
                              "stored_aliases": matches.most_common(5)}, ensure_ascii=False),
                  flush=True)
    targets, report = candidates(source, saved, args.batch, args.batches)
    targets, proof = align(targets, source, public, owner)
    report['verified_owner_album_aliases'] = proof
    report['canonical_work_candidates'] = sum(len(a['images']) for a in targets)
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        result = [archive(album, args.output, args.workers, timeout=28, model=EXPECTED_MODEL)
                  for album in targets]
        report["original_files_verified"] = sum(x["physically_saved"] for x in result)
        report["original_files_rejected"] = sum(x["source_indexed"]-x["physically_saved"] for x in result)
        report["results"] = result
    report["updated"] = datetime.now(timezone.utc).isoformat()
    (args.output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MIMMI_PIXIBB_REAL_UNSAVED_SHA_GAP_BACKFILL", json.dumps({
        k:v for k,v in report.items() if k not in ("results","invalid_source_entries")
    }, ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
