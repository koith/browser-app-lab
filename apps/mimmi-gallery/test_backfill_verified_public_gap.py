#!/usr/bin/env python3
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from backfill_verified_public_gap import candidates, known_saved_hashes

def album(aid, hash_char, source="https://cosplay.pixibb.com/djawa-photo-mimmi-any/"):
    return {"id":aid,"source":source,"title":"Mimmi sample set","advertised_photos":2,
            "images":[],"samples":[{"url":"https://images01.pixibb.com/test/photo.jpg",
                "number":1,"sha256":hash_char*64,"bytes":10000,"width":1200,"height":800}]}

def owner(albums=None):
    return {"schema_version":1,"model":"mimmi",
            "storage":"owner-private-terabox-sha-verified-bytes",
            "albums":albums or []}

class TestFullPhotoBackfill(unittest.TestCase):
    def test_skip_only_real_sha_saved_and_keep_full_unarchived_series(self):
        a=album("pixibb-example-photos","a")
        b=album("pixibb-new-photos","b")
        document={"model":"mimmi","summary":{"private_cloud_archived":0},"albums":[a,b]}
        public={"model":"mimmi","albums":[{"id":"other","images":[{"sha256":"a"*64}]}]}
        self.assertEqual(len(known_saved_hashes(public,owner())),1)
        batch,report=candidates(document,{"a"*64},0,1)
        self.assertEqual(report["new_sha_unique_before_download"],1)
        self.assertEqual(batch[0]["id"],"pixibb-new-photos")
        self.assertEqual(batch[0]["images"][0]["number"],1)
        self.assertEqual(report["new_original_files_saved"],0)

    def test_owner_private_photos_are_not_downloaded_again(self):
        private=[{"id":"album-private","images":[{"number":1,"sha256":"b"*64,
                   "bytes":10000,"key":"originals/album-private/00001-b.jpg"}]}]
        recorded=known_saved_hashes({"model":"mimmi","albums":[]},owner(private))
        result,report=candidates({"model":"mimmi","summary":{"private_cloud_archived":0},
                   "albums":[album("pixibb-rudy-codename","b")]},recorded,0,1)
        self.assertEqual(result,[])
        self.assertEqual(report["new_sha_unique_before_download"],0)

    def test_alternate_reencoded_full_set_is_not_fake_missing(self):
        alt=album("pixibb-auto-creamsoda-mimmi-vol-2-neko-mimmi-62-photos-cosplay","c")
        data={"model":"mimmi","summary":{"private_cloud_archived":0},"albums":[alt]}
        rows,report=candidates(data,set(),0,1)
        self.assertEqual(rows,[])
        self.assertEqual(len(report["excluded_alternate_editions"]),1)

    def test_full_real_public_manifest_detects_physically_unsaved_series(self):
        public=json.loads((ROOT/"stored-albums.json").read_text())
        all_sources=json.loads((ROOT/"pixibb-public-previews.json").read_text())
        saved=known_saved_hashes(public,owner())
        work,report=candidates(all_sources,saved,0,1)
        self.assertGreaterEqual(report["new_sha_unique_before_download"],300)
        self.assertTrue(any(x["id"]=="pixibb-rudy-codename" and len(x["images"])>=180 for x in work))
        self.assertTrue(any("christmas-special-2022" in x["id"] and len(x["images"])>=80 for x in work))
        self.assertTrue(any("tashkent" in x["id"] and len(x["images"])>=55 for x in work))
        for a in work:
            self.assertEqual(len({p["number"] for p in a["images"]}),len(a["images"]))

    def test_bad_owner_record_causes_fail_closed(self):
        invalid=owner([{"id":"album-private","images":[{"number":1,
              "sha256":"b"*64,"bytes":10000,"key":"remote_url_only/no_photo.jpg"}]}])
        with self.assertRaises(ValueError):
            known_saved_hashes({"model":"mimmi","albums":[]},invalid)

if __name__=="__main__":
    unittest.main(verbosity=2)
