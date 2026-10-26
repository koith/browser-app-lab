#!/usr/bin/env python3
"""Local no-credential public-only test of four new Yui web-preview selectors."""
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image
from crawl_v2ph_public import TARGETS,MAX_FREE_IMAGES,public_photo_url
from build_expanded_source_albums import build

def main():
    assert len(TARGETS)==4 and MAX_FREE_IMAGES==5
    assert public_photo_url("https://cdn.v2ph.com/photos/aBCde123.jpg",TARGETS[0]["source"])
    for url in ("https://localhost/private.jpg","file:///etc/passwd","https://example.com/track.gif"):
        assert not public_photo_url(url,TARGETS[0]["source"])
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        album=root/"thru-thru-public-preview"
        album.mkdir()
        photo=album/"001.jpg"
        Image.new("RGB",(800,1200),(33,44,55)).save(photo,"JPEG")
        blob=photo.read_bytes()
        row={"number":1,"url":"https://cdn.v2ph.com/photos/verified001.jpg",
             "file":"001.jpg","sha256":hashlib.sha256(blob).hexdigest(),
             "width":800,"height":1200,"bytes":len(blob)}
        (album/"manifest.json").write_text(json.dumps({
            "id":"thru-thru-public-preview","title":"Thru Thru",
            "source_page":TARGETS[0]["source"],"declared_full_album":117,
            "images":[row],"stored":1}))
        out=root/"gallery.json"
        result=build(root,out)
        assert len(result["albums"])==1
        assert len(result["albums"][0]["images"])==1
        assert result["albums"][0]["full_album_complete"] is False
        assert not list(root.rglob("*.zip"))
        photo.write_bytes(b"corrupted")
        try:
            build(root,out)
        except ValueError: pass
        else: raise AssertionError("Tampered image accepted")
    print("FREE_V2PH_SOURCE_PREVIEW_AND_SHA256_QA_PASS")

if __name__=="__main__":
    main()
