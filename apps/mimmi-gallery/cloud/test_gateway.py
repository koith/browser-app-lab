#!/usr/bin/env python3
"""Mimmi-only private API, bearer authorization, exact bytes, wrong model rejection."""
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
with TestClient(gateway.app) as client:
    assert client.get("/api/health").status_code==200
    assert client.get("/api/catalog").status_code==401
    headers={"Authorization":"Bearer offline-mimmi-test-token"}
    assert client.get("/api/catalog",headers=headers).json()["model"]=="mimmi"
    img=client.get("/api/media/mimmi-test/1/original",headers=headers)
    assert img.status_code==200 and img.content==raw
    assert img.headers["content-type"].startswith("image/jpeg")
    assert client.get("/api/media/../1/original",headers=headers).status_code!=200
    assert client.get("/api/media/mimmi-test/1/original",headers={"Authorization":"Bearer bad"}).status_code==401
    assert client.get("/api/media/mimmi-test/2/original",headers=headers).status_code==404
    async def wrong(key,limit,*,remote=None):
        if key=="metadata/catalog.json":return json.dumps({"schema_version":1,"model":"yui","albums":[]}).encode()
        return raw
    gateway.rclone_bytes=wrong
    gateway._cache["catalog"]=None
    assert client.get("/api/catalog",headers=headers).status_code==502
    gateway.rclone_bytes=read
    gateway._cache["catalog"]=None
    async def corrupted(key,limit,*,remote=None):
        if key=="metadata/catalog.json":return json.dumps(catalog).encode()
        return b"wrong"+raw
    gateway.rclone_bytes=corrupted
    check=client.get("/api/media/mimmi-test/1/original",headers=headers)
    assert check.status_code==502 and b"integrity" in check.content.lower()
print("MIMMI_PRIVATE_GATEWAY_AUTH_AND_SHA_TEST_PASS")
