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
MANIFEST_RE=re.compile(r"^manifest-[0-9]{6,30}\.json$")
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


def _parse_manifest(raw):
    info=json.loads(raw)
    if not isinstance(info,dict) or not SNAP_RE.fullmatch(str(info.get("file",""))) or not re.fullmatch(r"[0-9a-f]{64}",str(info.get("sha256",""))):
        raise ValueError("unsafe latest manifest")
    return info


def latest_manifest():
    # Immutable, unique per-run manifests avoid the TeraBox rcat overwrite
    # failure observed on latest.json. Never delete previous verified snapshots.
    try:
        listing=command(["lsf",REMOTE+"/manifests","--files-only","--retries","2"],timeout=90)
    except RuntimeError:
        listing=b""
    names=[name.strip() for name in listing.decode("utf-8","replace").splitlines()
           if MANIFEST_RE.fullmatch(name.strip())]
    # GitHub run IDs increase with each run. The newest fully verified pointer wins.
    for name in sorted(names,key=lambda v:int(v[9:-5]),reverse=True)[:30]:
        raw=read_remote(REMOTE+"/manifests/"+name,4096,optional=True)
        if raw is None:
            continue
        try:
            info=_parse_manifest(raw)
        except (ValueError,TypeError,json.JSONDecodeError):
            continue
        if info["file"]=="snapshot-"+name[9:-5]+".sqlite3":
            return info
    # Backward compatible with the historical latest.json pointer; no writes.
    legacy=read_remote(REMOTE+"/latest.json",4096,optional=True)
    return _parse_manifest(legacy) if legacy is not None else None


def publish_manifest(local_dir, data, run_id):
    if not re.fullmatch(r"[0-9]{6,30}",run_id):
        raise ValueError("invalid GitHub run ID")
    name="manifest-"+run_id+".json"
    payload=(json.dumps(data,sort_keys=True)+"\n").encode()
    path=Path(local_dir)/name
    path.write_bytes(payload)
    command(["copyto",str(path),REMOTE+"/manifests/"+name,"--retries","3"],timeout=240)
    readback=read_remote(REMOTE+"/manifests/"+name,4096)
    if readback != payload:
        raise RuntimeError("versioned manifest readback mismatch")
    return _parse_manifest(readback)


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
        # An immutable manifest is written LAST. Failed writes cannot clobber
        # the previously verified snapshot, and a readback confirms every byte.
        pointer=publish_manifest(folder,output,run_id)
        if pointer["sha256"]!=output["sha256"] or pointer["file"]!=output["file"]:
            raise RuntimeError("versioned pointer readback mismatch")
        print("PRIVATE_ACCOUNT_INDEX_VERIFIED",json.dumps({
            "accounts":output["accounts"],"source_rows":output["source_rows"],
            "account_groups":output["account_groups"],
            "grouped_accounts":output["grouped_accounts"],
            "public_scan_windows":windows,"catalog":catalog_info,
            "snapshot_readback_sha256":True,"no_person_identity_inference":True
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    run()
