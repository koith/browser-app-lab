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
                for forbidden in ('id="vault-file"','PhotoVault.importZip','vaultInput.onchange'):
                    self.assertNotIn(forbidden,html)
                local_reader=(ROOT/f"{model}-gallery/photo-vault.js").read_text(encoding="utf-8")
                for forbidden in ('importZip','zipEntries','DecompressionStream'):
                    self.assertNotIn(forbidden,local_reader)
                self.assertIn(f"{client}.albums()",html)
                self.assertIn(f"{client}.asset(",html)
                self.assertIn(f"PhotoVault.albums('{model}')",html)
                # The saved-photo SHA union replaces the legacy number-keyed
                # merge. Keep this guard aligned with the actual rendering path,
                # while the corpus test independently verifies every saved SHA.
                self.assertIn('src="saved-photo-union.js"', html)
                self.assertTrue(
                    "stored=SavedGalleryPhotoUnion.join([localStored,ownerStored,vaultStored])" in html
                    or ("const merged=SavedGalleryPhotoUnion.join([localStored,ownerStored,vaultStored])" in html
                        and "stored=joined.albums" in html),
                    "Gallery must render only the SHA-verified saved-photo union")
                self.assertIn("const archivedCount=stored.reduce(",html)
                # Archive-only: a discovered link cannot create a gallery photo.
                self.assertIn("localStored=",html)
                self.assertIn("ownerStored=",html)
                self.assertIn("vaultStored=",html)
                self.assertIn("remoteStored=[]",html)

if __name__=="__main__":
    unittest.main()
