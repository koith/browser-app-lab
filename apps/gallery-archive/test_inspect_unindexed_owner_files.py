"""Offline security and file-selection tests for existing TeraBox orphan inspection."""
import unittest
from inspect_unindexed_owner_files import candidates

class UnindexedReadTests(unittest.TestCase):
    def setUp(self):
        self.catalog={"model":"mimmi","albums":[
            {"id":"existing-album","images":[
                {"key":"originals/existing-album/known.jpg","sha256":"a"*64}]}]}
        self.listing=[
            {"Path":"originals/existing-album/known.jpg","Size":1000},
            {"Path":"originals/existing-album/unindexed.jpg","Size":3000},
            {"Path":"originals/new-album/one.jpg","Size":5000},
            {"Path":"originals/new-album/two.jpg","Size":6000},
            {"Path":"previews/existing-album/preview.jpg","Size":5000},
            {"Path":"originals/existing-album/too-big.jpg","Size":20_000_000},
            {"Path":"originals/existing-album/../unsafe.jpg","Size":5000},
        ]

    def test_only_safe_unindexed_photo_paths(self):
        rows,total=candidates(self.listing,self.catalog,100)
        self.assertEqual(total,3)
        self.assertEqual(len(rows),3)
        self.assertEqual([r[3] for r in rows],[
            "new-album","new-album","existing-album"])
        self.assertEqual(rows[0][1],6000)

    def test_limit_is_applied_only_after_safe_filter(self):
        rows,total=candidates(self.listing,self.catalog,1)
        self.assertEqual(total,3)
        self.assertEqual(rows[0][3],"new-album")

    def test_empty_or_malformed_list_fails_closed(self):
        with self.assertRaises(ValueError):
            candidates({},self.catalog,2)
        with self.assertRaises(ValueError):
            candidates(self.listing,{},2)
        with self.assertRaises(ValueError):
            candidates(self.listing,self.catalog,0)

if __name__=="__main__":
    unittest.main()
