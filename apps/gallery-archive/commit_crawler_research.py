#!/usr/bin/env python3
"""Commit verified Mimmi source evidence safely after multi-hour crawls.

Keeps a private copy of the just-collected manifest, fetches current main,
merges by album identity and SHA, then atomically publishes the researched
manifest + derived indexes. Concurrent git pushes retry without discarding
either crawler's evidence. Does not turn source URLs into gallery photos.
"""
from __future__ import annotations
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

ALLOWED = {"pixibb-public-previews.json", "xiutu-public-previews.json"}
PROJECT = Path(__file__).resolve().parents[2]


def ensure(value):
    if value.get("model") != "mimmi" or not isinstance(value.get("albums"), list):
        raise ValueError("Wrong model or invalid source catalog")
    for album in value["albums"]:
        if not isinstance(album.get("id"), str) or not album.get("id"):
            raise ValueError("Unnamed album")
        if not isinstance(album.get("source"), str) or not album["source"].startswith("https://"):
            raise ValueError("Unverifiable album source")
        if album.get("images", []) != []:
            raise ValueError("Research entries must not claim physical archive files")
        for photo in album.get("samples", []):
            if not isinstance(photo.get("sha256"), str) or len(photo["sha256"]) != 64:
                raise ValueError("Image sample lacks a full digest")
    return value


def merge_evidence(current: dict | None, new: dict) -> dict:
    """Non-destructively merge two verified public-source crawls."""
    ensure(new)
    if current is None:
        return copy.deepcopy(new)
    ensure(current)
    result = copy.deepcopy(current)
    albums = {a["id"]: copy.deepcopy(a) for a in current["albums"]}
    order = [a["id"] for a in current["albums"]]
    for incoming in new["albums"]:
        aid = incoming["id"]
        if aid not in albums:
            albums[aid] = copy.deepcopy(incoming)
            order.append(aid)
            continue
        old = albums[aid]
        if old["source"].rstrip("/") != incoming["source"].rstrip("/"):
            raise ValueError("Refuse to merge distinct photo sources under a shared ID: " + aid)
        # Current crawl's order takes precedence; earlier SHA-checked members
        # survive a transient 403, pagination hiccup, or incomplete refresh.
        new_samples = incoming.get("samples", [])
        history = old.get("samples", [])
        seen_sha = set()
        combined = []
        for sample in [*new_samples, *history]:
            sha = sample["sha256"]
            if sha not in seen_sha:
                seen_sha.add(sha)
                combined.append(copy.deepcopy(sample))
        for ix, sample in enumerate(combined, 1):
            sample["number"] = ix
            if sha := sample.get("sha256"):
                if sample not in new_samples and all(p.get("sha256") != sha for p in new_samples):
                    sample["carried_from_previous_verification"] = True
        merged = dict(old)
        for field, value in incoming.items():
            if field not in ("samples", "images", "visited_pages") and value not in (None, "", []):
                merged[field] = value
        merged["samples"] = combined
        merged["images"] = []
        merged["visited_pages"] = incoming.get("visited_pages") or old.get("visited_pages", [])
        albums[aid] = merged
    result["albums"] = [albums[aid] for aid in order]
    result["generated_at"] = new.get("generated_at", current.get("generated_at"))
    summary = dict(current.get("summary", {}))
    summary.update(new.get("summary", {}))
    summary["works"] = len(result["albums"])
    if "images_verified" in summary:
        summary["images_verified"] = sum(len(a.get("samples", [])) for a in result["albums"])
    if "actual_sha_verified_public_photo_urls" in summary:
        summary["actual_sha_verified_public_photo_urls"] = sum(
            len(a.get("samples", [])) for a in result["albums"])
    summary["fresh_verified"] = sum(a.get("fresh_http_verified", 0) for a in new["albums"])
    summary["private_cloud_archived"] = 0
    summary["physical_files_archived"] = 0
    result["summary"] = summary
    return ensure(result)


def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=PROJECT, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError("git " + args[0] + ": " + (p.stderr or p.stdout)[-550:])
    return p


def commit(manifest_name: str, retries: int) -> None:
    if manifest_name not in ALLOWED:
        raise ValueError("Only model-checked public-source evidence can be committed")
    path = Path("apps/mimmi-gallery") / manifest_name
    incoming = ensure(json.loads((PROJECT / path).read_text(encoding="utf-8")))
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(1, retries + 1):
        git("fetch", "origin", "main")
        # Fresh isolated Actions checkout only; preserve collected data in memory.
        git("reset", "--hard", "origin/main")
        file = PROJECT / path
        existing = json.loads(file.read_text(encoding="utf-8")) if file.exists() else None
        merged = merge_evidence(existing, incoming)
        file.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run = subprocess.run(
            [sys.executable, "apps/mimmi-gallery/build_model_gallery.py"],
            cwd=PROJECT, text=True, capture_output=True
        )
        if run.returncode:
            raise RuntimeError("Derived research catalog failed: " + run.stderr[-550:])
        git("add", str(path), "apps/mimmi-gallery/source-viewer-albums.json",
            "apps/mimmi-gallery/albums.json")
        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            print("MIMMI_CRAWL_NO_NEW_VERIFIED_SHA", manifest_name, flush=True)
            return
        git("commit", "-m", "Reconcile verified Mimmi public photo crawl without losing concurrent source evidence")
        pushed = git("push", "origin", "HEAD:main", check=False)
        if pushed.returncode == 0:
            print("MIMMI_CRAWL_MANIFEST_MERGED_AND_PUBLISHED",
                  json.dumps({"file": manifest_name, "albums": len(merged["albums"]),
                              "source_photo_occurrences": sum(len(a.get("samples", []))
                                                              for a in merged["albums"]),
                              "attempt": attempt}), flush=True)
            return
        print("MIMMI_CRAWL_REMOTE_ADVANCED_RETRY", manifest_name, attempt, flush=True)
    raise RuntimeError("Concurrent GitHub pushes prevented research commit after retries")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, choices=sorted(ALLOWED))
    p.add_argument("--retries", type=int, default=6)
    args = p.parse_args()
    if not 1 <= args.retries <= 12:
        p.error("Retries must be bounded")
    commit(args.manifest, args.retries)
