"""Read-only live TeraBox ZIP viewer acceptance, aggregate counts only.

This job runs on GitHub Actions with existing private cookie secrets, not
public Pages. It does not mutate, extract to disk, delete or upload anything.
"""
from __future__ import annotations
import json
from demand_archive import CloudArchive, sha256
from verified_bundle_reader import available_bundles, BundleAccountCloud
from target_account_enrichment import PROFILE_FILE_RE, THREAD_FILE_RE


def run():
    root=CloudArchive()
    root.preflight()
    bundles=available_bundles(root)
    selected=next(iter(bundles),None)
    if selected is None:
        raise RuntimeError("no verified account ZIP found in private TeraBox")
    archive=BundleAccountCloud(selected)
    accounts=selected.accounts
    if len(accounts)!=1 or selected.post_count==0:
        raise RuntimeError("verified private ZIP contains no exact public account")
    saved_posts=archive.load_catalog(include_entries=True)
    if len(saved_posts)!=selected.post_count:
        raise RuntimeError("indexed posts do not match verified source ZIP")
    profiles=[n for n in archive.names("profile/snapshots")
              if PROFILE_FILE_RE.fullmatch(n)]
    if not profiles:
        raise RuntimeError("verified profile snapshot not discoverable")
    original_media=0
    for post in saved_posts:
        for media in post.get("media",[]):
            data=archive.read_verified(media["key"],media["sha256"],
                                       cap=media["bytes"]+1)
            if data is None or len(data)!=media["bytes"]:
                raise RuntimeError("archived original media SHA mismatch")
            original_media+=1
    followers=len(archive.names("graph/pages"))
    threads=sum(len([name for name in archive.names("threads/"+post["id"])
                     if THREAD_FILE_RE.fullmatch(name)]) for post in saved_posts)
    if selected.source_state=="COMPLETE_CURRENT_PUBLIC_CURSOR" and threads==0:
        raise RuntimeError("verified account ZIP thread snapshots inaccessible")
    print("ACCOUNT_ZIP_READER_LIVE_VERIFIED "+json.dumps({
        "zip_whole_file_checksum_verified":True,
        "individual_objects_sha256_verified":selected.object_count,
        "indexed_posts_verified":len(saved_posts),
        "media_originals_sha256_verified":original_media,
        "profile_snapshots_visible":len(profiles),
        "graph_pages_visible":followers,
        "thread_snapshots_visible":threads,
        "source_state":selected.source_state,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    run()
