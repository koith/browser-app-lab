"""Private Drive checkpoint and never-certify-incomplete-preview regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent/"yui-gallery"))
from missing_candidates import archived_positions, select_missing
from collect_private_batch import archive

A="a"*64

class CheckpointTests(unittest.TestCase):
    def test_real_readback_252_slots(self):
        p=json.loads((ROOT/"private-archive-checkpoint.json").read_text())
        positions=archived_positions(p)
        self.assertEqual((len(positions),len(p["albums"])),(252,23))
        self.assertIn(("djawa-rudy2-codename-wolfgirl-9b4e68",209),positions)
        self.assertIn(("djawa-retrospection",7),positions)

    def test_no_reharvest_of_private_209_or_public_occupied_slot(self):
        p=json.loads((ROOT/"private-archive-checkpoint.json").read_text())
        already=archived_positions(p)|{("album-a",1,A)}
        source={"model":"mimmi","source_link_only":True,"albums":[
            {"id":"djawa-rudy%c2%b2-codename-wolfgirl",
             "images":[{"number":n,"sha256":A} for n in range(1,210)]},
            {"id":"album-a","images":[{"number":1,"sha256":"b"*64},
                                       {"number":2,"sha256":A}]}]}
        selected,count=select_missing(source,already,0,1)
        self.assertEqual(count,1)
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]["id"],"album-a")
        self.assertEqual(selected[0]["images"][0]["number"],2)
        self.assertIsNone(selected[0]["expected"])

    def test_corrupt_checkpoint_rejected(self):
        p=json.loads((ROOT/"private-archive-checkpoint.json").read_text())
        for case in ["wrong_model","wrong_count","duplicate"]:
            altered=json.loads(json.dumps(p))
            if case=="wrong_model":altered["model"]="yui"
            elif case=="wrong_count":altered["position_count"]+=1
            else:altered["albums"]["djawa-retrospection"].append([7,7])
            with self.assertRaises(ValueError):archived_positions(altered)

    def test_unknown_total_never_marked_complete(self):
        import hashlib
        raw=b"x"*9000
        photo={"number":1,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
               "width":600,"height":900,"url":"photos/"+hashlib.sha256(raw).hexdigest()+".jpg"}
        with tempfile.TemporaryDirectory() as folder:
            with patch("collect_private_batch.verify_one",return_value=((photo,raw),None)):
                result=archive({"id":"public-preview","title":"Preview",
                                "images":[{"number":1,"sha256":A,"bytes":9000,
                                           "url":"https://cdn.v2ph.com/preview.jpg"}]},
                               Path(folder),workers=1,model="mimmi")
            from zipfile import ZipFile
            with ZipFile(Path(folder)/"public-preview-private-import.zip") as z:
                manifest=json.loads(z.read("manifest.json"))
            self.assertIsNone(result["expected"])
            self.assertFalse(result["complete"])
            self.assertIsNone(manifest["albums"][0]["expected"])
            self.assertEqual(manifest["albums"][0]["status"],"partial_downloaded")

    def test_only_known_complete_edition_may_be_complete(self):
        import hashlib
        raw=b"z"*9000
        photo={"number":1,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
               "width":600,"height":900,"url":"photos/"+hashlib.sha256(raw).hexdigest()+".jpg"}
        with tempfile.TemporaryDirectory() as folder:
            with patch("collect_private_batch.verify_one",return_value=((photo,raw),None)):
                partial=archive({"id":"partial","images":[{"number":1,"sha256":A}],
                                 "expected":80},Path(folder),model="mimmi")
                complete=archive({"id":"one","images":[{"number":1,"sha256":A}],
                                  "expected":1},Path(folder),model="mimmi")
            self.assertFalse(partial["complete"])
            self.assertTrue(complete["complete"])

if __name__=="__main__":
    unittest.main()
