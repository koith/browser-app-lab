import json
from pathlib import Path
import tempfile
import unittest
from work_coverage import build,canonical,ranges,title_key


class CoverageTests(unittest.TestCase):
    def test_official_samples_are_not_publisher_edition_or_missing_numbers(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            photos=[{'number':i,'sha256':str(i)*64} for i in (1,2,3)]
            owner={'model':'yui','albums':[{'id':'public-samples','images':photos}]}
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            record={'id':'public-samples','title':'Public work','expected':24,
                    'advertised_publisher_photos':190,'collection_kind':'official_public_samples',
                    'source_pages':['https://djawaphoto.com/portfolio/public-work/'],'images':photos}
            (base/'additional-source-albums.json').write_text(json.dumps({'albums':[record]}))
            result=build(root,'yui',owner,{'albums':[{'id':'public-samples','images_count':3}]})
            work=result['albums'][0]
            self.assertEqual(work['publisher_claimed_totals'],[190])
            self.assertEqual(work['official_public_sample_counts'],[24])
            self.assertEqual(work['known_total'],190);self.assertFalse(work['conflicting_totals'])
            self.assertIsNone(work['missing_photo_numbers'])
            self.assertEqual(result['gallery_displayed_rows'],3)
            self.assertEqual(result['known_incomplete_stored_works_10_or_fewer'],1)

    def test_multiple_research_works_on_same_model_index_are_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            works=[{'title':title,'advertised_photos':100,
                    'sources':[{'url':'https://example.org/mimmi/'}]} for title in ('Work One','Work Two')]
            (base/'research-catalogue.json').write_text(json.dumps({'works':works}))
            result=build(root,'mimmi',{'model':'mimmi','albums':[]})
            self.assertEqual(len(result['albums']),2)
            self.assertEqual(len({a['id'] for a in result['albums']}),2)
            self.assertEqual(result['catalogue_records_without_stored_photos'],2)
            self.assertEqual(result['owner_rows'],0)
            self.assertTrue(all(a['sources']==['https://example.org/mimmi/'] for a in result['albums']))

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
            work=result['albums'][0];self.assertIsNone(work['missing_photo_numbers'],'Repeated SHA positions cannot prove file numbering')
            clean={'schema_version':1,'model':'mimmi','albums':[{'id':'work-aa','title':'Work','images':photos}]}
            self.assertEqual(build(root,'mimmi',clean)['albums'][0]['missing_photo_numbers'],[4,5,6,7,8])
            imported=json.loads(json.dumps(clean));imported['albums'][0]['images'][0]['source_numbering']='public_web_filename_not_publisher_original'
            self.assertIsNone(build(root,'mimmi',imported)['albums'][0]['missing_photo_numbers'],
                              'Appended alternate-source slots are not the former edition file numbers')
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
