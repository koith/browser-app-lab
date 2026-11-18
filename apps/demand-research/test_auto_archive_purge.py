"""Offline, synthetic-only verification of owner-scoped automatic archive erasure."""
from __future__ import annotations

import json

import pytest

from auto_archive_purge import (
    identity, marker_key, matches, read_blocks, purge_account, unblock_account,
)
from demand_archive import CloudArchive, canonical_json, sha256

A="a"*40
B="b"*40
P_A="https://bsky.app/profile/blocked.bsky.social"
P_B="https://bsky.app/profile/allowed.bsky.social"
DID_A="did:plc:abcdefghjklmnopqrstuvx"


class MemoryCloud:
    remote="archive:DemandResearch"

    def __init__(self,blocked_delete=False):
        self.items={}
        self.rows=[]
        self.blocked_delete=blocked_delete
        self.published=0

    flat_storage_key=staticmethod(CloudArchive.flat_storage_key)

    def names(self,folder):
        return sorted(k[len(folder)+1:] for k in self.items
                      if k.startswith(folder+"/") and "/" not in k[len(folder)+1:])

    def read(self,key,*,cap=100_000,optional=False,**_):
        data=self.items.get(key)
        if data is None and not optional:
            raise RuntimeError("missing cloud object")
        if data is not None and len(data)>cap:
            raise ValueError("oversize")
        return data

    def read_verified(self,key,digest,*,cap=100_000):
        data=self.read(key,cap=cap,optional=True)
        return data if data is not None and sha256(data)==digest else None

    def write_immutable(self,key,data):
        old=self.items.get(key)
        if old is not None and old!=data:
            raise RuntimeError("immutable conflict")
        self.items[key]=data

    def load_catalog(self,*,include_entries=True):
        return list(self.rows)

    def publish_catalog(self,by_id,run_id):
        self.rows=list(by_id.values())
        self.published+=1
        return {"posts":len(self.rows)}

    def command(self,args,*,timeout=45,allow_missing=False,**_):
        assert args[0] in ("deletefile","cat"),args
        assert args[1].startswith(self.remote+"/")
        key=args[1][len(self.remote)+1:]
        if self.blocked_delete and key.startswith("posts/"+A):
            raise RuntimeError("private cloud denied physical deletion")
        if args[0]=="deletefile":
            if key in self.items:
                del self.items[key]
                return b""
            return None if allow_missing else b""
        data=self.items.get(key)
        return data[:1] if data is not None else None


def make_post(pid,profile,source,with_media=False):
    media=[]
    if with_media:
        media=[{"key":"posts/"+pid+"/media/0001.jpg","mime":"image/jpeg",
                "sha256":"b"*64,"bytes":4}]
    return {"id":pid,"platform":"bluesky","profile_url":profile,
            "source_url":source,"text":"synthetic only", "media":media,
            "media_expected":1 if with_media else 0}


def seed():
    cloud=MemoryCloud()
    blocked=make_post(A,"https://bsky.app/profile/"+DID_A,
                      "https://bsky.app/profile/"+DID_A+"/post/a",True)
    other=make_post(B,P_B,P_B+"/post/b")
    cloud.rows=[blocked,other]
    for key in (
        "posts/"+A+"/post.json","posts/"+A+"/capture.json",
        "posts/"+A+"/media/0001.jpg","metadata/entries/"+A+".json",
        "metadata/early-"+A+".json","metadata/media-parts/"+A+"/0001.json",
        "posts/"+B+"/post.json",
        "account-archives/bluesky/fake/manual-profile.json",
    ):
        cloud.items[key]=b"archive-original"
        flat=cloud.flat_storage_key(key)
        if flat:
            cloud.items[flat]=b"archive-original"
    return cloud,blocked,other


def test_only_blocked_auto_posts_physically_erased_and_manual_backups_preserved():
    cloud,blocked,other=seed()
    target=identity("bluesky",P_A,DID_A)
    assert matches(blocked,target)
    assert not matches(other,target)
    assert not matches(blocked,identity("bluesky",P_B))
    result=purge_account(cloud,target)
    assert result=={"state":"purged","matched_posts":1,
                    "deleted_posts":1,"remaining_posts":0}
    assert cloud.published==1
    assert list(cloud.rows)==[other]
    assert cloud.items["posts/"+B+"/post.json"]==b"archive-original"
    assert cloud.items["account-archives/bluesky/fake/manual-profile.json"]==b"archive-original"
    assert "posts/"+A+"/post.json" not in cloud.items
    assert "metadata/flat-blob-"+sha256(("posts/"+A+"/post.json").encode())+".bin" not in cloud.items
    assert "posts/"+A+"/media/0001.jpg" not in cloud.items
    assert read_blocks(cloud)==[target]
    assert purge_account(cloud,target)["deleted_posts"]==0
    assert unblock_account(cloud,target)=={"state":"unblocked"}
    assert read_blocks(cloud)==[]
    assert cloud.rows==[other], "unblock must never resurrect erased records"


def test_failed_source_delete_is_never_claimed_as_success():
    cloud,blocked,other=seed()
    cloud.blocked_delete=True
    target=identity("bluesky",P_A,DID_A)
    with pytest.raises(RuntimeError,match="denied"):
        purge_account(cloud,target)
    assert cloud.published==0
    assert cloud.rows==[blocked,other]
    assert read_blocks(cloud)==[target], "verified exclusion must persist across retry"
    assert cloud.items["posts/"+B+"/post.json"]==b"archive-original"


@pytest.mark.parametrize("platform,url,did",[
    ("x",P_A,""),("bluesky","http://bsky.app/profile/blocked.bsky.social",""),
    ("bluesky","https://evil.example/profile/blocked.bsky.social",""),
    ("bluesky",P_A,"did:plc:../../bad")
])
def test_reject_unsafe_block_scope(platform,url,did):
    with pytest.raises(ValueError):
        identity(platform,url,did)


def test_block_identity_hash_is_exact_and_unchanged():
    target=identity("bluesky",P_A,DID_A)
    key=marker_key(target)
    assert key.startswith("metadata/blocked-auto-v1-")
    assert key.endswith(".json")
    assert key!=marker_key(identity("bluesky",P_A))
