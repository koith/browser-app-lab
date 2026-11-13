"""Replay only AES-GCM encrypted private capture artifacts into TeraBox.

Do not publish any post text, URLs, user names, object identifiers, recovered
files or backend error bodies. The GitHub artifact service is an emergency
short-lived bridge, never the final source of truth.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile

from demand_archive import CloudArchive
from recovery_spool import RecoverySpool, FILE_PATTERN, MAX_BUFFER_BYTES

ARTIFACT_NAME=re.compile(r"^intersection-private-recovery$")
MAX_ARTIFACTS=12
MAX_BYTES=200_000_000
MAX_BUNDLE_BYTES=48_000_000
MAX_ARTIFACT_PAGES=60
MAX_CONSECUTIVE_FAILURES=3
# Six failed attempts across independently encrypted source artifacts is the
# global limit, while three consecutive failures isolate only that artifact.
MAX_TOTAL_FAILURES=6
MAX_RECORD_SECONDS=120
# Leave time for a final sanitized summary before the 21-minute Actions kill.
MAX_REPLAY_SECONDS=900
MAX_BATCH_SECONDS=100
MAX_CLOUD_PACKS=2
MAX_CLOUD_PACK_FILES=120
CLOUD_PACK_ITEM="__verified_remote_pack__"
CLOUD_PACK_NAME=re.compile(r"recovery-pack-([a-f0-9]{64})\.zip\Z")


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
    for page in range(1,MAX_ARTIFACT_PAGES+1):
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
    # A large 14-day backlog otherwise traps new failures behind the same
    # first 20 artifacts forever. Keep the oldest at-risk originals first,
    # and rotate the remainder across scheduled recovery runs.
    ordered=sorted(items)
    if len(ordered)<=MAX_ARTIFACTS:
        return ordered
    urgent=ordered[:3]
    remainder=ordered[3:]
    seed=int(os.environ.get("GITHUB_RUN_ID","0") or "0")
    offset=seed%len(remainder)
    rotated=remainder[offset:]+remainder[:offset]
    return urgent+rotated[:MAX_ARTIFACTS-len(urgent)]


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


def preserve_encrypted_batch(cloud,spool,paths):
    """Store only authenticated ciphertext in one immutable TeraBox object.

    The archive contains original AES-GCM .enc files, never unencrypted post
    text, source URLs, media or the secret. SHA readback verifies the entire
    packed byte sequence from TeraBox. This is a fallback safety copy, NOT
    an individual post-and-media recovery or a completed journal entry.
    """
    names=set()
    valid=[]
    for path in paths:
        path=Path(path)
        if not FILE_PATTERN.fullmatch(path.name) or path.name in names:
            raise ValueError("unsafe encrypted private recovery filename")
        names.add(path.name)
        # Reject corrupt/mismatched AES-GCM contents before mirroring.
        # Each file remains individually recoverable via RecoverySpool.
        record=spool.read(path)
        if not isinstance(record.get("first"),dict):
            raise ValueError("invalid authenticated private recovery record")
        data=path.read_bytes()
        valid.append((path.name,data))
    if not valid:
        return None
    if sum(len(raw) for _,raw in valid)>MAX_BUNDLE_BYTES-1024*len(valid):
        raise ValueError("private recovery batch exceeds bounded size")
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_STORED) as zipout:
        for name,data in sorted(valid):
            # Fixed ZIP metadata makes the SHA content-addressed and
            # independent of runner filesystem timestamps and paths.
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_STORED
            info.external_attr=0o600<<16
            zipout.writestr(info,data)
    blob=out.getvalue()
    if len(blob)>MAX_BUNDLE_BYTES:
        raise ValueError("encrypted recovery batch exceeds size limit")
    digest=hashlib.sha256(blob).hexdigest()
    # A separately verified selected-account ZIP succeeded in the TeraBox
    # root while metadata/ child writes and readback were unreliable.
    # Prefer the *same existing, immutable and independently SHA-retrieved*
    # root-object transport for encrypted recovery packs as well.
    # The reader already accepts both root and historical metadata/ keys.
    key="recovery-pack-"+digest+".zip"
    try:
        cloud.write_immutable(key,blob)
    except RuntimeError as error:
        # A genuinely missing root path may still work at the legacy location.
        # Never treat authorization denial, quota, checksum conflicts or a
        # missing remote SHA readback as permission to claim a backup.
        if safe_failure_category(error)!="missing_remote_path":
            raise
        key="metadata/recovery-pack-"+digest+".zip"
        cloud.write_immutable(key,blob)
    observed=cloud.read_verified(key,digest,cap=len(blob)+1)
    if observed!=blob:
        raise RuntimeError("encrypted recovery batch TeraBox checksum unverified")
    return key


def select_remote_encrypted_packs(cloud):
    """Select only SHA-addressed ciphertext packs from the private archive.

    Rotate bounded recovery sources so expired Actions artifacts remain
    recoverable without indefinitely starving other encrypted originals.
    """
    keys=set()
    listed=False
    for prefix in ("metadata",""):
        try:
            names=cloud.names(prefix)
            if not isinstance(names,list):
                raise ValueError("invalid private recovery pack listing")
            listed=True
        except (RuntimeError,ValueError):
            continue
        for name in names:
            if isinstance(name,str) and CLOUD_PACK_NAME.fullmatch(name):
                keys.add((prefix+"/" if prefix else "")+name)
    if not listed:
        raise RuntimeError("private recovery pack listings unavailable")
    keys=sorted(keys)
    if not keys:
        return []
    seed=int(os.environ.get("GITHUB_RUN_ID","0") or "0")
    offset=seed%len(keys)
    return (keys[offset:]+keys[:offset])[:MAX_CLOUD_PACKS]


def extract_verified_remote_pack(cloud,key,directory):
    """Independently verify TeraBox ZIP SHA before decrypting original buffers.

    Reject archive paths, duplicates, invalid names and zip bombs; nothing is
    unzipped as plaintext or outside an isolated temporary directory.
    """
    match=re.fullmatch(r"(?:metadata/)?recovery-pack-([a-f0-9]{64})\.zip",key)
    if not match:
        raise ValueError("untrusted private recovery pack key")
    raw=cloud.read_verified(key,match.group(1),cap=MAX_BUNDLE_BYTES+1)
    if raw is None or not 0<len(raw)<=MAX_BUNDLE_BYTES:
        raise RuntimeError("private recovery pack SHA256 readback unverified")
    if hashlib.sha256(raw).hexdigest()!=match.group(1):
        raise RuntimeError("private recovery pack checksum mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=archive.infolist()
            if not 0<len(entries)<=MAX_CLOUD_PACK_FILES:
                raise ValueError("invalid private recovery pack count")
            names=set()
            total=0
            sealed=[]
            for member in entries:
                name=member.filename
                if (not FILE_PATTERN.fullmatch(name) or member.is_dir()
                        or name in names or member.flag_bits&1):
                    raise ValueError("unsafe private recovery pack member")
                names.add(name)
                total+=member.file_size
                if (not 34<member.file_size<=MAX_BUFFER_BYTES+2048
                        or total>MAX_BUNDLE_BYTES):
                    raise ValueError("private recovery pack exceeds size limit")
                ciphertext=archive.read(member)
                if len(ciphertext)!=member.file_size:
                    raise ValueError("invalid recovery pack ciphertext length")
                sealed.append((name,ciphertext))
    except (zipfile.BadZipFile,RuntimeError,EOFError) as error:
        raise ValueError("invalid private recovery pack integrity") from error
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    directory.chmod(0o700)
    spool=RecoverySpool(directory)
    for name,ciphertext in sealed:
        dest=directory/name
        with dest.open("xb") as file:
            os.chmod(dest,0o600)
            file.write(ciphertext)
        # Verify AES-GCM authentication before any remote post/media writes.
        spool.read(dest)
    return sorted(directory.glob("*.enc"))


def with_cloud_budget(cloud,work,*,max_seconds=MAX_RECORD_SECONDS):
    """Bound both batch backup AND individual post restore.

    TimeoutError deliberately escapes the TeraBox backend's ordinary
    RuntimeError retry loops. The caller treats it as a safe unverified
    provider failure. No cloud object is deleted or overwritten.
    """
    previous_runner=cloud.runner
    deadline=time.monotonic()+max_seconds

    def bounded_runner(args,data=None,timeout=150,allow_missing=False):
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError("private recovery time budget exceeded")
        return previous_runner(
            # A SHA-verified video/object read can legitimately exceed the
            # old 18-second per-command cap on the free remote gateway.
            # Keep a strict 45-second ceiling AND an overall per-record budget.
            args,data=data,timeout=max(1,min(timeout,45,remaining)),
            allow_missing=allow_missing)

    cloud.runner=bounded_runner
    try:
        return work()
    finally:
        cloud.runner=previous_runner


def restore_with_budget(spool,path,cloud,*,max_seconds=MAX_RECORD_SECONDS):
    return with_cloud_budget(cloud,lambda:spool.restore(path,cloud),
                             max_seconds=max_seconds)



def safe_failure_category(error):
    """Map private backend errors to fixed labels; never expose raw messages.

    Rclone/JSON exceptions may include private remote paths, credentials or
    account identifiers. Only this finite allowlist is emitted to Actions.
    Search chained causes first because higher layers often wrap an exact
    provider error with an uninformative generic write failure.
    """
    chain=[]
    seen=set()
    current=error
    while current is not None and id(current) not in seen and len(chain)<5:
        seen.add(id(current))
        chain.append(current)
        current=current.__cause__ or current.__context__
    for err in reversed(chain):
        if isinstance(err,TimeoutError):
            return "timeout"
        message=str(err).lower()
        if any(tag in message for tag in ("(authorization)","authentication failed",
                                           "unauthorized","forbidden")):
            return "authorization"
        if any(tag in message for tag in ("(capacity)","quota exceeded","no space")):
            return "capacity"
        if any(tag in message for tag in ("(rate_limited)","too many requests")):
            return "rate_limited"
        if any(tag in message for tag in ("(missing)","backend_missing_path",
                                           "missing path","directory not found")):
            return "missing_remote_path"
        if any(tag in message for tag in ("checksum mismatch",
                                           "sha256 mismatch","checksum conflict",
                                           "immutable archive key collision",
                                           "integrity mismatch","invalid tag")):
            return "integrity_conflict"
        if any(tag in message for tag in ("readback unverified","checksum unverified",
                                           "readback did not converge")):
            return "readback_unverified"
    if isinstance(error,(ValueError,KeyError,TypeError,OverflowError)):
        return "invalid_record"
    return "backend_unclassified"


def count_safe_failure(summary,field,error):
    key=safe_failure_category(error)
    buckets=summary[field]
    buckets[key]=buckets.get(key,0)+1


def replay(cloud=None,local_directory=None):
    started=time.monotonic()
    active=cloud or CloudArchive()
    active.preflight()
    summary={"artifacts":0,"encrypted_buffers":0,
             "first_observation_verified":0,"post_and_media_verified":0,
             "prior_original_preserved":0,"original_media_incomplete":0,
             "buffer_failures":0,"buffer_error_categories":{},
             "buffer_failure_stages":{},
             "artifact_download_failures":0,
             "deferred_buffers":0,
             "batch_sha_verified":0,"batch_ciphertext_count":0,
             "batch_failures":0,"batch_error_categories":{},
             "deferred_artifacts":0,
             "remote_packs_sha_verified":0,"remote_pack_ciphertext_count":0,
             "remote_pack_list_failures":0,"remote_pack_failures":0}
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
        pending=[(None,Path(local_directory))]
        tmp=None
    else:
        tmp=tempfile.TemporaryDirectory(prefix="intersection-recovery-")
        pending=[(name,run_id) for _,run_id,name in candidates]
        if not source_run:
            # Never require an expired GitHub artifact to restore an existing
            # SHA-verified encrypted pack from private TeraBox.
            try:
                packs=select_remote_encrypted_packs(active)
            except (RuntimeError,ValueError,KeyError,TypeError,OSError):
                summary["remote_pack_list_failures"]+=1
                packs=[]
            # The oldest unexpired Actions artifact is still urgent.
            pending=pending[:1]+[(CLOUD_PACK_ITEM,key) for key in packs]+pending[1:]
    deadline=started+MAX_REPLAY_SECONDS
    try:
        for index,item in enumerate(pending):
            # A damaged/slow artifact must not permanently poison unrelated
            # trusted source ZIPs. Stop after six total failed post attempts
            # if the provider really remains unhealthy. The untouched source
            # queue and SHA-verified ciphertext packs survive another run.
            if summary["buffer_failures"]>=MAX_TOTAL_FAILURES:
                summary["deferred_artifacts"]+=len(pending)-index
                break
            consecutive_failures=0
            # Process one artifact immediately; eager downloading all twelve
            # can exhaust the runner without recovering even one original.
            if time.monotonic()>=deadline-MAX_BATCH_SECONDS-MAX_RECORD_SECONDS:
                summary["deferred_artifacts"]+=len(pending)-index
                break
            cloud_pack=False
            if tmp is None:
                _,directory=item
            else:
                name,run_id=item
                directory=Path(tmp.name)/str(index)
                directory.mkdir(mode=0o700)
                cloud_pack=(name==CLOUD_PACK_ITEM)
                if cloud_pack:
                    try:
                        encrypted=with_cloud_budget(
                            active,lambda:extract_verified_remote_pack(
                                active,run_id,directory),
                            max_seconds=MAX_BATCH_SECONDS)
                        summary["remote_packs_sha_verified"]+=1
                        summary["remote_pack_ciphertext_count"]+=len(encrypted)
                    except (RuntimeError,ValueError,KeyError,TypeError,OSError,
                            TimeoutError,zipfile.BadZipFile):
                        summary["remote_pack_failures"]+=1
                        continue
                else:
                    try:
                        _gh(["run","download",str(run_id),"-n",name,"-D",str(directory)],
                            max_bytes=1_000_000)
                    except (RuntimeError,OSError,subprocess.TimeoutExpired):
                        summary["artifact_download_failures"]+=1
                        continue
            encrypted=sorted(directory.glob("*.enc"))
            if not encrypted:
                continue
            summary["artifacts"]+=1
            if len(encrypted)>120:
                summary["buffer_failures"]+=1
                continue
            spool=RecoverySpool(directory)
            # New GitHub artifacts need an immutable encrypted safety pack.
            # Existing cloud packs are already verified: never upload or
            # overwrite them while restoring individual original posts.
            if not cloud_pack:
                try:
                    if with_cloud_budget(
                            active,lambda:preserve_encrypted_batch(active,spool,encrypted),
                            max_seconds=min(MAX_BATCH_SECONDS,max(1,
                                deadline-time.monotonic()-MAX_RECORD_SECONDS))):
                        summary["batch_sha_verified"]+=1
                        summary["batch_ciphertext_count"]+=len(encrypted)
                except (RuntimeError,ValueError,OSError,KeyError,TypeError,TimeoutError) as error:
                    summary["batch_failures"]+=1
                    count_safe_failure(summary,"batch_error_categories",error)
            # Retry different source IDs on later recovery runs rather than
            # forever failing on the same first three immutable keys.
            if len(encrypted)>1:
                seed=int(os.environ.get("GITHUB_RUN_ID","0") or "0")
                offset=seed%len(encrypted)
                encrypted=encrypted[offset:]+encrypted[:offset]
            for offset,path in enumerate(encrypted):
                if time.monotonic()>=deadline-MAX_RECORD_SECONDS:
                    summary["deferred_buffers"]+=len(encrypted)-offset
                    break
                if consecutive_failures>=MAX_CONSECUTIVE_FAILURES:
                    # Source artifacts and any SHA-verified batch remain
                    # untouched, but none of these files count as restored.
                    summary["deferred_buffers"]+=len(encrypted)-offset
                    break
                summary["encrypted_buffers"]+=1
                try:
                    state=restore_with_budget(spool,path,active)
                    summary[state]+=1
                    consecutive_failures=0
                except (RuntimeError,ValueError,KeyError,TypeError,OverflowError,TimeoutError) as error:
                    summary["buffer_failures"]+=1
                    count_safe_failure(summary,"buffer_error_categories",error)
                    stage=getattr(spool,"restore_stage","not_started")
                    safe_stages={"not_started","decrypt","first_observation",
                                 "media_integrity","post_media_remote",
                                 "partial_media_remote"}
                    stage=stage if stage in safe_stages else "unknown"
                    bucket=summary["buffer_failure_stages"]
                    bucket[stage]=bucket.get(stage,0)+1
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
            or result["deferred_buffers"] or result["deferred_artifacts"]
            or result["batch_failures"] or result["remote_pack_list_failures"]
            or result["remote_pack_failures"]):
        raise RuntimeError("private archived recovery buffers still unverified")
