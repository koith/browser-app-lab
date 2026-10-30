#!/usr/bin/env python3
import json
import unittest
from publish_owner_index import clean_catalog

def record(model="mimmi"):
    return {"schema_version":1,"model":model,
      "storage":"owner-private-terabox-sha-verified-bytes",
      "albums":[{"id":"full-album","title":"Original full album","expected":91,
                 "source":"https://secret.example/photos","private_session":"must-never-leak",
                 "images":[{"number":i,"sha256":f"{i:064x}","bytes":28000,
                            "width":1800,"height":2700,
                            "preview":"previews/full-album/00001.webp",
                            "preview_sha256":f"{(i+500):064x}",
                            "key":f"originals/full-album/{i:04d}.jpg",
                            "source_url":"https://secret.example/file.jpg",
                            "token":"must-never-leak"} for i in range(1,92)]}]}

class TestOwnerStaticManifest(unittest.TestCase):
    def test_full_original_photo_count_without_exposing_secrets_or_bytes(self):
        input=record()
        result=clean_catalog(input,"mimmi")
        self.assertEqual(result["physical_originals_indexed"],91)
        self.assertEqual(result["albums"][0]["expected"],91)
        self.assertEqual(len(result["albums"][0]["images"]),91)
        text=json.dumps(result)
        for term in ("secret.example","token","key","originals/","previews/","session"):
            self.assertNotIn(term,text)
        self.assertEqual(input["albums"][0]["images"][0]["number"],1)

    def test_yui_model_is_separate_and_checked(self):
        self.assertEqual(clean_catalog(record("yui"),"yui")["model"],"yui")
        with self.assertRaises(ValueError):
            clean_catalog(record("yui"),"mimmi")

    def test_source_links_without_bytes_do_not_count_as_saved_original(self):
        invalid=record()
        invalid["albums"][0]["images"][0]["key"]="https://public-source.example/photo.jpg"
        with self.assertRaises(ValueError):
            clean_catalog(invalid,"mimmi")

    def test_missing_preview_sha_fails_closed(self):
        invalid=record()
        del invalid["albums"][0]["images"][1]["preview_sha256"]
        with self.assertRaises(ValueError):
            clean_catalog(invalid,"mimmi")

if __name__=="__main__":
    unittest.main(verbosity=2)
