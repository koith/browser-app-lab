"""GitHub Actions scheduled private TeraBox account-index checkpoint.

Creates isolated immutable snapshots; never edits the post/media archive.
No usernames, posts, or cloud credentials are printed or uploaded to Actions.
"""
from __future__ import annotations
import hashlib
from contextlib import contextmanager
import json
import os
import re
import selectors
import signal
import sys
import subprocess
import tempfile
import time
from pathlib import Path

import account_index
import account_index_sources
import account_groups
from demand_archive import CloudArchive, validate_post, MAX_POST

REMOTE="archive:DemandAccountIndex"
ARCHIVE="archive:DemandResearch/metadata/catalog.json"
SNAP_RE=re.compile(r"^snapshot-[0-9]{6,30}\.sqlite3$")
MANIFEST_RE=re.compile(r"^manifest-[0-9]{6,30}\.json$")
MAX_DB=120_000_000
MAX_CATALOG=70_000_000

# Keep operational logs strictly aggregate-only. A hung Actions job must
# identify its last stage without exposing account IDs, original posts, URLs,
# TeraBox paths, credentials, or exception messages.
_INDEX_STAGES=frozenset({
    "remote_preflight", "manifest_lookup", "snapshot_load",
    "public_source_scan", "catalog_read", "catalog_sync", "profile_scan",
    "snapshot_upload_readback", "manifest_upload_readback",
})


@contextmanager
def audit_stage(name):
    if name not in _INDEX_STAGES:
        raise ValueError("unsupported private index stage")
    started=time.monotonic()
    status="failed"
    print("PRIVATE_ACCOUNT_INDEX_STAGE",json.dumps({
        "stage":name,"state":"begin"},sort_keys=True),flush=True)
    try:
        yield
    except BaseException:
        raise
    else:
        status="pass"
    finally:
        print("PRIVATE_ACCOUNT_INDEX_STAGE",json.dumps({
            "stage":name,"state":status,
            "elapsed_ms":max(0,int((time.monotonic()-started)*1000))},
            sort_keys=True),flush=True)


def command(args, *, data=None, timeout=180):
    result=subprocess.run(["rclone",*args],input=data,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,timeout=timeout)
    if result.returncode:
        raise RuntimeError("private rclone operation failed")
    return result.stdout


