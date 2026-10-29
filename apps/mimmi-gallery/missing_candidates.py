"""Select only genuinely missing Mimmi album/number slots from verified source evidence.

Exact SHA may be reused across positions, but a populated numbered slot is not
overwritten by a different source-image hash without a separate image-identity review.
Owner-private archive checkpoints contain *no* private image bytes, hashes or links.
"""
from __future__ import annotations
import hashlib
import re
from urllib.parse import unquote

SHA = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,100}\Z")


def safe_id(value: str) -> str:
    original = str(value)
    name = unquote(original).lower().replace("²", "2").replace("³", "3")
    name = re.sub("[^a-z0-9-]+", "-", name).strip("-")
    if not name:
        name = "imported"
    if name != original:
        name += "-" + hashlib.sha256(original.encode()).hexdigest()[:6]
    return name[:100]


def saved_positions(stored: dict) -> set[tuple[str, int, str]]:
    """Public image positions, including implicit 1-based numbering."""
    if stored.get("model") != "mimmi" or not isinstance(stored.get("albums"), list):
        raise ValueError("Mimmi physical saved manifest is required")
    positions = set()
    for album in stored["albums"]:
        if not isinstance(album.get("id"), str):
            continue
        for i, photo in enumerate(album.get("images", []), 1):
            number = photo.get("number")
            if type(number) is not int or number < 1:
                number = i
            sha = photo.get("sha256")
            if isinstance(sha, str) and SHA.fullmatch(sha):
                positions.add((album["id"], number, sha))
    return positions


def archived_positions(checkpoint: dict) -> set[tuple[str, int]]:
    """Validate a checkpoint produced from downloaded, SHA-audited private ZIPs.

    It never proves that a browser has imported the media. It only proves that
    the collection pipeline has already preserved the given numbered originals.
    """
    if (checkpoint.get("schema_version") != 1
            or checkpoint.get("model") != "mimmi"
            or checkpoint.get("source") != "verified-private-drive-wrapper-zip-readback"
            or not isinstance(checkpoint.get("albums"), dict)
            or type(checkpoint.get("position_count")) is not int
            or checkpoint["position_count"] < 1
            or type(checkpoint.get("backed_up_zip_count")) is not int
            or checkpoint["backed_up_zip_count"] < 1):
        raise ValueError("Invalid private Drive backed-up position checkpoint")
    rows = set()
    for aid, ranges in checkpoint["albums"].items():
        if not isinstance(aid, str) or not ID.fullmatch(aid) or not isinstance(ranges, list):
            raise ValueError("Invalid private checkpoint album")
        for span in ranges:
            if (not isinstance(span, list) or len(span) != 2
                    or any(type(v) is not int for v in span)):
                raise ValueError("Invalid private checkpoint range")
            lo, hi = span
            if not (1 <= lo <= hi <= 15000):
                raise ValueError("Invalid private checkpoint bounds")
            for number in range(lo, hi + 1):
                key = (aid, number)
                if key in rows:
                    raise ValueError("Duplicate private checkpoint position")
                rows.add(key)
    if len(rows) != checkpoint["position_count"]:
        raise ValueError("Private checkpoint total does not match physical archived positions")
    return rows


def select_missing(source: dict, already: set[tuple],
                   batch: int, batches: int) -> tuple[list[dict], int]:
    if source.get("model") != "mimmi" or not source.get("source_link_only"):
        raise ValueError("Mimmi source-only inventory is required")
    if batches < 1 or batch not in range(batches):
        raise ValueError("Invalid batch index")
    # Public entries are (album, number, sha), archived checkpoint entries
    # are (album, number). Neither may be counted twice.
    filled = {(a, n) for a, n, *_ in already}
    selected, missing_count = [], 0
    for i, original in enumerate(source.get("albums", [])):
        aid = safe_id(original["id"])
        photos, numbers = [], set()
        for photo in original.get("images", []):
            sha, number = photo.get("sha256"), photo.get("number")
            if (not isinstance(sha, str) or not SHA.fullmatch(sha)
                    or type(number) is not int or number < 1 or number in numbers):
                continue
            numbers.add(number)
            if (aid, number) in filled:
                continue
            missing_count += 1
            if i % batches == batch:
                photos.append(photo)
        if photos:
            # UNKNOWN publisher total must remain unknown; an indexed 10-photo
            # preview is never labelled a complete 10-photo paid edition.
            expected = original.get("expected")
            expected = expected if type(expected) is int and expected >= len(photos) else None
            selected.append({**original, "id": aid, "images": photos, "expected": expected})
    return selected, missing_count
