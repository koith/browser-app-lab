"""Restore privately archived first-observation posts and commit compact catalog.

Unlike the frequent public source poll, this maintenance pass may read every
post marker, validate SHA256 and rebuild a compact catalog. It never uploads
post text or media to GitHub, or deletes/overwrites any remote object.
"""
from __future__ import annotations

import json
import os
from demand_archive import CloudArchive
from demand_capture_job import run


def rebuild(cloud=None, run_id=None):
    active=cloud or CloudArchive()
    result=run(fetchers=[lambda term,start,end: []],cloud=active,
               run_id=run_id, fast_mode=False)
    # A new reader instance ensures we verify remote durable state, not a
    # convenient in-memory dictionary retained by the writer.
    reader=CloudArchive(active.remote,runner=active.runner)
    journal=reader.load_catalog(include_entries=True)
    snapshot=reader.load_catalog(include_entries=False)
    snapshot_ids={p["id"] for p in snapshot}
    journal_ids={p["id"] for p in journal}
    valid=bool(snapshot_ids) and snapshot_ids==journal_ids
    summary={"journal_readable_posts":len(journal),
             "published_catalog_posts":len(snapshot),
             "catalog_matches_journal":valid,
             "unverified_marker_count":reader.unrecoverable_entries,
             "unverified_catalog_references":reader.catalog_unverified_refs,
             "catalog_published_this_run":bool(
                 result["catalog"].get("catalog_sha256_verified"))}
    print("PRIVATE_ARCHIVE_REBUILD_SUMMARY",
          json.dumps(summary,sort_keys=True),flush=True)
    if not valid:
        raise RuntimeError("private cloud index not yet consistent with verified journal")
    return summary


if __name__=="__main__":
    rebuild(run_id=os.environ.get("GITHUB_RUN_ID"))
