"""Owner-requested exclusions and erasure for AUTOMATIC public-post archive only.

Never touch /account-archives (explicit selected-account backups), private
account indexes, or records of another author. Immutable historical catalogs
contain checksums only; new catalogs are published after verified physical
deletion of the exact account-owned post objects and their shallow replicas.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from urllib.parse import urlsplit

from account_index import profile_url as normalize_profile, from_original
from demand_archive import CloudArchive, canonical_json

_LOCK=threading.Lock()
_MARK_RE=re.compile(r"^blocked-auto-v1-([a-f0-9]{64})\.json$")
_DID_RE=re.compile(r"^did:(?:plc|web):[A-Za-z0-9.:%_-]{6,180}$")
_PID_RE=re.compile(r"^[a-f0-9]{40}$")
_MAX_PER_PURGE=25


def identity(platform, profile, author_did=""):
    normalized=normalize_profile(profile)
    if normalized is None or normalized[0]!=platform:
        raise ValueError("invalid public source profile")
    did=(author_did or "").lower().strip()
    if did and (platform!="bluesky" or not _DID_RE.fullmatch(did)):
        raise ValueError("invalid public source identity")
    return {"platform":platform,"profile_url":normalized[1],"author_did":did}


def marker_key(account):
    if not isinstance(account,dict):
        raise ValueError("invalid blocked account")
    value=account["platform"]+"|"+account["profile_url"]+"|"+account["author_did"]
    return "metadata/blocked-auto-v1-"+hashlib.sha256(value.encode()).hexdigest()+".json"


def matches(post,account):
    if not isinstance(post,dict) or post.get("platform")!=account["platform"]:
        return False
    for field in ("profile_url","source_url"):
        raw=post.get(field)
        p=normalize_profile(raw) if field=="profile_url" else from_original(raw)
        if p is not None and p==(account["platform"],account["profile_url"]):
            return True
        if (p is not None and account["platform"]=="bluesky"
                and account["author_did"]
                and p[1]=="https://bsky.app/profile/"+account["author_did"]):
            return True
    return False


def read_blocks(cloud):
    """Load only exact private metadata exclusion markers; no user data logs."""
    names=cloud.names("metadata")
    result=[]
    markers=[name for name in names if _MARK_RE.fullmatch(name)]
    if len(markers)>1000:
        raise RuntimeError("manual auto-archive exclusions exceed safe limit")
    for name in markers:
        raw=cloud.read("metadata/"+name,cap=1200,optional=True)
        if raw is None:
            raise RuntimeError("private exclusion marker unreadable")
        try:
            value=json.loads(raw)
            record=identity(value["platform"],value["profile_url"],
                            value.get("author_did",""))
        except (TypeError,ValueError,KeyError,UnicodeError):
            raise RuntimeError("invalid stored archive exclusion") from None
        if marker_key(record)!="metadata/"+name:
            raise RuntimeError("archive exclusion identity mismatch")
        result.append(record)
    return result


def block(cloud, account):
    key=marker_key(account)
    raw=canonical_json(account)
    cloud.write_immutable(key,raw)
    if cloud.read_verified(key,hashlib.sha256(raw).hexdigest(),cap=1300)!=raw:
        raise RuntimeError("durable blocked-account verification failed")
    return key


def _remove_physical(cloud,key):
    """Delete exactly one verified source-specific file plus the optional flat copy.

    Failed readback (including TeraBox authorization denial) is NOT success.
    """
    if (not isinstance(key,str) or ".." in key or "\\" in key
            or not re.fullmatch(r"[A-Za-z0-9_./-]{4,250}",key)
            or not key.startswith(("posts/","metadata/"))):
        raise ValueError("unsafe deletion key")
    paths=[key]
    flat=cloud.flat_storage_key(key)
    if flat and flat not in paths:
        paths.append(flat)
    for target in paths:
        cloud.command(["deletefile",cloud.remote+"/"+target,"--retries","2"],
                      timeout=45,allow_missing=True)
        for domain in (None,"https://nephobox.com"):
            data=cloud._read_physical(target,cap=1,optional=True,domain=domain)
            if data is not None:
                raise RuntimeError("private archive erasure readback not empty")


def erase_post(cloud,post):
    """Delete media/early records first; post and catalog marker LAST.

    A retry can still find the original post until post.json has been removed.
    Other account archives are not addressed.
    """
    pid=post.get("id","")
    if not _PID_RE.fullmatch(str(pid)):
        raise ValueError("invalid saved public post id")
    keys=[]
    for item in post.get("media",[]):
        media=item.get("key","") if isinstance(item,dict) else ""
        if (not isinstance(media,str) or not media.startswith("posts/"+pid+"/media/")
                or ".." in media or "\\" in media or not re.fullmatch(r"[A-Za-z0-9_./-]{4,250}",media)):
            raise ValueError("invalid account-bound media key")
        keys.append(media)
    # Extra first-sighting records and image-part slots are also account data.
    keys.extend(["posts/"+pid+"/capture.json","metadata/early-"+pid+".json"])
    for i in range(1,17):
        keys.append("metadata/media-parts/"+pid+"/"+str(i).zfill(4)+".json")
    for key in dict.fromkeys(keys):
        _remove_physical(cloud,key)
    # post.json is removed only after its owned media passed physical readback.
    _remove_physical(cloud,"posts/"+pid+"/post.json")
    _remove_physical(cloud,"metadata/entries/"+pid+".json")
    _remove_physical(cloud,"metadata/entries-repaired/"+pid+".json")


def purge_account(cloud,account,*,maximum=_MAX_PER_PURGE):
    if not isinstance(maximum,int) or not 1<=maximum<=_MAX_PER_PURGE:
        raise ValueError("invalid deletion batch")
    with _LOCK:
        block(cloud,account)
        # This is ONLY the automatic feed catalog. Never load selected-account ZIPs.
        rows=cloud.load_catalog(include_entries=True)
        targets=[row for row in rows if matches(row,account)]
        count=0
        for row in targets[:maximum]:
            erase_post(cloud,row)
            count+=1
        if count:
            # Publish an updated SHA-verified catalog excluding the removed IDs.
            # A fresh run id avoids changing any previous immutable manifest.
            surviving={row["id"]:row for row in rows
                       if row["id"] not in {p["id"] for p in targets[:count]}}
            cloud.publish_catalog(surviving,str(time.time_ns()))
        return {"state":"purged" if len(targets)==count else "pending",
                "matched_posts":len(targets),"deleted_posts":count,
                "remaining_posts":max(0,len(targets)-count)}


def unblock_account(cloud,account):
    with _LOCK:
        key=marker_key(account)
        _remove_physical(cloud,key)
        return {"state":"unblocked"}
