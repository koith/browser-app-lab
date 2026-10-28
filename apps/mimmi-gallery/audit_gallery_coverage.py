#!/usr/bin/env python3
"""Read-only Mimmi archive coverage audit.

Never inserts a research URL into the gallery or calls it stored. Only the
stored-albums.json manifest + actual committed image QA define displayed count.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHA = re.compile(r"[0-9a-f]{64}\Z")


def photo_shas(album):
    pictures = album.get("images") or album.get("samples") or []
    return {
        p["sha256"] for p in pictures
        if isinstance(p, dict) and isinstance(p.get("sha256"), str)
        and SHA.fullmatch(p["sha256"])
        and isinstance(p.get("bytes"), int) and p["bytes"] > 4500
    }


def report(root=ROOT):
    index = json.loads((root / "stored-albums.json").read_text(encoding="utf-8"))
    if index.get("model") != "mimmi":
        raise ValueError("Wrong model for physical gallery")
    albums = index.get("albums", [])
    physical = {a["id"]: photo_shas(a) for a in albums if a.get("images")}
    observed = sum(len(a.get("images", [])) for a in albums)
    if observed != index.get("physical_verified_image_count"):
        raise ValueError("Physical inventory count disagrees with saved album rows")
    saved = set().union(*physical.values()) if physical else set()
    if len(saved) != observed:
        raise ValueError("Duplicate SHA across physical albums: review before counting")
    sources = []
    source_files = ("source-viewer-albums.json", "xiutu-public-previews.json")
    for filename in source_files:
        path = root / filename
        if not path.exists():
            continue
        evidence = json.loads(path.read_text(encoding="utf-8"))
        if evidence.get("model") != "mimmi":
            raise ValueError("Wrong-model research index: " + filename)
        for a in evidence.get("albums", []):
            hashes = photo_shas(a)
            if hashes:
                sources.append((str(a.get("id", "")), str(a.get("title", "")), hashes))
    researched = set().union(*(s[2] for s in sources)) if sources else set()
    missing = researched - saved

    # A matching SHA, not a similar title, proves two websites show the same
    # edition. Never mix similarly named paid, AI-enhanced, or different sets.
    shortlist = []
    for a in albums:
        aid = a["id"]
        on_disk = physical.get(aid, set())
        if not 0 < len(on_disk) <= 10:
            continue
        same_work = [s for s in sources if s[0] == aid or bool(s[2] & on_disk)]
        extra = set().union(*(s[2] for s in same_work)) - saved if same_work else set()
        shortlist.append({
            "id": aid,
            "title": str(a.get("title", ""))[:100],
            "physically_stored": len(on_disk),
            "verified_but_not_stored_candidates": len(extra),
            "matching_sources": len(same_work),
        })
    shortlist.sort(key=lambda a: (-a["verified_but_not_stored_candidates"], a["physically_stored"], a["id"]))
    return {
        "physical_files": observed,
        "physical_albums": len(physical),
        "small_albums_at_most_10": len(shortlist),
        "research_sha_unique": len(researched),
        "research_sha_already_stored": len(researched & saved),
        "verified_source_candidates_not_stored": len(missing),
        "low_count_album_candidates": shortlist[:30],
        "disclaimer": "Research SHA candidates are NOT downloaded, hosted, licensed or counted in the gallery.",
    }


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        one, two, three = "a"*64, "b"*64, "c"*64
        def p(hash_value):
            return {"sha256": hash_value, "bytes": 7000}
        (root / "stored-albums.json").write_text(json.dumps({
            "model": "mimmi", "physical_verified_image_count": 1,
            "albums": [{"id": "set-one", "title": "Set 1", "images": [p(one)]}]
        }))
        (root / "source-viewer-albums.json").write_text(json.dumps({
            "model": "mimmi", "albums": [
                {"id": "mirror-id", "title": "Same edition", "images": [p(one), p(two)]},
                {"id": "different-id", "title": "Unlinked", "images": [p(three)]}]
        }))
        (root / "xiutu-public-previews.json").write_text(json.dumps({
            "model": "mimmi", "albums": [
                {"id": "duplicate-id", "title": "Duplicate source", "images": [], "samples": [p(two)]}]
        }))
        d = report(root)
        assert (d["physical_files"], d["physical_albums"]) == (1, 1), d
        assert d["research_sha_unique"] == 3, d
        assert d["verified_source_candidates_not_stored"] == 2, d
        assert d["small_albums_at_most_10"] == 1, d
        assert d["low_count_album_candidates"][0]["verified_but_not_stored_candidates"] == 1, d
        print("MIMMI_PHYSICAL_GAP_AUDIT_FIXTURE_PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        print("MIMMI_READ_ONLY_COVERAGE_AUDIT", json.dumps(report(), ensure_ascii=False))
