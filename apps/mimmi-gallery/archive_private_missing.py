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
from missing_candidates import select_missing, saved_positions, archived_positions, owner_catalog_positions, safe_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, default=0)
    p.add_argument("--batches", type=int, default=3)
    p.add_argument("--out", default="/tmp/mimmi-private-candidates")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--private-checkpoint", default=str(ROOT / "private-archive-checkpoint.json"))
    p.add_argument("--owner-catalog", type=Path, help="Latest read-only TeraBox catalog; required in production automation")
    args = p.parse_args()
    stored = json.loads((ROOT / "stored-albums.json").read_text(encoding="utf-8"))
    if stored.get("model") != "mimmi":
        raise ValueError("Wrong stored index")
    public = saved_positions(stored)
    if args.owner_catalog is not None:
        owner = json.loads(args.owner_catalog.read_text(encoding="utf-8"))
        private = owner_catalog_positions(owner)
        source_kind = "live_owner_catalog"
    else:
        # Historical CLI/test compatibility only. Production must pass --owner-catalog.
        checkpoint = json.loads(Path(args.private_checkpoint).read_text(encoding="utf-8"))
        private = archived_positions(checkpoint)
        source_kind = "historical_private_zip_checkpoint"
    existing = public | private
    print("ALREADY_PHYSICALLY_SAVED", "public", len(public), "private", len(private),
          "private_inventory_source", source_kind, flush=True)
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
             "model": "mimmi", "real_files_only": True, "public_saved_photo_positions": len(public),
             "private_inventory_source": source_kind,
             "private_drive_preserved_photo_positions": len(private),
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
