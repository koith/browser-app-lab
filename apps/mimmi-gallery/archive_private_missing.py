#!/usr/bin/env python3
"""Archive Mimmi's 370 researched-but-unsaved candidate SHA files as PRIVATE byte-verified ZIPs.

Keeps existing 2,162 public saved files intact. No URL is displayed unless its
unchanged SHA-256-verified bytes have been downloaded and kept persistently.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "yui-gallery"))
from collect_private_batch import archive


def safe_id(value: str) -> str:
    original = str(value)
    name = unquote(original).lower().replace("²", "2").replace("³", "3")
    name = re.sub("[^a-z0-9-]+", "-", name).strip("-")
    if not name:
        name = "imported"
    # Distinguish any encoded source identifiers from ordinary archive IDs.
    if name != original:
        name += "-" + hashlib.sha256(original.encode()).hexdigest()[:6]
    return name[:100]


def select_missing(source: dict, already: set[str], batch: int, batches: int) -> tuple[list[dict], int]:
    if source.get("model") != "mimmi" or not source.get("source_link_only"):
        raise ValueError("Mimmi source-only inventory is required")
    if batches < 1 or batch not in range(batches):
        raise ValueError("Invalid batch index")
    selected, seen, total = [], set(), 0
    for i, original in enumerate(source.get("albums", [])):
        photos = []
        numbers = set()
        for p in original.get("images", []):
            sha = p.get("sha256")
            n = p.get("number")
            if (not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{64}", sha)
                    or not isinstance(n, int) or n < 1 or n in numbers
                    or sha in already or sha in seen):
                continue
            numbers.add(n)
            seen.add(sha)
            photos.append(p)
            total += 1
        if i % batches == batch and photos:
            a = {**original, "id": safe_id(original["id"]), "images": photos,
                 "expected": original.get("expected") or len(original.get("images", []))}
            selected.append(a)
    return selected, total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, default=0)
    p.add_argument("--batches", type=int, default=3)
    p.add_argument("--out", default="/tmp/mimmi-private-candidates")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    stored = json.loads((ROOT / "stored-albums.json").read_text(encoding="utf-8"))
    if stored.get("model") != "mimmi":
        raise ValueError("Wrong stored index")
    existing = {item["sha256"] for a in stored["albums"] for item in a["images"]}
    source = json.loads((ROOT / "source-viewer-albums.json").read_text(encoding="utf-8"))
    albums, researched_unique_missing = select_missing(source, existing, args.batch, args.batches)
    print("UNSAVED_CANDIDATES", args.batch, len(albums),
          sum(len(a["images"]) for a in albums),
          "all_index_unique_missing", researched_unique_missing, flush=True)
    if args.dry_run:
        return
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for a in albums:
        report = archive(a, folder, workers=args.workers, timeout=14, model="mimmi")
        results.append(report)
    audit = {"generated_at": datetime.now(timezone.utc).isoformat(),
             "model": "mimmi", "real_files_only": True, "originally_saved_sha": len(existing),
             "researched_unique_sha_not_saved": researched_unique_missing,
             "batch": args.batch, "batches": args.batches,
             "albums": results,
             "physically_downloaded": sum(v["physically_saved"] for v in results),
             "missing_or_rejected": sum(v["source_indexed"] - v["physically_saved"] for v in results)}
    (folder / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n")
    print("MIMMI_NEW_PRIVATE_VERIFIED_BYTES", audit["physically_downloaded"],
          "rejected", audit["missing_or_rejected"], flush=True)


if __name__ == "__main__":
    main()
