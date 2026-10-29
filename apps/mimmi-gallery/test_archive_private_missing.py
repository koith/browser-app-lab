"""Mimmi private missing-photograph selection is SHA-based and no-network."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from archive_private_missing import select_missing,safe_id


class Tests(unittest.TestCase):
    def test_safe_album_ids(self):
        result=safe_id('djawa-rudy%c2%b2-codename-wolfgirl')
        self.assertTrue(result.startswith('djawa-rudy2-codename-wolfgirl'))
        self.assertNotIn('%',result)

    def test_missing_excludes_stored_and_cross_source_sha_duplicates(self):
        shas=['a'*64,'b'*64,'c'*64,'d'*64]
        photo=lambda sha,n:{"sha256":sha,"number":n,"bytes":11000,
                             "width":800,"height":1200,"url":"https://images08.pixibb.com/test.jpg"}
        source={"model":"mimmi","source_link_only":True,"albums":[
            {"id":"one","title":"One","images":[photo(shas[0],1),photo(shas[1],2)]},
            {"id":"two","title":"Two","images":[photo(shas[1],1),photo(shas[2],2)]},
            {"id":"three","title":"Three","images":[photo(shas[3],1)]}
        ]}
        first,total=select_missing(source,{shas[0]},0,2)
        second,other=select_missing(source,{shas[0]},1,2)
        self.assertEqual(total,3)
        self.assertEqual(other,3)
        self.assertEqual([a['id'] for a in first],['one','three'])
        self.assertEqual([a['id'] for a in second],['two'])
        chosen=[p["sha256"] for a in first+second for p in a["images"]]
        self.assertEqual(set(chosen),{shas[1],shas[2],shas[3]})
        self.assertEqual(len(chosen),3)


if __name__=="__main__":
    unittest.main(verbosity=2)
