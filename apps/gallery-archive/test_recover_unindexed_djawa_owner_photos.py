"""Offline SHA/decoder and source gate for known-work existing-owner recovery."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from recover_unindexed_djawa_owner_photos import eligible,stage,ALLOWED_WORKS


def fake_bytes():
    b=io.BytesIO()
    Image.new("RGB",(900,1300),(17,42,93)).save(b,format="JPEG")
    return b.getvalue()


class ExistingDjawaOwnerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=self.root/"apps/mimmi-gallery"
        self.base.mkdir(parents=True)
        aid=ALLOWED_WORKS[0]
        self.key="originals/"+aid+"/candidate.jpg"
        self.raw=fake_bytes()
        self.catalog={"model":"mimmi","schema_version":1,
          "storage":"owner-private-terabox-sha-verified-bytes",
          "albums":[{"id":aid,"images":[{"key":"originals/"+aid+"/current.jpg",
                   "sha256":"a"*64}]}]}
        self.listing=[{"Path":self.key,"Size":len(self.raw)},
          {"Path":"originals/unknown-or-private-work/x.jpg","Size":len(self.raw)},
          {"Path":"previews/"+aid+"/thing.jpg","Size":len(self.raw)},
          {"Path":"originals/"+aid+"/../../escape.jpg","Size":len(self.raw)}]
        self._json("owner-index.json",{"model":"mimmi","albums":[
          {"id":aid,"images":[{"sha256":"a"*64}]}]})
        self._json("stored-albums.json",{"model":"mimmi","albums":[]})
        self._json("public-work-pages.json",{"albums":[
            {"id":aid,"title":"Retrospection"},
            {"id":ALLOWED_WORKS[1],"title":"Christmas Special 2021 : Mimmi"}]})

    def _json(self,name,doc):
        (self.base/name).write_text(json.dumps(doc))

    def _reader(self,remote,key,target,env):
        self.assertEqual(key,self.key)
        target.write_bytes(self.raw)
        return True,"read_verified"

    def test_safe_known_edition_only(self):
        selected,total=eligible(self.listing,self.catalog,set(),18)
        self.assertEqual(total,1)
        self.assertEqual(selected[0][0],self.key)

    def test_verified_unindexed_real_bytes_staged(self):
        target=self.root/"stage"
        report=stage(self.root,target,self.listing,self.catalog,reader=self._reader)
        self.assertEqual(report["valid_new_sha_staged"],1)
        item=json.loads((target/"metadata/catalog.json").read_text())["albums"][0]["images"][0]
        self.assertEqual(item["sha256"],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual((item["width"],item["height"]),(900,1300))
        self.assertEqual((target/self.key).read_bytes(),self.raw)

    def test_sha_already_indexed_does_not_stage(self):
        self._json("owner-index.json",{"model":"mimmi","albums":[
          {"id":ALLOWED_WORKS[0],"images":[{"sha256":hashlib.sha256(self.raw).hexdigest()}]}]})
        target=self.root/"stage2"
        report=stage(self.root,target,self.listing,self.catalog,reader=self._reader)
        self.assertEqual(report["valid_new_sha_staged"],0)
        self.assertEqual(report["sha_already_indexed"],1)
        self.assertEqual(json.loads((target/"metadata/catalog.json").read_text())["albums"],[])

    def test_refuse_wrong_owner_catalog(self):
        self.catalog["model"]="yui"
        with self.assertRaisesRegex(ValueError,"UNVERIFIED"):
            stage(self.root,self.root/"bad",self.listing,self.catalog,reader=self._reader)

if __name__=="__main__":
    unittest.main()
