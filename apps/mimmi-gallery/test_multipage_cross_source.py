#!/usr/bin/env python3
"""No 10-photo V2PH cap; recover exact SHA-matched public URLs from other hosts."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import discover_v2ph_actor as actor
import build_model_gallery as builder
import publish_stored_public as publisher

def verify_130_photo_pagination():
    class Response:
        def __init__(self,url):
            self.url=url
            self.content=b"<html><h1>Mimmi Verified Album</h1></html>"
        def raise_for_status(self):pass
    def fetch(url,**_):
        return Response(url)
    def list_photos(soup,url):
        n=int(parse_qs(urlsplit(url).query).get("page",["1"])[0])
        if n>13:return []
        return [f"https://cdn.v2ph.com/photos/{n:03}-{i:03}.jpg" for i in range(10)]
    def verified(url):
        return {"url":url,"sha256":hashlib.sha256(url.encode()).hexdigest(),
                "bytes":15000,"width":800,"height":1200}
    with patch.object(actor.S,"get",side_effect=fetch), \
         patch.object(actor,"photos_on_page",side_effect=list_photos), \
         patch.object(actor,"get_bytes_verified",side_effect=verified), \
         patch.object(actor.time,"sleep"):
        a=actor.verify_album({"id":"v2ph-actor-abc123","title":"Mimmi","source":"https://www.v2ph.com/album/abc123.html"},
                             max_samples=180,max_album_pages=35)
    assert len(a["samples"])==130,len(a["samples"])
    assert [p["number"] for p in a["samples"]]==list(range(1,131))
    assert len(a["pages"])==14, a["pages"]
    assert a["pages"][0]["candidate_images"]==10
    assert a["pages"][12]["candidate_images"]==10
    assert a["pages"][13]["candidate_images"]==0

def verify_batch_rotation():
    catalog=[{"id":f"v2ph-actor-test{i:02}","title":"Mimmi Test","source":f"https://www.v2ph.com/album/test{i:02}.html"} for i in range(22)]
    touched=[]
    def fake_verify(a,max_samples,max_album_pages,browser_scroll=False):
        touched.append((a["id"],max_samples,max_album_pages))
        return {**a,"samples":[],"images":[],"pages":[],"status":"source_only"}
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        with patch.object(actor,"ROOT",root),patch.object(actor,"scan_actor",return_value=(catalog,[])), \
             patch.object(actor,"verify_album",side_effect=fake_verify):
            actor.run(8,30,180,35,batch_index=1,batch_size=8)
        assert len(touched)==8
        assert touched[0][0]=="v2ph-actor-test08",touched
        assert touched[-1][0]=="v2ph-actor-test15",touched
        assert all(x[1:]==(180,35) for x in touched)

def verify_sha_identical_alternates():
    digest=hashlib.sha256(b"fake image bytes").hexdigest()
    a={"title":"Mimmi Some Edition","id":"mimmi-a","publisher":"DJAWA",
       "source":"https://djawaphoto.com/portfolio/a/",
       "samples":[{"url":"https://djawaphoto.com/wp-content/uploads/2026/10/a.jpg",
                   "sha256":digest,"bytes":15000,"width":800,"height":1200}]}
    b={"title":"Mimmi Some Edition","id":"mimmi-b","publisher":"DJAWA",
       "source":"https://www.v2ph.com/album/a12345.html",
       "samples":[{"url":"https://cdn.v2ph.com/photos/a.jpg",
                   "sha256":digest,"bytes":15000,"width":800,"height":1200}]}
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"official-previews.json").write_text(json.dumps({"albums":[a]}))
        (root/"v2ph-public-previews.json").write_text(json.dumps({"albums":[b]}))
        with patch.object(builder,"FILES",[("official","official-previews.json"),("v2ph_seed","v2ph-public-previews.json")]):
            result=builder.build(root)
        assert result["summary"]["verified_unique_source_images"]==1
        assert result["summary"]["photos_with_alternative_public_source"]==1
        photo=result["albums"][0]["images"][0]
        assert photo["alternate_source_urls"]==["https://cdn.v2ph.com/photos/a.jpg"],photo
        attempts=[]
        def stub(url,sha,length):
            attempts.append(url)
            if url==photo["url"]:raise ValueError("public original temporarily unavailable")
            assert sha==digest and length==15000
            return b"fake image bytes"
        data,url=publisher.fetch_from_verified_alternates(photo,downloader=stub)
        assert url=="https://cdn.v2ph.com/photos/a.jpg"
        assert data==b"fake image bytes" and len(attempts)==2
        assert publisher.fetch_from_verified_alternates is not None

if __name__=="__main__":
    verify_130_photo_pagination()
    verify_batch_rotation()
    verify_sha_identical_alternates()
    print("MIMMI_FULL_ALBUM_130_PHOTOS_ROTATING_BATCH_CROSS_SOURCE_SHA_FAILOVER_PASS")
