import json
from pathlib import Path
import tempfile
import unittest
from work_coverage import build,canonical,ranges,title_key


class CoverageTests(unittest.TestCase):
    def test_alias_cycle_rejected_and_ranges(self):
        with self.assertRaises(ValueError):canonical('a',{'a':'b','b':'a'})
        self.assertEqual(ranges([1,2,5,6,7]),[[1,2],[5,7]])
        self.assertEqual(title_key('[DJAWA] Mimmi - Rudy² - Page 2'),title_key('Mimmi Rudy2'))

    def test_totals_unknown_numbering_conflicts_and_duplicate_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            photos=[{'number':n,'sha256':str(n)*64,'bytes':10000} for n in (1,2,3)]
            owner={'schema_version':1,'model':'mimmi','albums':[{'id':'work-aa','title':'Work','images':photos+[{**photos[0],'number':4}]}]}
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            (base/'source-viewer-albums.json').write_text(json.dumps({'albums':[{'id':'work-aa','title':'Work','expected':8,'source':'https://example.org/work','images':photos}]}))
            result=build(root,'mimmi',owner)
            self.assertEqual(result['owner_rows'],4);self.assertEqual(result['owner_unique_sha256'],3)
            work=result['albums'][0];self.assertEqual(work['missing_photo_numbers'],[5,6,7,8])
            self.assertEqual(work['gallery_displayed_rows'],None)
            (base/'source-viewer-albums.json').write_text(json.dumps({'albums':[{'id':'work-aa','source':'https://example.org/older-edition','images':photos}]}))
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{'id':'work-aa','source':'https://example.org/new-edition','advertised_photos':8}]}))
            work=build(root,'mimmi',owner)['albums'][0]
            self.assertIsNone(work['missing_photo_numbers'],'Anchors from a different edition cannot prove the new source numbering')
            (base/'official-previews.json').write_text(json.dumps({'albums':[{'id':'work-aa','title':'Work','source':'https://djawaphoto.com/portfolio/work/','advertised_photos':100,'samples':[]}]}))
            work=build(root,'mimmi',owner)['albums'][0]
            self.assertEqual(work['known_total'],100)
            self.assertIsNone(work['missing_photo_numbers'],'Publisher count alone cannot identify original file numbers')
            (base/'official-previews.json').write_text(json.dumps({'albums':[{'id':'work-aa','source':'https://djawaphoto.com/portfolio/work/','advertised_photos':100},{'id':'work-aa','source':'https://djawaphoto.com/portfolio/other-edition/','advertised_photos':120}]}))
            work=build(root,'mimmi',owner)['albums'][0]
            self.assertTrue(work['conflicting_totals']);self.assertIsNone(work['known_total'])


if __name__=='__main__':unittest.main(verbosity=2)
