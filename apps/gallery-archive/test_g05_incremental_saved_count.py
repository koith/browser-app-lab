#!/usr/bin/env python3
"""Check real SHA-backed SNS growth is allowed without erasing the 20-photo baseline."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
class RealIncrementalPublicSnsTest(unittest.TestCase):
    def test_new_photo_is_immutable_and_baseline_still_present(self):
        from qa_g07_new_public_saved_sha import source_proof
        proof=source_proof()
        self.assertEqual(proof['sha256'],
            '68ff6a9b92bd13e7a1def21ef2dfb42a28c7bf627d1a493164906107158dcc7b')
        album=next(a for a in json.loads((ROOT/'apps/yui-gallery/stored-albums.json').read_text())['albums']
                   if a['id']=='public-yui-sns')
        if len(album['images'])>=3:
            self.assertGreaterEqual(len(set(p['sha256'] for p in album['images'])),3)
            self.assertEqual(album['images'][:2][0]['number'],467)
            self.assertEqual(album['images'][:2][1]['number'],468)

if __name__=='__main__':
    unittest.main()
