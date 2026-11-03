"""Replay only AES-GCM encrypted private capture artifacts into TeraBox.

Do not publish any post text, URLs, user names, object identifiers, recovered
files or backend error bodies. The GitHub artifact service is an emergency
short-lived bridge, never the final source of truth.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from demand_archive import CloudArchive
from recovery_spool import RecoverySpool

ARTIFACT_NAME=re.compile(r"^intersection-private-recovery$")
MAX_ARTIFACTS=20
MAX_BYTES=200_000_000
MAX_CONSECUTIVE_FAILURES=3
MAX_RECORD_SECONDS=55


def _gh(args,*,max_bytes=2_000_000):
    result=subprocess.run(["gh",*args],capture_output=True,
                          check=False,timeout=100)
    if result.returncode:
        # gh stderr is intentionally never printed to public Actions logs.
        raise RuntimeError("private recovery artifact API unavailable")
    if len(result.stdout)>max_bytes:
        raise RuntimeError("private recovery artifact response over size limit")
    return result.stdout


def list_candidates():
    repo=os.getenv("GITHUB_REPOSITORY","")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise RuntimeError("missing repository context for private recovery")
    items=[]
    for page in (1,2,3):
        raw=_gh(["api",f"/repos/{repo}/actions/artifacts?name=intersection-private-recovery&per_page=100&page={page}"])
        data=json.loads(raw)
        batch=data.get("artifacts",[])
        for item in batch:
            name=item.get("name","")
            if (not ARTIFACT_NAME.fullmatch(name) or item.get("expired") is True
                    or not isinstance(item.get("size_in_bytes"),int)
                    or item["size_in_bytes"]>MAX_BYTES):
                continue
            run=item.get("workflow_run") or {}
            run_id=run.get("id")
            if (not isinstance(run_id,int) or run_id<1
                    or run.get("head_branch")!="main"
                    or run.get("repository_id")!=run.get("head_repository_id")):
                # Never restore an untrusted fork or pull-request artifact.
                continue
            items.append((str(item.get("created_at","")),run_id,name))
        if len(batch)<100:
            break
    # First observed snapshots are immutable; process the oldest retained
    # encrypted artifact first if they represent the same original post.
    return sorted(items)[:MAX_ARTIFACTS]


def validate_source_run(source_run):
    """Check that a targeted artifact comes from our trusted main workflow."""
    repo=os.environ.get("GITHUB_REPOSITORY","")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise RuntimeError("missing repository context for private recovery")
    raw=_gh(["api",f"/repos/{repo}/actions/runs/{source_run}"])
    data=json.loads(raw)
    head=data.get("head_repository") or {}
    if (data.get("name")!="INTERSECTION — Fast Private Public-Post Capture"
            or data.get("head_branch")!="main"
            or data.get("event") not in ("push","schedule","workflow_dispatch")
            or head.get("full_name")!=repo):
        raise RuntimeError("untrusted private recovery source run")


def restore_with_budget(spool,path,cloud,*,max_seconds=MAX_RECORD_SECONDS):
    """Limit each restore without bypassing TeraBox immutable SHA readback.

    Every subprocess invocation is shorter than the remaining per-original
    budget. A stalled provider must not monopolize the entire Actions runner
    and prevent the next encrypted artifact from being retried later.
    """
    previous_runner=cloud.runner
    deadline=time.monotonic()+max_seconds

    def bounded_runner(args,data=None,timeout=150,allow_missing=False):
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise RuntimeError("private encrypted restore time budget exceeded")
        return previous_runner(
            args,data=data,timeout=max(1,min(timeout,18,remaining)),
            allow_missing=allow_missing)

    cloud.runner=bounded_runner
    try:
        return spool.restore(path,cloud)
    finally:
        cloud.runner=previous_runner


def replay(cloud=None,local_directory=None):
    active=cloud or CloudArchive()
    active.preflight()
    summary={"artifacts":0,"encrypted_buffers":0,
             "first_observation_verified":0,"post_and_media_verified":0,
             "prior_original_preserved":0,"original_media_incomplete":0,
             "buffer_failures":0,"artifact_download_failures":0,
             "deferred_buffers":0}
    if local_directory:
        source_dirs=[Path(local_directory)]
    else:
        # Authentication is an Actions token limited to reading artifacts of
        # the SAME repository. It is never included in artifact contents.
        if not os.getenv("GH_TOKEN"):
            raise RuntimeError("private recovery actions token unavailable")
        source_dirs=[]
        # Download and restore sequentially; never spill plaintext artifacts.
        source_run=os.getenv("DEMAND_RECOVERY_SOURCE_RUN_ID","")
        if source_run:
            if not re.fullmatch(r"[0-9]{6,30}",source_run):
                raise ValueError("invalid private recovery source run")
            # A workflow_run completion event or explicit operator retry
            # can target a single run, but only if that run is an approved
            # main-branch capture (not an untrusted pull request or fork).
            validate_source_run(source_run)
            candidates=[("",int(source_run),"intersection-private-recovery")]
        else:
            candidates=list_candidates()
    if local_directory:
        directories=[(None,Path(local_directory))]
        tmp=None
    else:
        tmp=tempfile.TemporaryDirectory(prefix="intersection-recovery-")
        directories=[]
        for index,(created,run_id,name) in enumerate(candidates):
            target=Path(tmp.name)/str(index)
            target.mkdir(mode=0o700)
            try:
                _gh(["run","download",str(run_id),"-n",name,"-D",str(target)],
                    max_bytes=1_000_000)
                directories.append((name,target))
            except (RuntimeError,OSError,subprocess.TimeoutExpired):
                summary["artifact_download_failures"]+=1
    try:
        consecutive_failures=0
        for _name,directory in directories:
            encrypted=sorted(directory.glob("*.enc"))
            if not encrypted:
                continue
            summary["artifacts"]+=1
            if len(encrypted)>120:
                summary["buffer_failures"]+=1
                continue
            spool=RecoverySpool(directory)
            for offset,path in enumerate(encrypted):
                if consecutive_failures>=MAX_CONSECUTIVE_FAILURES:
                    # All source bytes remain encrypted and eligible for the
                    # next periodic replay. Never claim these are backed up.
                    summary["deferred_buffers"]+=len(encrypted)-offset
                    break
                summary["encrypted_buffers"]+=1
                try:
                    state=restore_with_budget(spool,path,active)
                    summary[state]+=1
                    consecutive_failures=0
                except (RuntimeError,ValueError,KeyError,TypeError,OverflowError):
                    summary["buffer_failures"]+=1
                    consecutive_failures+=1
    finally:
        if tmp:
            tmp.cleanup()
    print("INTERSECTION_ENCRYPTED_RECOVERY_SUMMARY",
          json.dumps(summary,sort_keys=True),flush=True)
    return summary


if __name__=="__main__":
    result=replay()
    if (result["buffer_failures"] or result["artifact_download_failures"]
            or result["deferred_buffers"]):
        raise RuntimeError("private archived recovery buffers still unverified")
