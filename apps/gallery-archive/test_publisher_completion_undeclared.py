#!/usr/bin/env python3
"""An unpublished publisher package size is not a made-up failed measurement."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from publisher_completion import evaluate


class OfficialCompletionTests(unittest.TestCase):
    def test_undeclared_package_size_is_not_a_permanent_false_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            base=root/'apps'/'mimmi-gallery'
            path=base/'stored-albums'/'work'/'one.jpg'
            path.parent.mkdir(parents=True)
            raw=b'ordinary-verified-file-bytes'
            path.write_bytes(raw)
            row={'sha256':hashlib.sha256(raw).hexdigest(),
                 'url':'stored-albums/work/one.jpg','width':1200,
                 'height':800,'watermark_status':'verified_none'}
            (base/'stored-albums.json').write_text(json.dumps({
                'albums':[{'id':'work','images':[row]}]}))
            spec={'model':'mimmi','album_id':'work','publisher_page':'https://example.org/work',
                  'declared_photo_count':1,'declared_width':1200,
                  'declared_height':800,'declared_package_bytes':None}
            qa={'distinct_full_edition_cuts_verified':True,
                'all_cuts_browser_open_verified':True}
            result=evaluate(root,spec,qa)
            self.assertTrue(result['complete'],result)
            self.assertEqual(result['package_size_evidence_status'],'NOT_DECLARED_BY_PUBLISHER')
            specified={**spec,'declared_package_bytes':123456}
            missing=evaluate(root,specified,qa)
            self.assertFalse(missing['complete'])
            self.assertEqual(missing['package_size_evidence_status'],'MISSING_VERIFICATION')
            correct=evaluate(root,specified,{
                **qa,'verified_official_package_bytes':123456,
                'full_package_sha_readback_verified':True})
            self.assertTrue(correct['complete'],correct)


if __name__=='__main__':
    unittest.main()
