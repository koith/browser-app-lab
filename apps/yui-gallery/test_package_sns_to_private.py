#!/usr/bin/env python3
"""Ensure SNS photos become real private ZIP bytes, not just a success report."""
import hashlib
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from PIL import Image
from package_sns_to_private import pack

def jpeg(rgb):
    i=Image.new("RGB",(640,800),rgb);b=io.BytesIO();i.save(b,format="JPEG",quality=90);return b.getvalue()

def main():
    with TemporaryDirectory() as d:
        root=Path(d);source=root/"source";(source/"images").mkdir(parents=True)
        old=jpeg((38,48,85));new=jpeg((65,150,99))
        def row(raw,post):
            sha=hashlib.sha256(raw).hexdigest()
            name=f"images/{sha}.jpg";(source/name).write_bytes(raw)
            return {"author":"super_yuisan","url":"https://pbs.twimg.com/media/test.jpg?name=orig",
                    "sha256":sha,"bytes":len(raw),"width":640,"height":800,
                    "file":name,"post":post}
        known=row(old,"https://x.com/super_yuisan/status/1")
        fresh=row(new,"https://x.com/super_yuisan/status/2")
        (source/"manifest.json").write_text(json.dumps({
            "kind":"public_social_attachments","images":[known,fresh]}))
        previous=root/"previous.json"
        previous.write_text(json.dumps({"model":"yui","schema_version":1,
            "albums":[{"id":"public-yui-sns","images":[{"number":361,"sha256":known["sha256"]}]}]}))
        out=root/"out";report=pack(source,previous,out)
        assert report["actually_new_sha256_physical_pictures"]==1,report
        path=out/"yui-sns-new-private-import.zip"
        with ZipFile(path) as zip:
            manifest=json.loads(zip.read("manifest.json"))
            assert manifest["model"]=="yui"
            entry=manifest["albums"][0]["images"][0]
            assert entry["number"]==362,entry
            assert zip.read(entry["url"])==new
        # Re-scan exact already-saved image: never generate a false new photo.
        previous.write_text(json.dumps({"model":"yui","schema_version":1,
            "albums":[{"id":"public-yui-sns","images":[
              {"number":361,"sha256":known["sha256"]},
              {"number":362,"sha256":fresh["sha256"]}]}]}))
        (source/"manifest.json").write_text(json.dumps({
            "kind":"public_social_attachments","images":[known,fresh]}))
        empty=root/"empty";empty.mkdir()
        delta=pack(source,previous,empty)
        assert delta["actually_new_sha256_physical_pictures"]==0
        assert not list(empty.glob("*-private-import.zip"))
        print("YUI_PUBLIC_SNS_ACTUAL_PRIVATE_ARCHIVE_BYTES_NUMBERED_DELTA_AND_NO_REIMPORT_PASS")

if __name__=="__main__":main()
