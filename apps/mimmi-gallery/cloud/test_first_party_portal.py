#!/usr/bin/env python3
"""Owner gallery login: two model catalogs, first-party cookie, no leaked token."""
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
    raise AssertionError(("Unauthorized public asset",model,asset))
portal.public_asset=fake_public_asset

with TestClient(backend.app,base_url="https://testserver") as client:
    assert client.get("/gallery/yui/").status_code==200
    assert "접근 코드" in client.get("/gallery/yui/").text
    assert client.get("/gallery/yui/owner-media.js").status_code==401
    assert client.get("/api/yui/catalog").status_code==401
    wrong=client.post("/gallery/login",data={"model":"yui","code":"incorrect"})
    assert wrong.status_code==200 and "접근 코드를 확인" in wrong.text
    assert portal.COOKIE_NAME not in wrong.cookies
    valid=client.post("/gallery/login",data={"model":"yui","code":TOKEN},
                      follow_redirects=False)
    assert valid.status_code==303 and valid.headers["location"]=="/gallery/yui/"
    assert "httponly" in valid.headers["set-cookie"].lower()
    assert "secure" in valid.headers["set-cookie"].lower()
    assert "samesite=lax" in valid.headers["set-cookie"].lower()
    assert TOKEN not in valid.headers["set-cookie"]
    assert portal.COOKIE_NAME in client.cookies
    assert client.get("/gallery/yui/").status_code==200
    assert "FIRST PARTY GALLERY" in client.get("/gallery/mimmi/").text
    assert client.get("/gallery/mimmi/owner-media.js").status_code==200
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
    logout=client.post("/gallery/logout",follow_redirects=False)
    assert logout.status_code==303
    assert client.get("/api/yui/catalog").status_code==401
    assert "접근 코드" in client.get("/gallery/yui/").text

assert not portal.session_valid(TOKEN,"12345.bad")
assert not portal.session_valid(TOKEN,portal.session_sign("different-key",int(__import__('time').time())+200))
assert not portal.session_valid(TOKEN,portal.session_sign(TOKEN,int(__import__('time').time())-10))
print("FIRST_PARTY_YUI_MIMMI_REAL_BYTES_COOKIE_BROWSER_ENTRY_SECURITY_PASS")
