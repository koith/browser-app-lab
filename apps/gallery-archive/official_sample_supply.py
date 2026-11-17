#!/usr/bin/env python3
"""Classify already-recorded DJAWA public sample URLs; never equate with paid masters.

Only moves a source from fixed priority to normal rotation when every recorded
official sample URL is represented by a verified SHA or same-work saved source
URL. A changed/new source can still be scanned on later runs.
"""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path


def exhausted_official_samples(root: Path, model: str = "mimmi") -> set[str]:
    root = Path(root)
    if model != "mimmi":
        return set()
    folder = root / "apps" / (model + "-gallery")
    paths = [folder / n for n in (
        "public-work-pages.json", "official-previews.json", "stored-albums.json",
        "owner-index.json")]
    if any(not p.is_file() for p in paths):
        return set()
    sources, official, stored, owner = (
        json.loads(p.read_text(encoding="utf-8")) for p in paths)
    if (official.get("model", {}).get("id") != model
            or owner.get("model") != model
            or stored.get("model", model) != model):
        raise ValueError("OFFICIAL_SAMPLE_MODEL_MISMATCH")

    known = {a["id"]: a for a in sources.get("albums", [])
             if isinstance(a, dict) and isinstance(a.get("id"), str)}
    source_to_id = {a.get("source"): a["id"] for a in known.values()
                    if isinstance(a.get("source"), str)}
    all_hashes = {
        p["sha256"]
        for doc in (stored, owner)
        for album in doc.get("albums", [])
        for p in album.get("images", [])
        if isinstance(p, dict) and isinstance(p.get("sha256"), str)
        and len(p["sha256"]) == 64
    }
    saved_urls = defaultdict(set)
    for album in stored.get("albums", []):
        for photo in album.get("images", []):
            url = photo.get("source_url")
            if isinstance(url, str) and url.startswith("https://"):
                saved_urls[album.get("id")].add(url)

    documented = defaultdict(set)
    covered = defaultdict(set)
    for album in official.get("albums", []):
        if not isinstance(album, dict):
            continue
        aid = album.get("id")
        if aid not in known:
            aid = source_to_id.get(album.get("source"))
        if aid not in known or album.get("publisher") != "DJAWA":
            continue
        for sample in album.get("samples", []):
            if not isinstance(sample, dict):
                continue
            url = sample.get("url")
            sha = sample.get("sha256")
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            documented[aid].add(url)
            if (isinstance(sha, str) and sha in all_hashes) or url in saved_urls[aid]:
                covered[aid].add(url)
    return {aid for aid, urls in documented.items()
            if urls and urls.issubset(covered[aid])}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    exhausted = exhausted_official_samples(root)
    print("DJAWA_RECORDED_SAMPLE_URLS_EXHAUSTED", len(exhausted),
          ",".join(sorted(exhausted)))
