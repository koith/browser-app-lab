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
    # A concurrent fast capture may append new verified posts while this
    # compact snapshot is being published. Do NOT require a byte-for-byte
    # equality against a moving journal head; gateway reads both.
    snapshot=reader.load_catalog(include_entries=False)
    unverified_refs=reader.catalog_unverified_refs
    journal=reader.load_catalog(include_entries=True)
    invalid_markers=reader.unrecoverable_entries
    snapshot_ids={p["id"] for p in snapshot}
    journal_ids={p["id"] for p in journal}
    expected=result["catalog"].get("posts",0)
    snapshot_valid=(bool(snapshot_ids)
                    and snapshot_ids.issubset(journal_ids)
                    and len(snapshot_ids)>=expected
                    and unverified_refs==0)
    lag=len(journal_ids-snapshot_ids)
    complete=snapshot_valid and lag==0 and invalid_markers==0
    summary={"journal_readable_posts":len(journal),
             "published_catalog_posts":len(snapshot),
             "catalog_matches_journal":snapshot_ids==journal_ids,
             "index_lag_post_count":lag,
             "snapshot_sha_verified":snapshot_valid,
             "fully_reconciled":complete,
             "unverified_marker_count":invalid_markers,
             "unverified_catalog_references":unverified_refs,
             "catalog_published_this_run":bool(
                 result["catalog"].get("catalog_sha256_verified"))}
    print("PRIVATE_ARCHIVE_REBUILD_SUMMARY",
          json.dumps(summary,sort_keys=True),flush=True)
    if not snapshot_valid:
        raise RuntimeError("private cloud snapshot has unverified or missing post references")
    return summary


if __name__=="__main__":
    rebuild(run_id=os.environ.get("GITHUB_RUN_ID"))
