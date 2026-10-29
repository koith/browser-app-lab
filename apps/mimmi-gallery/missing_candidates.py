"""Determine genuinely missing physical album/number/SHA positions without discarding reused bytes."""
from __future__ import annotations
import hashlib
import re
from urllib.parse import unquote

SHA = re.compile(r"[a-f0-9]{64}\Z")


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
    """Only suppress a candidate if its *same album, numbered slot and SHA* is saved."""
    if stored.get("model") != "mimmi" or not isinstance(stored.get("albums"), list):
        raise ValueError("Mimmi physical saved manifest is required")
    positions = set()
    for album in stored["albums"]:
        if not isinstance(album.get("id"), str):
            continue
        for i, photo in enumerate(album.get("images", []), 1):
            number = photo.get("number")
            if type(number) is not int or number < 1:
                number = i  # Public stored manifests may have implicit 1-based numbers.
            sha = photo.get("sha256")
            if isinstance(sha, str) and SHA.fullmatch(sha):
                positions.add((album["id"], number, sha))
    return positions


def select_missing(source: dict, already: set[tuple[str, int, str]],
                   batch: int, batches: int) -> tuple[list[dict], int]:
    if source.get("model") != "mimmi" or not source.get("source_link_only"):
        raise ValueError("Mimmi source-only inventory is required")
    if batches < 1 or batch not in range(batches):
        raise ValueError("Invalid batch index")
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
            if (aid, number, sha) in already:
                continue
            missing_count += 1
            if i % batches == batch:
                photos.append(photo)
        if photos:
            selected.append({**original, "id": aid, "images": photos,
                             "expected": original.get("expected") or len(original.get("images", []))})
    return selected, missing_count
