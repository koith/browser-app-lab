#!/usr/bin/env python3
"""Static guard: archive management belongs to backend, not Yui/Mimmi viewer.

This does not claim live private cloud authentication; authenticated image
readback is separately tested by qa_real_gallery_browser.py.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ViewerOnlyTest(unittest.TestCase):
    def test_two_galleries_show_photos_not_file_import_setup(self):
        for model,client in (("yui","YuiPrivate"),("mimmi","MimmiPrivate")):
            with self.subTest(model=model):
                html=(ROOT/f"{model}-gallery/index.html").read_text(encoding="utf-8")
                for unwanted in (
                    "내 ZIP 여러 개 가져오기", "내 Drive 원본 연결",
                    'id="vault-import"', '<button id="vault-import"',
                    'href="drive-sync.html"',
                    'href="cloud.html"', ".vault-actions",
                ):
                    self.assertNotIn(unwanted,html)
                self.assertIn('multiple hidden><span id="vault-status" hidden',html)
                self.assertIn(f"{client}.albums()",html)
                self.assertIn(f"{client}.asset(",html)
                self.assertIn(f"PhotoVault.albums('{model}')",html)
                self.assertTrue("stored=[...combined.values()]" in html or "stored=joined.albums" in html,
                                "Gallery must use only saved, verified album rows")
                self.assertIn("const archivedCount=stored.reduce(",html)
                # Archive-only: a discovered link cannot create a gallery photo.
                self.assertIn("localStored=",html)
                self.assertIn("ownerStored=",html)
                self.assertIn("vaultStored=",html)
                self.assertIn("remoteStored=[]",html)

if __name__=="__main__":
    unittest.main()
