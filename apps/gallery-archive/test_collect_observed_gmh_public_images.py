#!/usr/bin/env python3
"""Offline regression: provenance, no URL guesses, real decoded bytes, dedupe."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from collect_observed_gmh_public_images import collect, verified_item

SLUG="djawa-mimmi-mimmi-your-panties-a"
PAGE="https://g-mh.com/gallery/"+SLUG+"/"
PHOTO="https://img.g-mh.com/"+SLUG+"/g-mhcom_001.webp"
ITEM={"model":"mimmi","work_id":"djawa-your-panties","edition_identity":"Your Panties A",
      "observed_heading":"DJAWA Mimmi 밈미 – Your Panties A",
      "source_page":PAGE,"media_urls":[PHOTO]}
REG={"djawa-your-panties":{"id":"djawa-your-panties","title":"Your Panties","source":PAGE}}

def jpeg_bytes():
    # Real, large enough decoded photo file; deterministic pixels.
    x=Image.effect_noise((900,1200),65).convert("RGB")
    buf=BytesIO();x.save(buf,format="JPEG",quality=87)
    return buf.getvalue()

class FakePublicHTTP:
    def __init__(self,payload):self.payload=payload;self.urls=[]
    def fetch(self,url,*,kind,max_bytes):
        self.urls.append((url,kind))
        assert kind=="image" and url==PHOTO, "must never fetch page/guess URLs"
        return self.payload

class Tests(unittest.TestCase):
    def test_verified_exact_work_and_cdn(self):
        self.assertEqual(verified_item(ITEM,"mimmi",REG),(True,"exact_observed_album_and_cdn"))
    def test_cannot_mix_other_models_even_if_filename_looks_similar(self):
        bad={**ITEM,"observed_heading":"DJAWA Yui – Your Panties A"}
        self.assertEqual(verified_item(bad,"mimmi",REG)[1],"wrong_model")
    def test_public_page2_provenance_preserves_exact_model_and_slug(self):
        page2={**ITEM,"source_page":PAGE+"page/2/","media_urls":[
            "https://img.g-mh.com/"+SLUG+"/g-mhcom_011.webp"]}
        self.assertEqual(verified_item(page2,"mimmi",REG),(True,"exact_observed_album_and_cdn"))
        bad={**page2,"source_page":PAGE+"page/0/"}
        self.assertEqual(verified_item(bad,"mimmi",REG)[1],"unreviewed_source_path")
        bad={**page2,"source_page":PAGE+"page/2/?preview=1"}
        self.assertEqual(verified_item(bad,"mimmi",REG)[1],"unreviewed_source_path")
        bad={**page2,"media_urls":[
            "https://img.g-mh.com/other-book/g-mhcom_011.webp"]}
        self.assertEqual(verified_item(bad,"mimmi",REG)[1],"cdn_media_not_observed_for_exact_work")

    def test_wrong_album_cdn_not_imported(self):
        bad={**ITEM,"media_urls":[PHOTO.replace(SLUG,"another-album")]}
        self.assertEqual(verified_item(bad,"mimmi",REG)[1],"cdn_media_not_observed_for_exact_work")
    def test_source_site_not_downloaded_and_only_real_image_counted(self):
        with TemporaryDirectory() as d:
            root=Path(d);base=root/"apps/mimmi-gallery";base.mkdir(parents=True)
            (base/"public-work-pages.json").write_text(json.dumps({"albums":list(REG.values())}))
            (base/"owner-index.json").write_text(json.dumps({"albums":[]}))
            (base/"stored-albums.json").write_text(json.dumps({"albums":[]}))
            manifest=root/"observed.json"
            manifest.write_text(json.dumps({"schema_version":1,"cdn_domain":"img.g-mh.com","works":[ITEM]}))
            http=FakePublicHTTP(jpeg_bytes());stage=root/"stage"
            result=collect("mimmi",stage,root,manifest,http,max_photos=2,max_per_work=2)
            self.assertEqual(result["real_downloaded_files_staged"],1)
            self.assertEqual(http.urls,[(PHOTO,"image")])
            catalog=json.loads((stage/"metadata/catalog.json").read_text())
            self.assertEqual(catalog["albums"][0]["id"],"djawa-your-panties")
            photo=catalog["albums"][0]["images"][0]
            raw=(stage/photo["key"]).read_bytes()
            self.assertEqual(photo["sha256"],hashlib.sha256(raw).hexdigest())
            self.assertEqual(photo["source_photo_number"],1)
    def test_no_repeated_download_for_exact_saved_public_source_url(self):
        with TemporaryDirectory() as d:
            root=Path(d);base=root/"apps/mimmi-gallery";base.mkdir(parents=True)
            (base/"public-work-pages.json").write_text(json.dumps({"albums":list(REG.values())}))
            (base/"owner-index.json").write_text(json.dumps({"albums":[]}))
            (base/"stored-albums.json").write_text(json.dumps({"albums":[{
                "id":"djawa-your-panties","images":[{"source_url":PHOTO,
                    "sha256":"a"*64,"url":"stored-albums/djawa-your-panties/a.webp"}]}]}))
            manifest=root/"observed.json"
            manifest.write_text(json.dumps({"schema_version":1,"cdn_domain":"img.g-mh.com","works":[ITEM]}))
            http=FakePublicHTTP(jpeg_bytes())
            result=collect("mimmi",root/"stage",root,manifest,http)
            self.assertEqual(result["real_downloaded_files_staged"],0)
            self.assertEqual(result["reused_source_urls"],1)
            self.assertEqual(http.urls,[])
if __name__=="__main__":unittest.main(verbosity=2)
