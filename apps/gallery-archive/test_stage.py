#!/usr/bin/env python3
"""Make sure TeraBox staging really writes SHA-verified image bytes, not URLs."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_STORED
from PIL import Image
from terabox_stage import prepare

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);inp=root/"input";inp.mkdir()
        img=Image.new("RGB",(620,930),(110,70,130))
        payload=io.BytesIO();img.save(payload,format="JPEG",quality=85)
        raw=payload.getvalue();digest=hashlib.sha256(raw).hexdigest()
        entry={"number":1,"url":f"photos/{digest}.jpg","sha256":digest,"bytes":len(raw),
               "width":620,"height":930}
        manifest={"model":"yui","physical_verified_image_count":2,
                  "albums":[{"id":"test-album","title":"Test photo",
                             "images":[entry,{**entry,"number":2}]}]}
        nest=io.BytesIO()
        with ZipFile(nest,"w",ZIP_STORED) as z:
            z.writestr("manifest.json",json.dumps(manifest))
            z.writestr(entry["url"],raw)
        with ZipFile(inp/"test-wrapper.zip","w") as z:
            z.writestr("test-album-private-import.zip",nest.getvalue())
        # The actual Actions artifact download unpacks the wrapper in-place.
        with ZipFile(inp/"test-wrapper.zip") as z:
            z.extractall(inp)
        report=prepare("yui",root/"stage",inp,False)
        assert report["physical_positions"]==2,report
        assert report["media_files"]==4
        catalog=json.loads((root/"stage/metadata/catalog.json").read_text())
        p=catalog["albums"][0]["images"]
        assert len(p)==2 and [i["number"] for i in p]==[1,2]
        for photo in p:
            image=(root/"stage"/photo["key"]).read_bytes()
            thumbnail=(root/"stage"/photo["preview"]).read_bytes()
            assert hashlib.sha256(image).hexdigest()==digest
            assert hashlib.sha256(thumbnail).hexdigest()==photo["preview_sha256"]
        assert catalog["albums"][0]["complete"] is False
        assert catalog["summary"]["physical_photo_positions"]==2
        # Malicious or corrupted archive cannot be counted as saved photos.
        bad=dict(entry);bad["sha256"]="0"*64
        badmanifest={**manifest,"physical_verified_image_count":1,
                     "albums":[{"id":"test-album","images":[bad]}]}
        broken=root/"broken";broken.mkdir()
        with ZipFile(broken/"test-album-private-import.zip","w") as z:
            z.writestr("manifest.json",json.dumps(badmanifest))
            z.writestr(bad["url"],raw)
        try:prepare("yui",root/"bad-stage",broken,False)
        except ValueError:pass
        else:raise AssertionError("A wrong image SHA was accepted")
        print("TERABOX_STAGE_SHA_IMAGE_AND_DUPLICATE_NUMBER_QA_PASS")

if __name__=="__main__":
    main()