def read_remote(path,max_bytes,optional=False,*,max_seconds=None):
    """Bound the WHOLE remote read, not just wait() after stdout EOF.

    A provider can leave rclone cat's stdout open indefinitely. Blocking
    .read() never reaches the old wait(timeout=120), and GitHub Actions killed
    the 15-minute account index with no durable checkpoint. This loop caps
    time AND output without logging user records or provider error bodies.
    """
    if max_seconds is None:
        max_seconds=150 if max_bytes>1_000_000 else 40
    if max_seconds<=0 or max_bytes<=0:
        raise ValueError("invalid bounded private remote read")
    proc=subprocess.Popen(["rclone","cat",path,"--retries","2"],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
    data=bytearray()
    deadline=time.monotonic()+max_seconds
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise RuntimeError("private remote read timed out")
                if not selector.select(min(remaining,2.0)):
                    continue
                # os.read consumes only currently available bytes; unlike
                # BufferedReader.read(n) it cannot wait for all n bytes.
                block=os.read(proc.stdout.fileno(),65536)
                if not block:
                    break
                data.extend(block)
                if len(data)>max_bytes:
                    raise ValueError("private remote payload too large")
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise RuntimeError("private remote read timed out")
        try:
            status=proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise RuntimeError("private remote read timed out") from None
        if status:
            if optional:return None
            raise RuntimeError("private remote read failed")
        return bytes(data)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()


def _parse_manifest(raw):
    info=json.loads(raw)
    if not isinstance(info,dict) or not SNAP_RE.fullmatch(str(info.get("file",""))) or not re.fullmatch(r"[0-9a-f]{64}",str(info.get("sha256",""))):
        raise ValueError("unsafe latest manifest")
    return info


def latest_manifest_from_public_actions(*,get_runs=None,remote_reader=None):
    """Locate immutable account snapshots when TeraBox nested listing is broken.

    Public GitHub Actions metadata gives only candidate numeric run IDs;
    it never supplies or authenticates backup bytes. Each *private* manifest
    and SQLite payload still requires an independent remote SHA-256 readback.
    """
    if get_runs is None:
        from urllib.request import Request,urlopen
        url=("https://api.github.com/repos/koith/browser-app-lab/"
             "actions/workflows/demand-account-index-sync.yml/runs?per_page=5")
        req=Request(url,headers={
            "Accept":"application/vnd.github+json",
            "User-Agent":"intersection-private-index-manifest-fallback"})
        try:
            with urlopen(req,timeout=8) as response:
                blob=response.read(100001)
            if len(blob)>100000:
                return None
            data=json.loads(blob)
        except (OSError,ValueError,json.JSONDecodeError):
            return None
    else:
        data=get_runs()
    if not isinstance(data,dict) or not isinstance(data.get("workflow_runs"),list):
        return None
    reader=read_remote if remote_reader is None else remote_reader
    for run in data["workflow_runs"][:5]:
        if not isinstance(run,dict) or run.get("head_branch")!="main":
            continue
        rid=run.get("id")
        if type(rid) is not int or not 100000<=rid<=999999999999999999999999999999:
            continue
        name="manifest-"+str(rid)+".json"
        try:
            raw=reader(REMOTE+"/manifests/"+name,4096,
                       optional=True,max_seconds=14)
            if raw is None:
                continue
            info=_parse_manifest(raw)
            if info["file"]=="snapshot-"+str(rid)+".sqlite3":
                return info
        except (RuntimeError,ValueError,TypeError,KeyError,json.JSONDecodeError,OSError):
            continue
    return None


def latest_manifest():
    # Immutable, unique per-run manifests avoid the TeraBox rcat overwrite
    # failure observed on latest.json. Never delete previous verified snapshots.
    try:
        listing=command(["lsf",REMOTE+"/manifests","--files-only","--retries","2"],timeout=90)
    except (RuntimeError, OSError):
        # A first-run missing folder, a blocked listing, or a CI test without
        # rclone must not prevent the read-only legacy pointer fallback.
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


def catalog_sync_child(db_path, marker_path, *, cloud=None, max_items=64,
                       max_seconds=430):
    """Read a bounded page of immutable SHA-verifiable journal originals.

    Older monolithic load_catalog() repeatedly exceeded 90 and even 180
    seconds, so all newly verified posts disappeared from the account index
    until a complete scan succeeded. Never let a partial read call the
    destructive full-snapshot sync_catalog(), or mutate remote files.
    Advance a PRIVATE SQLite journal cursor, preserving earlier observations.
    """
    if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("private cloud credential missing")
    active=cloud or CloudArchive("archive:DemandResearch")
    deadline=time.monotonic()+max_seconds
    previous=active.runner

    def bounded_runner(args,data=None,timeout=150,allow_missing=False):
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError("bounded private journal page exhausted")
        return previous(args,data=data,
                        timeout=max(1,min(timeout,22,remaining)),
                        allow_missing=allow_missing)
    active.runner=bounded_runner
    try:
        ids=sorted(active.marker_ids())
        if not ids:
            Path(marker_path).write_text(json.dumps({
                "accepted":0,"has_posts":False,"mode":"journal_incremental",
                "pending":0,"verified":0},sort_keys=True))
            return
        db=account_index.connect(str(db_path))
        try:
            row=db.execute("SELECT value FROM index_meta WHERE key='journal_page_cursor'").fetchone()
            cursor=row[0] if row else ""
        finally:
            db.close()
        # Sorted circular order automatically revisits earlier damaged
        # markers on later scans. No post IDs are printed to logs.
        start=next((i for i,pid in enumerate(ids) if pid>cursor),0)
        chosen=(ids[start:]+ids[:start])[:max_items]
        posts=[]
        verified=[]
        attempted=0
        for pid in chosen:
            if deadline-time.monotonic()<22:
                break
            attempted+=1
            for directory in ("metadata/entries-repaired","metadata/entries"):
                try:
                    marker=active.read(directory+"/"+pid+".json",cap=1024,
                                       optional=True)
                    if marker is None:
                        continue
                    parsed=json.loads(marker)
                    if type(parsed) is not dict:
                        continue
                    digest=parsed.get("sha256")
                    if (parsed.get("id")!=pid or not isinstance(digest,str)
                            or not re.fullmatch(r"[a-f0-9]{64}",digest)):
                        continue
                    raw=active.read_verified("posts/"+pid+"/post.json",
                                             digest,cap=MAX_POST)
                    if raw is None:
                        continue
                    record=validate_post(json.loads(raw))
                    if record["id"]!=pid:
                        continue
                    posts.append(record)
                    verified.append(pid)
                    break
                except (RuntimeError,ValueError,TypeError,KeyError,TimeoutError):
                    # Keep private source paths and raw provider errors out of
                    # Actions; retries must not destroy older index snapshots.
                    continue
        last=chosen[attempted-1] if attempted else cursor
        summary=account_index.ingest_verified_marker_page(
            str(db_path),posts,verified,ids,last)
        print("PRIVATE_JOURNAL_PAGE_SHA_VERIFIED",json.dumps({
            "remote_marker_candidates":len(ids),
            "attempted":attempted,
            "verified_post_markers_this_run":len(verified),
            "pending_post_markers":summary["pending_marker_count"],
            "full_catalog_media_parity_verified":False,
        },sort_keys=True),flush=True)
        # An append-only journal page is not the versioned catalog+media
        # parity assertion required to close INT-04.
        Path(marker_path).write_text(json.dumps({
            "accepted":summary["accepted"],"has_posts":True,
            "mode":"journal_incremental",
            "pending":summary["pending_marker_count"],
            "verified":len(verified)},sort_keys=True))
    finally:
        active.runner=previous


def catalog_sync_bounded(db_path, folder, *, timeout_seconds=450, worker=None):
    """Avoid a stuck remote catalog preventing all other account checkpoints.

    The worker is in its own process group so a timeout also stops its rclone
    descendants. The old full-catalog reads repeatedly timed out at 90 and 180 seconds.
    The current page cursor remains bounded but can safely consume a larger
    430-second read budget, with a 450-second isolated process cap within
    the 780-second job hard limit. A failed page never deletes old entries.
    On any failure, never report a verified catalog sync. The parent may
    still SHA-verify an immutable PARTIAL checkpoint later.
    """
    marker=Path(folder)/"catalog-sync-result.json"
    argv=(worker if worker is not None else [
        sys.executable,str(Path(__file__).resolve()),
        "--catalog-sync",str(db_path),str(marker)])
    process=subprocess.Popen(argv,stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        try:
            code=process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            return "deferred_timeout"
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if code:
        return "deferred_error"
    try:
        data=marker.read_bytes()
        if len(data)>256:
            raise ValueError("oversized private catalog receipt")
        info=json.loads(data)
        if (type(info) is not dict or type(info.get("accepted")) is not int
                or not 0<=info["accepted"]<=100000 or type(info.get("has_posts")) is not bool):
            raise ValueError("invalid private catalog receipt")
    except (FileNotFoundError,ValueError,TypeError,KeyError,UnicodeError):
        return "deferred_invalid_receipt"
    if info.get("mode")=="journal_incremental":
        pending=info.get("pending")
        verified=info.get("verified")
        if (type(pending) is not int or not 0<=pending<=150000
                or type(verified) is not int or not 0<=verified<=64):
            return "deferred_invalid_receipt"
        # Partial journal progress is durable and real, but full remote
        # journal/catalog/media parity has not been SHA checked here.
        accepted=info.get("accepted")
        if type(accepted) is not int or not 0<=accepted<=64:
            return "deferred_invalid_receipt"
        # Integer counts only, no private source ID or post content.
        # Distinguish a 0-progress remote attempt from real SHA-confirmed
        # journal ingestion while never claiming full catalog parity.
        return ("deferred_journal_pending_"+str(pending)+
                "_sha_"+str(verified)+"_imported_"+str(accepted))
    return "verified_"+str(info["accepted"]) if info["has_posts"] else "not_found"


def run():
    if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("private cloud credential missing")
    # This read-only preflight distinguishes missing first snapshot from broken auth.
    with audit_stage("remote_preflight"):
        command(["lsf","archive:","--max-depth","1","--retries","2"],timeout=100)
    run_id=os.environ.get("GITHUB_RUN_ID","")
    with tempfile.TemporaryDirectory(prefix="intersection-index-") as folder:
        db=Path(folder)/"accounts.sqlite3"
        with audit_stage("manifest_lookup"):
            prior=latest_manifest()
        if prior:
            with audit_stage("snapshot_load"):
                load_snapshot(db,prior)
        with audit_stage("public_source_scan"):
            scan=account_index_sources.run_batch(str(db),max_requests=6)
        # The provider may hang for multiple 120s object-read retries.
        # Isolate it and preserve earlier verified index data on timeout.
        with audit_stage("catalog_read"):
            catalog_info=catalog_sync_bounded(str(db),folder)
        with audit_stage("profile_scan"):
            group_scan=account_groups.scan_known_profiles(str(db),max_profiles=55)
        stats=account_index.status(str(db))
        windows=account_index_sources.coverage(str(db))
        with audit_stage("snapshot_upload_readback"):
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
        with audit_stage("manifest_upload_readback"):
            pointer=publish_manifest(folder,output,run_id)
        if pointer["sha256"]!=output["sha256"] or pointer["file"]!=output["file"]:
            raise RuntimeError("versioned pointer readback mismatch")
        partial=catalog_info.startswith("deferred_")
        print("PRIVATE_ACCOUNT_INDEX_PARTIAL_CHECKPOINT_VERIFIED" if partial
              else "PRIVATE_ACCOUNT_INDEX_VERIFIED",json.dumps({
            "accounts":output["accounts"],"source_rows":output["source_rows"],
            "account_groups":output["account_groups"],
            "grouped_accounts":output["grouped_accounts"],
            "public_scan_windows":windows,"catalog":catalog_info,
            "snapshot_readback_sha256":True,"no_person_identity_inference":True
        },ensure_ascii=False),flush=True)
        # No false green workflow: partial progress is durable, but remote
        # catalog ingestion is still incomplete and must be retried.
        if partial:
            raise RuntimeError("private catalog sync remains unverified")


if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--catalog-sync":
        catalog_sync_child(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==1:
        run()
    else:
        raise SystemExit("invalid private index worker arguments")
