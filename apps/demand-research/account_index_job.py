"""GitHub Actions scheduled private TeraBox account-index checkpoint.

Creates isolated immutable snapshots; never edits the post/media archive.
No usernames, posts, or cloud credentials are printed or uploaded to Actions.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import account_index
import account_index_sources
import account_groups

REMOTE="archive:DemandAccountIndex"
ARCHIVE="archive:DemandResearch/metadata/catalog.json"
SNAP_RE=re.compile(r"^snapshot-[0-9]{6,30}\.sqlite3$")
MAX_DB=120_000_000
MAX_CATALOG=70_000_000


def command(args, *, data=None, timeout=180):
    result=subprocess.run(["rclone",*args],input=data,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,timeout=timeout)
    if result.returncode:
        raise RuntimeError("private rclone operation failed")
    return result.stdout


def read_remote(path,max_bytes,optional=False):
    proc=subprocess.Popen(["rclone","cat",path,"--retries","2"],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    data=bytearray()
    try:
        while block:=proc.stdout.read(65536):
            data.extend(block)
            if len(data)>max_bytes:
                raise ValueError("private remote payload too large")
        status=proc.wait(timeout=120)
        if status:
            if optional:return None
            raise RuntimeError("private remote read failed")
        return bytes(data)
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait()


def latest_manifest():
    raw=read_remote(REMOTE+"/latest.json",2048,optional=True)
    if raw is None:return None
    info=json.loads(raw)
    if not isinstance(info,dict) or not SNAP_RE.fullmatch(str(info.get("file",""))) or not re.fullmatch(r"[0-9a-f]{64}",str(info.get("sha256",""))):
        raise ValueError("unsafe latest manifest")
    return info


def load_snapshot(path,manifest):
    blob=read_remote(REMOTE+"/snapshots/"+manifest["file"],MAX_DB)
    if hashlib.sha256(blob).hexdigest()!=manifest["sha256"]:
        raise RuntimeError("private snapshot digest mismatch")
    path.write_bytes(blob)


def create_snapshot(path,run_id):
    if not re.fullmatch(r"[0-9]{6,30}",run_id):
        raise ValueError("invalid Actions run identifier")
    import sqlite3
    conn=sqlite3.connect(str(path))
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("SQLite integrity check failure")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:conn.close()
    if path.stat().st_size>MAX_DB:raise ValueError("account snapshot too large")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    name="snapshot-"+run_id+".sqlite3"
    command(["copyto",str(path),REMOTE+"/snapshots/"+name,"--retries","3"],timeout=240)
    actual=read_remote(REMOTE+"/snapshots/"+name,MAX_DB)
    if hashlib.sha256(actual).hexdigest()!=digest:
        raise RuntimeError("snapshot readback mismatch; latest pointer not changed")
    return {"file":name,"sha256":digest,"at":int(time.time())}


def run():
    if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("private cloud credential missing")
    # This read-only preflight distinguishes missing first snapshot from broken auth.
    command(["lsf","archive:","--max-depth","1","--retries","2"],timeout=100)
    run_id=os.environ.get("GITHUB_RUN_ID","")
    with tempfile.TemporaryDirectory(prefix="intersection-index-") as folder:
        db=Path(folder)/"accounts.sqlite3"
        prior=latest_manifest()
        if prior:load_snapshot(db,prior)
        scan=account_index_sources.run_batch(str(db),max_requests=6)
        catalog_info="not_found"
        raw=read_remote(ARCHIVE,MAX_CATALOG,optional=True)
        if raw is not None:
            # The existing authenticated TeraBox post catalog remains read-only.
            obj=json.loads(raw)
            from gateway import validate_catalog
            if isinstance(obj,dict):
                posts=validate_catalog(obj)
                imported=account_index.sync_catalog(str(db),posts)
                catalog_info="verified_"+str(imported["accepted"])
            else:
                raise ValueError("catalog schema invalid")
        group_scan=account_groups.scan_known_profiles(str(db),max_profiles=55)
        stats=account_index.status(str(db))
        windows=account_index_sources.coverage(str(db))
        output=create_snapshot(db,run_id)
        groups=account_groups.groups_page(str(db),limit=1)
        output.update({"account_groups":groups["total"],
            "grouped_accounts":groups["linked_accounts"],
            "group_evidence_checked":group_scan["checked"],
            "accounts":stats["accounts"],"source_rows":stats["source_rows"],
            "last_catalog_sync":stats["last_catalog_sync"],
            "public_scan_windows":windows,"catalog":catalog_info,
            "last_public_scan_requests":scan.get("requests",0),
            "last_public_scan_accepted":scan.get("accepted",0)})
        # The pointer is written LAST. A crash before this write preserves prior state.
        command(["rcat",REMOTE+"/latest.json"],data=(json.dumps(output,sort_keys=True)+"\n").encode(),timeout=120)
        pointer=latest_manifest()
        if not pointer or pointer["sha256"]!=output["sha256"] or pointer["file"]!=output["file"]:
            raise RuntimeError("latest pointer readback mismatch")
        print("PRIVATE_ACCOUNT_INDEX_VERIFIED",json.dumps({
            "accounts":output["accounts"],"source_rows":output["source_rows"],
            "account_groups":output["account_groups"],
            "grouped_accounts":output["grouped_accounts"],
            "public_scan_windows":windows,"catalog":catalog_info,
            "snapshot_readback_sha256":True,"no_person_identity_inference":True
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    run()
