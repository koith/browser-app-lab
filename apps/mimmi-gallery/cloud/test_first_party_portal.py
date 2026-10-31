#!/usr/bin/env python3
"""Passwordless gallery: two model catalogs and real SHA-verified bytes."""
from __future__ import annotations
import hashlib
import os
os.environ["GALLERY_ACCESS_TOKEN"] = "strong-offline-test-token-do-not-deploy"
os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"] = "offline-test-cookie"
from fastapi.testclient import TestClient
from gateway import main as backend, portal

TOKEN=os.environ["GALLERY_ACCESS_TOKEN"]
yui_photo=b"private-yui-original-bytes"*300
mimmi_photo=b"private-mimmi-original-bytes"*300
def catalog(model):
    photo=yui_photo if model=="yui" else mimmi_photo
    h=hashlib.sha256(photo).hexdigest()
    album=f"{model}-test"
    return {"schema_version":1,"model":model,"albums":[{
        "id":album,"title":"Real private bytes","images":[{
            "number":1,"key":f"originals/{album}/1.jpg",
            "bytes":len(photo),"sha256":h,"width":600,"height":800
        }]
    }]}

async def get_yui():return catalog("yui")
async def get_mimmi():return catalog("mimmi")
backend.yui_catalog_bytes=get_yui
backend.get_catalog=get_mimmi
async def read(key,limit,*,remote=None):
    if key=="originals/yui-test/1.jpg" and remote=="archive:YuiArchive":return yui_photo
    if key=="originals/mimmi-test/1.jpg":return mimmi_photo
    raise RuntimeError("Unexpected private TeraBox request")
backend.rclone_bytes=read

async def fake_public_asset(model,asset):
    if asset=="index.html":
        return (f'<html><body>{model} FIRST PARTY GALLERY</body></html>'.encode(),"text/html")
    if asset=="stored-albums.json":
        return (b'{"albums":[]}',"application/json")
    if asset=="owner-media.js":
        return (b"window.PrivateTest=true;","application/javascript")
    if asset=="album-grouping.js" and model=="mimmi":
        return (b"window.MimmiAlbumGrouping={};","application/javascript")
    if asset in ("owner-index.json", "number-collision-distinct.json"):
        return (b'{"schema_version":1,"albums":[]}',"application/json")
    raise AssertionError(("Unauthorized public asset",model,asset))
portal.public_asset=fake_public_asset

with TestClient(backend.app,base_url="https://testserver") as client:
    for model in ("yui", "mimmi"):
        page=client.get(f"/gallery/{model}/")
        assert page.status_code==200
        assert f"{model} FIRST PARTY GALLERY" in page.text
        assert 'type="password"' not in page.text
        assert "접근 코드" not in page.text
        script=client.get(f"/gallery/{model}/owner-media.js")
        assert script.status_code==200
        assert "PrivateTest" in script.text
        # A mounted Render gallery must serve the same public metadata files
        # as GitHub Pages, not silently fail the owner album index.
        owner_index=client.get(f"/gallery/{model}/owner-index.json")
        assert owner_index.status_code==200
        assert owner_index.json()["schema_version"]==1

    # Mimmi depends on album-grouping.js during its initial render; the
    # number-collision manifest is needed for distinct committed photos.
    assert client.get("/gallery/mimmi/album-grouping.js").status_code==200
    assert client.get("/gallery/mimmi/number-collision-distinct.json").status_code==200

    assert client.get("/gallery/yui/stored-albums.json").json()=={"albums":[]}
    assert client.get("/api/yui/catalog").json()["model"]=="yui"
    assert client.get("/api/catalog").json()["model"]=="mimmi"
    assert client.get("/api/yui/media/yui-test/1/original").content==yui_photo
    assert client.get("/api/media/mimmi-test/1/original").content==mimmi_photo
    redirect=client.get("/gallery/yui/stored-albums/yui-test/hash123.jpg",
                        follow_redirects=False)
    assert redirect.status_code==307
    assert redirect.headers["location"].startswith("https://koith.github.io/")
    assert client.get("/gallery/yui/../../unknown").status_code!=200

    # Removed login and logout endpoints must never reintroduce the prompt.
    assert client.post("/gallery/login",data={"model":"yui","code":TOKEN}).status_code in (404,405)
    assert client.post("/gallery/logout").status_code in (404,405)
    assert portal.COOKIE_NAME not in client.cookies
    assert "FIRST PARTY GALLERY" in client.get("/gallery/yui/").text

print("FIRST_PARTY_YUI_MIMMI_PASSWORDLESS_REAL_BYTES_QA_PASS")
