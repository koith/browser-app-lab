"""Repackage previous real image bytes without duplicating public or Drive-backed slots."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZIP_STORED
from PIL import Image

sys.path.insert(0,str(Path(__file__).parent))
from package_recovered_physical import pack


def sample(color):
    im=Image.effect_noise((480,640),90)
    b=io.BytesIO()
    im.save(b,format="JPEG",quality=91)
    raw=b.getvalue()
    sha=hashlib.sha256(raw).hexdigest()
    return {"number":0,"sha256":sha,"bytes":len(raw),"width":480,"height":640,
            "url":"photos/"+sha+".jpg"},raw


def make_wrapper(path,album,photos):
    img,raw=sample(1)
    manifest={"model":"mimmi","physical_verified_image_count":len(photos),
              "albums":[{"id":album,"title":"Actual physical gallery",
                         "images":[{**img,"number":n} for n in photos]}]}
    b=io.BytesIO()
    with ZipFile(b,"w",ZIP_STORED) as z:
        z.writestr("manifest.json",json.dumps(manifest))
        z.writestr(img["url"],raw)
    with ZipFile(path,"w") as z:
        z.writestr(album+"-private-import.zip",b.getvalue())
    return img,raw


class Tests(unittest.TestCase):
    def test_only_unfilled_positions_survive_and_same_sha_can_recur(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)
            img,raw=make_wrapper(path/"prior.actions.zip","fixture",[1,2,3,4])
            public={"model":"mimmi","albums":[{"id":"fixture","images":[
                {"number":1,"sha256":img["sha256"]}]}]}
            checkpoint={"schema_version":1,"model":"mimmi","source":"verified-private-drive-wrapper-zip-readback",
                        "backed_up_zip_count":1,"position_count":1,"albums":{"fixture":[[2,2]]}}
            out=path/"new.actions.zip"
            result=pack([path/"prior.actions.zip"],public,checkpoint,out)
            self.assertEqual(result["new_verified_photo_positions"],2)
            self.assertEqual(result["existing_or_duplicate_rows"],2)
            with ZipFile(out) as wrapper:
                with ZipFile(io.BytesIO(wrapper.read("fixture-private-import.zip"))) as z:
                    manifest=json.loads(z.read("manifest.json"))
                    rows=manifest["albums"][0]["images"]
                    self.assertEqual([r["number"] for r in rows],[3,4])
                    self.assertIsNone(manifest["albums"][0]["expected"])
                    self.assertEqual(z.read(rows[0]["url"]),raw)

    def test_output_rejects_corrupt_source_sha(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)
            img,raw=make_wrapper(path/"prior.actions.zip","fixture",[1])
            # No real photo is supposed to have this mismatched SHA.
            with ZipFile(path/"prior.actions.zip") as wrapper:
                b=wrapper.read("fixture-private-import.zip")
            with ZipFile(io.BytesIO(b)) as inner:
                m=json.loads(inner.read("manifest.json"))
            m["albums"][0]["images"][0]["sha256"]="0"*64
            m["albums"][0]["images"][0]["url"]="photos/"+"0"*64+".jpg"
            modified=io.BytesIO()
            with ZipFile(modified,"w") as inner:
                inner.writestr("manifest.json",json.dumps(m))
                inner.writestr("photos/"+"0"*64+".jpg",raw)
            with ZipFile(path/"prior.actions.zip","w") as outer:
                outer.writestr("fixture-private-import.zip",modified.getvalue())
            checkpoint={"schema_version":1,"model":"mimmi","source":"verified-private-drive-wrapper-zip-readback",
                        "backed_up_zip_count":1,"position_count":1,"albums":{"other":[[1,1]]}}
            with self.assertRaisesRegex(ValueError,"corrupted"):
                pack([path/"prior.actions.zip"],{"model":"mimmi","albums":[]},checkpoint,path/"out.zip")

if __name__=="__main__":
    unittest.main()
