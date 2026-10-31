"""Retired photo archive paths cannot restart from schedules or source events."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class IndividualOnlyTests(unittest.TestCase):
    def test_old_photo_bundle_jobs_are_manual_notices_only(self):
        files=json.loads((ROOT/'apps/gallery-archive/retired-photo-bundle-workflows.json').read_text())['workflows']
        self.assertGreaterEqual(len(files),19)
        for name in files:
            with self.subTest(workflow=name):
                text=(ROOT/'.github/workflows'/name).read_text()
                self.assertIn('on:\n  workflow_dispatch:\n',text)
                for forbidden in ('schedule:','workflow_run:','push:','pull_request:',
                                  'private-import.zip','ZipFile','upload-artifact','download-artifact',
                                  'collect_private_batch.py','terabox_stage.py'):
                    self.assertNotIn(forbidden,text)
                self.assertIn('Gallery Direct Individual Photo Collection and Verified Storage',text)

    def test_individual_storage_path_retains_readback_and_genuine_browser_checks(self):
        text=(ROOT/'.github/workflows/gallery-direct-individual-archive.yml').read_text()
        self.assertIn('verify_terabox.py',text)
        self.assertIn('gallery-newly-stored-photo-qa.yml',text)
        self.assertNotIn('private-import.zip',text)


if __name__=='__main__':unittest.main(verbosity=2)
