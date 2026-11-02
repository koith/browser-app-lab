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
    public_private_position_conflicts = set()
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
                    # Re-encoded previews, alternate editions and originals can
                    # have different SHA in the same numbered slot. Audit this,
                    # never silently merge or replace a published image.
                    public_private_position_conflicts.add((album["id"], position))
                else:
                    saved[album["id"]][position] = p["sha256"]
                stored_sha.add(p["sha256"])
                owner_count += 1

    # A provider read may fail while the last published static owner index
    # still records thousands of SHA-checked photos. Do NOT mistake a failed
    # live catalog read for zero saved owner photos. Keep live verification
    # counts separate; use published metadata only as UNVERIFIED gap context.
    live_private_catalog_verified = owner is not None and owner.is_file()
    reference_saved = defaultdict(dict, {aid: dict(photos) for aid, photos in saved.items()})
    reference_sha = set(stored_sha)
    published_fallback_rows = 0
    published_fallback_used = False
    if not live_private_catalog_verified:
        published = base / "owner-index.json"
        if published.exists():
            index = read_json(published)
            if (index.get("model") != model or index.get("schema_version") != 1
                    or not isinstance(index.get("albums"), list)):
                raise ValueError("Published owner index schema/model mismatch")
            published_fallback_used = True
            for album in index["albums"]:
                if not isinstance(album.get("id"), str) or not isinstance(album.get("images"), list):
                    raise ValueError("Published owner index invalid album")
                for ix, p in enumerate(album["images"], 1):
                    if not valid_photo(p):
                        raise ValueError("Published owner index invalid SHA/size")
                    position = photo_number(p, ix)
                    reference_saved[album["id"]].setdefault(position, p["sha256"])
                    reference_sha.add(p["sha256"])
                    published_fallback_rows += 1

    seen_sources = set()
    known_source_sha = set()
    per_album = defaultdict(lambda: {"sha": set(), "numbers": set(), "by_number": defaultdict(set), "expected": None})
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
                record["by_number"][n].add(p["sha256"])
                known_source_sha.add(p["sha256"])

    # Cross-site discovery creates different album IDs for the SAME photos.
    # A shared SHA proves byte identity, but does not prove equal publisher
    # photo numbering or an identical work/edition. Do not score an unmapped
    # research album's positions as MISSING from an unrelated saved album.
    alias_path = base / "album-aliases.json"
    aliases = read_json(alias_path).get("aliases", {}) if alias_path.exists() else {}
    if not isinstance(aliases, dict):
        raise ValueError("Invalid album aliases")

    def canonical_work(work: str) -> str:
        seen = set()
        while work in aliases:
            if work in seen:
                raise ValueError("Cyclic album aliases")
            seen.add(work)
            target = aliases[work]
            if not isinstance(target, str) or not target:
                raise ValueError("Invalid album alias target")
            work = target
        return work

    unarchived_shas = known_source_sha - reference_sha
    missing = []
    known_missing = 0
    advertised_missing = 0
    unfilled_source_positions = 0
    alternate_versions_at_filled_positions = 0
    unlinked_source_positions = 0
    reviewed_alias_source_positions = 0
    unlinked_work_ids = 0
    for aid, info in per_album.items():
        absent = info["sha"] - reference_sha
        known_missing += len(absent)
        expected = info["expected"]
        canonical = canonical_work(aid)
        # Only exact IDs may share publisher photo position numbers. A reviewed
        # alias certifies work membership, not a source site's numbering.
        if aid in reference_saved and reference_saved[aid]:
            relationship = "exact_saved_work"
            filled_positions = set(reference_saved[aid])
        elif canonical != aid and reference_saved.get(canonical):
            relationship = "reviewed_alias_different_numbering"
            filled_positions = set(reference_saved[canonical])
            reviewed_alias_source_positions += len(info["numbers"])
        else:
            relationship = "unlinked_research_work"
            filled_positions = set()
            unlinked_source_positions += len(info["numbers"])
            unlinked_work_ids += 1
        position_comparable = relationship == "exact_saved_work"
        source_unfilled = info["numbers"] - filled_positions if position_comparable else set()
        source_alternative_hashes = sum(
            len(hashes - reference_sha) for number, hashes in info["by_number"].items()
            if number in filled_positions
        ) if position_comparable else 0
        unfilled_source_positions += len(source_unfilled)
        alternate_versions_at_filled_positions += source_alternative_hashes
        advertised_gap = (len(set(range(1, expected + 1)) - filled_positions)
                          if expected is not None and position_comparable else None)
        if advertised_gap is not None:
            advertised_missing += advertised_gap
        if absent or source_unfilled or advertised_gap or source_alternative_hashes or relationship != "exact_saved_work":
            missing.append({
                "id": aid,
                "relationship": relationship,
                "canonical_saved_work": canonical if relationship == "reviewed_alias_different_numbering" else None,
                "source_sha_not_yet_stored": len(absent) if not published_fallback_used else None,
                "source_sha_absent_from_reference_index": len(absent),
                "reference_is_live_private_catalog": live_private_catalog_verified,
                "source_shas_already_stored_elsewhere": (len(info["sha"] & reference_sha) if relationship != "exact_saved_work" else 0) if not published_fallback_used else None,
                "source_shas_indexed_elsewhere": len(info["sha"] & reference_sha) if relationship != "exact_saved_work" else 0,
                "source_numbered_positions_not_stored": len(source_unfilled) if position_comparable and not published_fallback_used else None,
                "source_numbered_positions_absent_from_reference": len(source_unfilled) if position_comparable else None,
                "alternate_source_sha_at_saved_number": source_alternative_hashes if position_comparable else None,
                "stored_numbered_positions": len(filled_positions) if relationship != "unlinked_research_work" else None,
                "source_known_numbers": len(info["numbers"]),
                "web_expected_numbered_positions": expected,
                "missing_numbered_positions": advertised_gap,
            })
    # Prioritize genuinely unknown bytes over numbering-only claims.
    missing.sort(key=lambda a: (
        -a["source_sha_absent_from_reference_index"],
        -(a["source_numbered_positions_not_stored"] or 0),
        -(a["missing_numbered_positions"] or 0), a["id"]
    ))
    saved_positions = sum(len(x) for x in saved.values())
    reference_positions = sum(len(x) for x in reference_saved.values())
    return {
        "model": model,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "public_sha_verified_files": public_count,
        "public_albums": public_albums,
        "private_catalog_entries": owner_count if owner is not None and owner.exists() else None,
        "private_catalog_albums": owner_albums if owner is not None and owner.exists() else None,
        "combined_unique_album_number_positions": saved_positions,
        "published_owner_index_only_rows": published_fallback_rows if published_fallback_used else None,
        "indexed_reference_positions": reference_positions,
        "gap_reference_integrity": "LIVE_PRIVATE_CATALOG" if live_private_catalog_verified else ("PUBLISHED_METADATA_REMOTE_UNVERIFIED" if published_fallback_used else "PUBLIC_FILES_ONLY"),
        "public_private_position_conflicts_for_manual_identity_review": len(public_private_position_conflicts),
        "research_album_ids": len(work_ids),
        "research_distinct_sha_candidates": len(known_source_sha),
        "research_distinct_sha_not_in_saved_catalog": len(unarchived_shas) if not published_fallback_used else None,
        "research_distinct_sha_not_in_index_reference": len(unarchived_shas),
        "missing_source_sha_album_observations": known_missing if not published_fallback_used else None,
        "source_sha_absent_from_index_reference_observations": known_missing,
        "source_numbered_positions_not_stored": unfilled_source_positions if not published_fallback_used else None,
        "source_numbered_positions_not_in_reference": unfilled_source_positions,
        "unlinked_research_work_positions_not_claimed_missing": unlinked_source_positions,
        "reviewed_alias_source_positions_not_number_comparable": reviewed_alias_source_positions,
        "unlinked_research_work_ids": unlinked_work_ids,
        "source_sha_alternatives_for_already_filled_positions": alternate_versions_at_filled_positions,
        "advertised_numbered_positions_not_in_matching_id": advertised_missing if not published_fallback_used else None,
        "advertised_numbered_positions_not_in_reference": advertised_missing,
        "research_records_skipped_without_valid_sha": invalid_entries,
        "albums_needing_review": missing,
        "caution": "When gap_reference_integrity=PUBLISHED_METADATA_REMOTE_UNVERIFIED, private bytes have NOT been freshly read; only the last published index is used to prevent false missing inventory. Identical SHA across research IDs means identical bytes, NOT identical edition numbering. Unlinked research works and reviewed aliases do not contribute false missing-number counts. Alternate source SHA can be a re-encode, not an absent cut. Research, advertised totals and private-catalog entries are not newly downloaded photos; paid-edition completeness and publisher masters remain unverified.",
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
