#!/usr/bin/env python3
"""No-network owner-private S3 mirror: same SHA, never public blobs or bypass.

Feature stays inert without explicit S3 private credentials; fail closed on
corrupt replica bytes. TeraBox remains canonical and unmodified.
"""
import asyncio
import hashlib
import os
from unittest.mock import patch
from fastapi import HTTPException
from gateway import main as gw

payload=b"already-verified-private-original-bytes"
digest=hashlib.sha256(payload).hexdigest()
key="originals/verified-work/00001.jpg"
prior=(gw._DURABLE_OWNER_READY,gw._DURABLE_OWNER_BASE)
try:
    gw._DURABLE_OWNER_READY=True
    gw._DURABLE_OWNER_BASE="ownerreplica:private-mirror"
    assert gw.durable_owner_remote("mimmi")=="ownerreplica:private-mirror/mimmi"
    assert gw.durable_owner_remote("yui")=="ownerreplica:private-mirror/yui"
    assert gw.durable_owner_remote("other") is None

    calls=[]
    async def exact(path,limit,remote=None,cookie_override=None):
        calls.append((path,remote))
        if remote.startswith("ownerreplica:"):
            return payload
        raise AssertionError("Owner live source was read despite valid private mirror")

    gw._media_cache.clear()
    with patch.object(gw,"rclone_bytes",side_effect=exact):
        got=asyncio.run(gw.verified_remote_media(key,len(payload),digest,gw.REMOTE))
    assert got==payload and len(calls)==1 and calls[0][1].endswith("/mimmi")
    print("PRIVATE_DURABLE_OWNER_MIRROR_SHA_SOURCE_PRIORITY_PASS")

    async def wrong(path,limit,remote=None,cookie_override=None):
        if remote.startswith("ownerreplica:"):
            return payload+b"-tampered"
        raise AssertionError("Corrupted owner mirror may not silently downgrade integrity")
    gw._media_cache.clear()
    with patch.object(gw,"rclone_bytes",side_effect=wrong):
        try:asyncio.run(gw.verified_remote_media(key,len(payload),digest,gw.YUI_REMOTE))
        except HTTPException as ex:assert ex.status_code==502
        else:raise AssertionError("Mirror SHA mismatch returned media")
    print("PRIVATE_DURABLE_CORRUPT_ORIGINAL_FAIL_CLOSED_PASS")

    calls.clear()
    async def mirror_missing(path,limit,remote=None,cookie_override=None):
        calls.append(remote)
        if remote.startswith("ownerreplica:"):
            raise HTTPException(status_code=503,detail="Mirror not provisioned yet")
        if remote==gw.YUI_REMOTE:return payload
        raise AssertionError("Wrong owner account used")
    gw._media_cache.clear()
    with patch.object(gw,"rclone_bytes",side_effect=mirror_missing):
        got=asyncio.run(gw.verified_remote_media(key,len(payload),digest,gw.YUI_REMOTE))
    assert got==payload and calls[0].endswith("/yui") and calls[-1]==gw.YUI_REMOTE
    print("PRIVATE_DURABLE_MISSING_OBJECT_SAME_OWNER_FALLBACK_PASS")

    # Catalogs are always revalidated by existing model/schema guards.
    calls.clear()
    with patch.object(gw,"rclone_bytes",side_effect=mirror_missing):
        got=asyncio.run(gw.catalog_source_bytes("yui",1000))
    assert got==payload and calls[0].endswith("/yui") and calls[-1]==gw.YUI_REMOTE
    print("PRIVATE_DURABLE_CATALOG_SAME_OWNER_FAILOVER_PASS")

    class Stream:
        def __init__(self,parts):
            self.parts=list(parts)
        async def read(self,size):
            return self.parts.pop(0) if self.parts else b""
    class Process:
        returncode=0
        stdout=Stream([b'{"schema_version":1,"model":"mimmi"}'])
        stderr=Stream([])
        async def wait(self):return 0
        def kill(self):raise AssertionError("Healthy mirror process killed")
    async def subprocess_fake(*argv,**kwargs):
        assert "ownerreplica:private-mirror/mimmi/metadata/catalog.json" in argv
        return Process()
    with patch.object(gw,"cookie_header",side_effect=AssertionError(
            "S3 reader must not require or normalize TeraBox owner cookies")),patch.object(
                gw.asyncio,"create_subprocess_exec",side_effect=subprocess_fake):
        raw=asyncio.run(gw.rclone_bytes("metadata/catalog.json",4096,
                       remote=gw.durable_owner_remote("mimmi")))
        assert b'"model":"mimmi"' in raw
    print("PRIVATE_DURABLE_COLD_START_S3_NEVER_REQUIRES_TERABOX_COOKIE_PASS")

    gw._DURABLE_OWNER_READY=False
    assert gw.durable_owner_remote("mimmi") is None
    assert gw.durable_owner_remote("yui") is None
    print("PRIVATE_DURABLE_FEATURE_DISABLED_WHEN_NOT_CONFIGURED_PASS")
finally:
    gw._DURABLE_OWNER_READY,gw._DURABLE_OWNER_BASE=prior
    gw._media_cache.clear()
