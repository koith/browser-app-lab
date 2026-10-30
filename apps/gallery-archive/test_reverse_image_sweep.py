#!/usr/bin/env python3
"""Offline regression: image-first search prioritization and Yandex JSON."""
import html
import json
import tempfile
from pathlib import Path

from reverse_seed_priority import seeds
from reverse_sites_parser import sites_from_html
from reverse_image_sweep import search_one,sweep
from reverse_image_discovery import untrack

def fixture(base):
    for model in ("mimmi","yui"):
        p=base/(model+"-gallery")
        p.mkdir()
        (p/"stored-albums.json").write_text(json.dumps({"model":model,"albums":[]}))
        albums=[]
        for aid,count in (("one",3),("full",75)):
            photos=[{"number":n+1,"sha256":f"{(n+1)%10}"*64,
                     "bytes":150000,"preview_sha256":"b"*64}
                    for n in range(count)]
            albums.append({"id":aid,"title":("Mimmi" if model=="mimmi" else "Yui")+" Red Shirt",
                           "images":photos})
        (p/"owner-index.json").write_text(json.dumps({
            "schema_version":1,"storage":"sha-verified-owner-metadata-only",
            "model":model,"albums":albums}))

class FakeResponse:
    status_code=200
    headers={"Content-Type":"text/html"}
    def __init__(self,text):
        self.text=text
        self.content=text.encode()

class FakeClient:
    def get(self,url,params=None,**kw):
        assert kw.get("allow_redirects") is False
        record={"initialState":{"cbirSites":{"sites":[{
            "url":"https://www.v2ph.com/album/some.html?utm_source=yandexsmartcamera",
            "title":"DJAWA Mimmi Red Shirt",
            "originalImage":{"url":"https://cdn.v2ph.com/photos/frame.jpg",
                             "width":2200,"height":3300}
        }]}}}
        text='<div data-state="'+html.escape(json.dumps(record))+'"></div>'
        return FakeResponse(text)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        fixture(base)
        entries=seeds(base)
        assert len(entries)==12,len(entries)
        assert entries[0]["owner_saved_count"]==3,entries
        assert entries[0]["seed_kind"]=="public-gateway-cover"
        assert all("cookie" not in s["public_image_url"] for s in entries)
        matches=sites_from_html(FakeClient().get("",{},allow_redirects=False).text,untrack)
        assert len(matches)==1,matches
        assert matches[0]["matched_width"]==2200,matches
        accepted=search_one(entries[0],FakeClient())
        if entries[0]["model"]=="mimmi":
            assert len(accepted["candidate_pages"])==1,accepted
        scan=sweep(base,4,0,workers=2,client_factory=FakeClient)
        assert scan["seed_queries"]==4,scan
        assert scan["unique_albums_queried"]==4,scan
        assert scan["gallery_photos_new"]==0,scan
        assert scan["physical_photos_new"]==0,scan
        assert scan["research_only"],scan
    print("IMAGE_FIRST_AGGRESSIVE_SOURCE_FIXTURE_PASS")

if __name__=="__main__":
    main()
