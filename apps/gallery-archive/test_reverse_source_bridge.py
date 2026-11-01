import json
from pathlib import Path
import tempfile
import unittest
from reverse_source_bridge import collect_evidence


class ReverseSourceBridgeTests(unittest.TestCase):
    def test_image_first_leads_are_public_pages_not_saved_photos(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            shard=root/'yui-shard'
            shard.mkdir()
            (shard/'reverse-full-yui-0.json').write_text(json.dumps({
              'summary':{'model':'yui','shard':0},
              'photo_seeds':[{'album_id':'known-work','album_title':'Yui Sim Spring',
                'candidates':[
                    {'url':'https://public-gallery.example.org/spring/source','identity_hint':True},
                    {'url':'https://public-gallery.example.org/other','identity_hint':False}
                ]}],
              'title_leads':[{'id':'new-yui-work','title':'Yui Sim Summer',
                'candidate_pages':[{'url':'https://public-gallery.example.org/summer'}]}]
            }))
            result=collect_evidence(root,'yui',{'known-work'})
            self.assertEqual(result['status'],
                             'unverified_reverse_source_pages_not_photo_files')
            self.assertEqual(result['counts']['unverified_unique_page_links'],2)
            by={x['id']:x for x in result['targets']}
            self.assertEqual(by['known-work']['urls'],
                ['https://public-gallery.example.org/spring/source'])
            self.assertFalse(by['new-yui-work']['owner_registered'])
            self.assertEqual(collect_evidence(root,'mimmi',{'known-work'})['targets'],[])


if __name__=='__main__':
    unittest.main()
