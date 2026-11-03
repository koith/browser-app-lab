"""Restore privately archived first-observation posts and commit compact catalog.

Unlike the frequent public source poll, this maintenance pass may read every
post marker, validate SHA256 and rebuild a compact catalog. It never uploads
post text or media to GitHub, or deletes/overwrites any remote object.
"""
from __future__ import annotations

import json
import os
import time
from demand_archive import CloudArchive
from demand_capture_job import run


def rebuild(cloud=None, run_id=None):
    active=cloud or CloudArchive()
    result=run(fetchers=[lambda term,start,end: []],cloud=active,
               run_id=run_id, fast_mode=False)
    # The TeraBox listing backend can show an older manifest immediately
    # after the writer has independently read back and SHA-verified the new
    # immutable index. A single stale read must not mean permanent data loss.
    # Use fresh independent readers and bounded rechecks. Never write an
    # alternate index merely to make a stale observation look successful.
    expected=result["catalog"].get("posts",0)
    snapshot_valid=False
    attempts=0
    # A concurrent fast capture may append new verified posts. Equality with
    # that moving journal is not required; the published snapshot must at
    # least include all entries the current rebuild committed.
    for delay in (0.0,0.6,1.6,3.0):
        if delay:
            time.sleep(delay)
        attempts+=1
        reader=CloudArchive(active.remote,runner=active.runner)
        snapshot=reader.load_catalog(include_entries=False)
        unverified_refs=reader.catalog_unverified_refs
        journal=reader.load_catalog(include_entries=True)
        invalid_markers=reader.unrecoverable_entries
        snapshot_ids={p["id"] for p in snapshot}
        journal_ids={p["id"] for p in journal}
        snapshot_valid=(bool(snapshot_ids)
                        and snapshot_ids.issubset(journal_ids)
                        and len(snapshot_ids)>=expected
                        and unverified_refs==0)
        if snapshot_valid:
            break
    lag=len(journal_ids-snapshot_ids)
    complete=snapshot_valid and lag==0 and invalid_markers==0
    summary={"independent_read_attempts":attempts,
             "journal_readable_posts":len(journal),
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
