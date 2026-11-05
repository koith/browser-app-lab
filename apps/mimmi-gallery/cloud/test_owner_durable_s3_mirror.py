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

    gw._DURABLE_OWNER_READY=False
    assert gw.durable_owner_remote("mimmi") is None
    assert gw.durable_owner_remote("yui") is None
    print("PRIVATE_DURABLE_FEATURE_DISABLED_WHEN_NOT_CONFIGURED_PASS")
finally:
    gw._DURABLE_OWNER_READY,gw._DURABLE_OWNER_BASE=prior
    gw._media_cache.clear()
