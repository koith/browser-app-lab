#!/usr/bin/env python3
"""Both gallery APIs allow direct viewing while verifying exact SHA-backed bytes."""
import hashlib
import json
import os
os.environ["GALLERY_ACCESS_TOKEN"]="offline-mimmi-test-token"
os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]="offline-fake-cookie"
from fastapi.testclient import TestClient
from gateway import main as gateway

raw=b"verified-mimmi-image-byte-payload"*300
h=hashlib.sha256(raw).hexdigest()
catalog={"schema_version":1,"model":"mimmi","albums":[{"id":"mimmi-test",
    "title":"Offline sample", "images":[{"number":1,"key":"originals/mimmi-test/0001.jpg",
        "bytes":len(raw),"sha256":h,"width":600,"height":800}]}]}
async def read(key,limit,*,remote=None):
    if key=="metadata/catalog.json":return json.dumps(catalog).encode()
    if key=="originals/mimmi-test/0001.jpg":return raw
    raise ValueError("Unexpected key")
gateway.rclone_bytes=read
gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
with TestClient(gateway.app) as client:
    assert client.get("/api/health").status_code==200
    assert client.get("/api/catalog").status_code==200
    headers={"Authorization":"Bearer offline-mimmi-test-token"}
    assert client.get("/api/catalog",headers=headers).json()["model"]=="mimmi"
    img=client.get("/api/media/mimmi-test/1/original",headers=headers)
    assert img.status_code==200 and img.content==raw
    assert img.headers["content-type"].startswith("image/jpeg")
    assert client.get("/api/media/../1/original",headers=headers).status_code!=200
    assert client.get("/api/media/mimmi-test/1/original",headers={"Authorization":"Bearer bad"}).status_code==200
    assert client.get("/api/media/mimmi-test/2/original",headers=headers).status_code==404
    async def wrong(key,limit,*,remote=None):
        if key=="metadata/catalog.json":return json.dumps({"schema_version":1,"model":"yui","albums":[]}).encode()
        return raw
    gateway.rclone_bytes=wrong
    gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
    gateway._cache["catalog"]=None
    assert client.get("/api/catalog",headers=headers).status_code==502
    gateway.rclone_bytes=read
    gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
    gateway._cache["catalog"]=None
    async def corrupted(key,limit,*,remote=None):
        if key=="metadata/catalog.json":return json.dumps(catalog).encode()
        return b"wrong"+raw
    gateway.rclone_bytes=corrupted
    gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
    check=client.get("/api/media/mimmi-test/1/original",headers=headers)
    assert check.status_code==502 and b"integrity" in check.content.lower()
print("MIMMI_GATEWAY_DIRECT_VIEW_AND_SHA_TEST_PASS")


# A single free Render service must never confuse the two model folders.
yui_raw=b"verified-Yui-original-photo-bytes"*300
yui_sha=hashlib.sha256(yui_raw).hexdigest()
yui_preview=b"verified-thumbnail-bytes"*300
yui_preview_sha=hashlib.sha256(yui_preview).hexdigest()
yui_catalog={"schema_version":1,"model":"yui","albums":[{"id":"yui-only",
    "title":"Yui private collection","images":[{"number":4,
       "key":"originals/yui-only/00004-original.jpg","bytes":len(yui_raw),
       "sha256":yui_sha,"preview":"previews/yui-only/00004-preview.webp",
       "preview_bytes":len(yui_preview),"preview_sha256":yui_preview_sha}]}]}
async def both_models(key,limit,*,remote=None):
    if remote=="archive:YuiArchive":
        if key=="metadata/catalog.json":return json.dumps(yui_catalog).encode()
        if key=="originals/yui-only/00004-original.jpg":return yui_raw
        if key=="previews/yui-only/00004-preview.webp":return yui_preview
        raise ValueError("Unknown Yui media request")
    if key=="metadata/catalog.json":return json.dumps(catalog).encode()
    if key=="originals/mimmi-test/0001.jpg":return raw
    raise ValueError("Unknown Mimmi media request")
