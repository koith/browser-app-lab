#!/usr/bin/env python3
"""Archive Mimmi researched photo positions as PRIVATE SHA-256-verified ZIPs.

Keeps existing committed public saved files intact. No URL is displayed unless its
unchanged SHA-256-verified bytes have been downloaded and kept persistently.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "yui-gallery"))
from collect_private_batch import archive
from missing_candidates import select_missing, saved_positions


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
    existing = saved_positions(stored)
    source = json.loads((ROOT / "source-viewer-albums.json").read_text(encoding="utf-8"))
    albums, researched_missing_positions = select_missing(source, existing, args.batch, args.batches)
    print("UNSAVED_CANDIDATES", args.batch, len(albums),
          sum(len(a["images"]) for a in albums),
          "all_index_missing_positions", researched_missing_positions, flush=True)
    if args.dry_run:
        return
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for a in albums:
        report = archive(a, folder, workers=args.workers, timeout=14, model="mimmi")
        results.append(report)
    audit = {"generated_at": datetime.now(timezone.utc).isoformat(),
             "model": "mimmi", "real_files_only": True, "originally_saved_photo_positions": len(existing),
             "researched_missing_photo_positions": researched_missing_positions,
             "batch": args.batch, "batches": args.batches,
             "albums": results,
             "physically_downloaded": sum(v["physically_saved"] for v in results),
             "missing_or_rejected": sum(v["source_indexed"] - v["physically_saved"] for v in results)}
    (folder / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n")
    print("MIMMI_NEW_PRIVATE_VERIFIED_BYTES", audit["physically_downloaded"],
          "rejected", audit["missing_or_rejected"], flush=True)


if __name__ == "__main__":
    main()
