"""Read-only private TeraBox archive integrity inventory.

No personally identifying data, URLs, post text, IDs, object names, or raw
backend errors in public Actions logs. Never deletes or writes remote content.
"""
from __future__ import annotations

import json
import re
from demand_archive import CloudArchive, sha256, canonical_json


def inspect(cloud=None, sample_size=8):
    cloud=cloud or CloudArchive()
    cloud.preflight()
    catalogs=cloud.names("metadata/manifests")
    original=cloud.names("metadata/entries")
    repaired=cloud.names("metadata/entries-repaired")
    markers=[("metadata/entries-repaired",n) for n in repaired if re.fullmatch(r"[0-9a-f]{40}\.json",n)]
    markers += [("metadata/entries",n) for n in original if re.fullmatch(r"[0-9a-f]{40}\.json",n)]
    ok=bad=0
    visited=set()
    for parent,name in markers:
        pid=name[:-5]
        if pid in visited:
            continue
        visited.add(pid)
        if len(visited)>sample_size:
            break
        try:
            meta=json.loads(cloud.read(parent+"/"+name,cap=1024))
            valid_marker=(isinstance(meta,dict) and meta.get("id")==pid and
                          re.fullmatch(r"[0-9a-f]{64}",str(meta.get("sha256",""))))
            data=(cloud.read_verified("posts/"+pid+"/post.json",
                                      meta["sha256"],cap=100_000)
                  if valid_marker else None)
            good=bool(valid_marker and data is not None)
            ok += bool(good)
            bad += not bool(good)
        except (RuntimeError,ValueError,TypeError,KeyError):
            bad+=1
    try:
        posts=cloud.load_catalog(include_entries=False)
        status="readable"
        count=len(posts)
        catalog_bytes=len(canonical_json({"schema_version":1,"posts":posts}))
    except (RuntimeError,ValueError,TypeError):
        status="unreadable"
        count=None
        catalog_bytes=None
    try:
        journal_verified_count=len(cloud.load_catalog(include_entries=True))
        journal_integrity_failures=cloud.unrecoverable_entries
    except (RuntimeError,ValueError,TypeError):
        journal_verified_count=None
        journal_integrity_failures=None
    result={
      "catalog_status":status,
      "catalog_post_count":count,
      "catalog_expected_bytes":catalog_bytes,
      "journal_verified_post_count":journal_verified_count,
      "journal_unrecoverable_count":journal_integrity_failures,
      "versioned_manifest_count":len([n for n in catalogs if re.fullmatch(r"manifest-[0-9]{6,30}\.json",n)]),
      "entry_marker_count":len([n for n in original if re.fullmatch(r"[0-9a-f]{40}\.json",n)]),
      "repaired_marker_count":len([n for n in repaired if re.fullmatch(r"[0-9a-f]{40}\.json",n)]),
      "sampled_unique_entries":min(len(visited),sample_size),
      "sample_valid":ok,"sample_mismatch":bad,
      "sampling_only":True,"full_integrity_claim":False
    }
    print("PRIVATE_ARCHIVE_READ_ONLY_SUMMARY",json.dumps(result,sort_keys=True),flush=True)
    return result


if __name__=="__main__":
    inspect()
