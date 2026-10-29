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

    def test_published_fallback_sha_matches_but_restricted_origin_not_retried(self):
        from io import BytesIO
        from PIL import Image
        from collect_private_batch import verify_one
        import hashlib
        image=Image.new("RGB",(480,640),(120,80,30))
        buff=BytesIO();image.save(buff,format="JPEG",quality=90)
        raw=buff.getvalue()
        sha=hashlib.sha256(raw).hexdigest()
        calls=[]
        class Response:
            status_code=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def iter_content(self,chunk_size):yield raw
        def fake_request(url,**kwargs):
            calls.append(url)
            return Response()
        item={"number":2,"url":"https://cdn.jliji.com/not-retry.jpg",
              "alternate_source_urls":["https://img-jp-a.cdnimg.vip/korea/public.jpg"],
              "sha256":sha,"bytes":len(raw),"width":480,"height":640}
        with patch("collect_private_batch.requests.get",side_effect=fake_request):
            verified,error=verify_one(item,"https://www.xiutu.me/public-album")
        self.assertIsNone(error)
        self.assertEqual(verified[0]["sha256"],sha)
        self.assertEqual(calls,["https://img-jp-a.cdnimg.vip/korea/public.jpg"])

    def test_public_alternate_never_accepted_if_sha_differs(self):
        from io import BytesIO
        from PIL import Image
        from collect_private_batch import verify_one
        import hashlib
        im=Image.new("RGB",(480,640));b=BytesIO();im.save(b,format="JPEG")
        raw=b.getvalue()
        class Response:
            status_code=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def iter_content(self,chunk_size):yield raw
        item={"number":1,"url":"https://cdn.jliji.com/not-retry.jpg",
              "alternate_source_urls":["https://img-jp-a.cdnimg.vip/korea/wrong.jpg"],
              "sha256":"a"*64,"bytes":len(raw),"width":480,"height":640}
        with patch("collect_private_batch.requests.get",return_value=Response()):
            verified,error=verify_one(item,"https://www.xiutu.me/public-album")
        self.assertIsNone(verified)
        self.assertEqual(error["reason"],"sha256_or_byte_length_mismatch")

if __name__=="__main__":
    unittest.main()
