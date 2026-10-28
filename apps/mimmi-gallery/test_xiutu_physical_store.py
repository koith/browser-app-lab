#!/usr/bin/env python3
"""Free real-file archiving: six public CreamSoda sets are no mere 10-photo teasers."""
import hashlib
import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import publish_stored_public as publisher

HOST="https://img-jp-a.cdnimg.vip"
SITE="https://www.xiutu.me/photo/"
LINKS=publisher.XIUTU_EDITION_LINKS

def jpeg():
    im=Image.new("RGB",(1100,860),(240,180,160))
    draw=ImageDraw.Draw(im)
    for k in range(350):
        draw.line((k*19%1100,0,k*13%1100,860),
                  fill=(k*17%256,k*19%256,k*23%256),width=2)
    buf=BytesIO();im.save(buf,format="JPEG",quality=93)
    data=buf.getvalue()
    assert len(data)>5000
    return data

def photo(blob,number):
    return {"url":f"{HOST}/public/{number:03}.jpg",
        "sha256":hashlib.sha256(blob).hexdigest(),
        "bytes":len(blob),"width":1100,"height":860,"number":number}

def main():
    assert LINKS["xiutu-public-1190160"]=="v2ph-actor-a5e78m5a"
    assert LINKS["xiutu-public-1190158"]=="v2ph-actor-a8847m5a"
    assert LINKS["xiutu-public-1190156"]=="v2ph-actor-a884435a"
    assert LINKS["xiutu-public-1190145"]=="v2ph-actor-ae57484a"
    blob=jpeg();other=blob+b"x"
    # Images must be valid JPEG bytes: use an independently generated JPEG.
    im=Image.new("RGB",(1100,860),(135,190,220))
    buf=BytesIO();im.save(buf,format="JPEG",quality=97)
    alternative=buf.getvalue()
    # A model identity scan that found two real images from different editions.
    records=[
      {"id":"xiutu-public-1190160","title":"CreamSoda Neko Mimmi (62P)",
       "source":SITE+"1190160","samples":[photo(blob,1)],"images":[]},
      {"id":"xiutu-public-1190154","title":"CreamSoda Mash Mimmi 2 (72P)",
       "source":SITE+"1190154","samples":[photo(alternative,2)],"images":[]},
      {"id":"xiutu-public-invalid","title":"bad","source":"https://evil.test/p",
       "samples":[photo(blob,3)],"images":[]},
    ]
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        (root/"xiutu-public-previews.json").write_text(json.dumps({"model":"mimmi","albums":records}))
        (root/"source-viewer-albums.json").write_text(json.dumps({"model":"mimmi","albums":[]}))
        previews=publisher.xiutu_verified_public_editions(root)
        assert [p["id"] for p in previews]==[
            "v2ph-actor-a5e78m5a","xiutu-public-1190154"],previews
        bytes_by_hash={hashlib.sha256(blob).hexdigest():blob,
                       hashlib.sha256(alternative).hexdigest():alternative}
        def stub(meta,downloader=None):
            actual=bytes_by_hash[meta["sha256"]]
            assert len(actual)==meta["bytes"],meta
            return actual,meta["url"]
        with patch.object(publisher,"ROOT",root),patch.object(publisher,"MANIFEST",root/"source-viewer-albums.json"),patch.object(publisher,"INDEX",root/"stored-albums.json"),patch.object(publisher,"OUT",root/"stored-albums"),patch.object(publisher,"fetch_from_verified_alternates",side_effect=stub),patch.object(publisher.time,"sleep"):
            n=publisher.publish(limit=10,budget_mb=5,allow_rehost=True)
            assert n==2,n
            d=json.loads((root/"stored-albums.json").read_text())
            assert d["physical_verified_image_count"]==2
            assert len(d["albums"])==2
            assert set(x["id"] for x in d["albums"])=={
                "v2ph-actor-a5e78m5a","xiutu-public-1190154"}
            for a in d["albums"]:
                for p in a["images"]:
                    target=root/p["url"]
                    assert target.is_file() and target.stat().st_size==p["bytes"]
                    assert hashlib.sha256(target.read_bytes()).hexdigest()==p["sha256"]
                    assert p["url"].startswith("stored-albums/"+a["id"]+"/")
            again=publisher.publish(limit=10,budget_mb=5,allow_rehost=True)
            assert again==2,"Idempotence violated, duplicated physical photo rows"
        print("MIMMI_XIUTU_PHYSICAL_FILES_TWO_EDITIONS_SHA_IDEMPOTENT_PASS")

if __name__=="__main__":main()