gateway.rclone_bytes=both_models
gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
gateway._cache["catalog"]=None
gateway._yui_cache["catalog"]=None
with TestClient(gateway.app) as client:
    headers={"Authorization":"Bearer offline-mimmi-test-token"}
    assert client.get("/api/yui/catalog").status_code==200
    loaded=client.get("/api/yui/catalog",headers=headers)
    assert loaded.status_code==200 and loaded.json()["model"]=="yui"
    photo=client.get("/api/yui/media/yui-only/4/original",headers=headers)
    assert photo.status_code==200 and photo.content==yui_raw
    preview=client.get("/api/yui/media/yui-only/4/preview",headers=headers)
    assert preview.status_code==200 and preview.content==yui_preview
    assert client.get("/api/yui/media/yui-only/5/original",headers=headers).status_code==404
    assert client.get("/api/catalog",headers=headers).json()["model"]=="mimmi"
    assert client.get("/api/yui/media/yui-only/4/original",
                      headers={"Authorization":"Bearer invalid"}).status_code==200
    async def mismatch(key,limit,*,remote=None):
        if key=="metadata/catalog.json" and remote=="archive:YuiArchive":
            return json.dumps(yui_catalog).encode()
        return b"corrupted"
    gateway.rclone_bytes=mismatch
    gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
    failed=client.get("/api/yui/media/yui-only/4/original",headers=headers)
    assert failed.status_code==502 and b"SHA" in failed.content
print("YUI_AND_MIMMI_SHARED_RENDER_GATEWAY_DIRECT_VIEW_SHA_MODEL_ISOLATION_PASS")


# Actual lightweight preview bytes must be read from previews/, not the original.
preview_data=b"mimmi-small-verified-webp-thumbnail"*100
preview_sha=hashlib.sha256(preview_data).hexdigest()
preview_catalog=json.loads(json.dumps(catalog))
preview_catalog["albums"][0]["images"][0].update({
    "preview":"previews/mimmi-test/0001-small.webp",
    "preview_sha256":preview_sha,
    "preview_bytes":len(preview_data),
})
async def preview_read(key,limit,*,remote=None):
    if key=="metadata/catalog.json":return json.dumps(preview_catalog).encode()
    if key=="previews/mimmi-test/0001-small.webp":return preview_data
    if key=="originals/mimmi-test/0001.jpg":return raw
    raise ValueError("Unexpected archive asset")
gateway.rclone_bytes=preview_read
gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
gateway._cache["catalog"]=None
with TestClient(gateway.app) as client:
    auth={"Authorization":"Bearer offline-mimmi-test-token"}
    thumb=client.get("/api/media/mimmi-test/1/preview",headers=auth)
    assert thumb.status_code==200 and thumb.content==preview_data
    assert thumb.headers["content-type"].startswith("image/webp")
    full=client.get("/api/media/mimmi-test/1/original",headers=auth)
    assert full.status_code==200 and full.content==raw
    async def corrupt_preview(key,limit,*,remote=None):
        if key=="previews/mimmi-test/0001-small.webp":return b"incorrect-thumbnail"
        return await preview_read(key,limit,remote=remote)
    gateway.rclone_bytes=corrupt_preview
    gateway._media_cache.clear()  # The next test must exercise its new origin fixture.
    failed=client.get("/api/media/mimmi-test/1/preview",headers=auth)
    assert failed.status_code==200 and failed.content==raw
    assert failed.headers['X-Archive-Variant']=='verified-original-fallback'
    assert hashlib.sha256(failed.content).hexdigest()==h
    async def both_corrupted(key,limit,*,remote=None):
        if key=='metadata/catalog.json':return json.dumps(preview_catalog).encode()
        return b'incorrect-original-and-preview'
    gateway.rclone_bytes=both_corrupted
    gateway._media_cache.clear()
    failed=client.get('/api/media/mimmi-test/1/preview',headers=auth)
    assert failed.status_code==502 and b'SHA' in failed.content
print("MIMMI_SEPARATE_PREVIEW_SHA_REMOTE_BYTE_QA_PASS")
