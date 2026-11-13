#!/usr/bin/env python3
"""Regression: published real bytes preserve observed source photo slot evidence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from publish_new_public_photos_to_pages import publish


class PublishProvenanceTest(unittest.TestCase):
    def run_case(self, number, provenance=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gallery = root / "apps" / "mimmi-gallery"
            gallery.mkdir(parents=True)
            stage = root / "stage"
            source = stage / "originals" / "work" / "one.jpg"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (360, 480), (40, 90, 130)).save(source, format="JPEG")
            raw = source.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            (gallery / "owner-index.json").write_text(json.dumps(
                {"schema_version": 1, "model": "mimmi",
                 "albums": [{"id": "older", "images": [{"sha256": "a" * 64}]}]}))
            (gallery / "stored-albums.json").write_text(json.dumps({"albums": []}))
            (gallery / "public-work-pages.json").write_text(json.dumps(
                {"albums": [{"id": "work", "title": "Work", "source": "https://example.org/work"}]}))
            photo = {"number": 1, "key": "originals/work/one.jpg", "sha256": digest,
                     "bytes": len(raw), "width": 360, "height": 480,
                     "source_photo_number": number, "numbering_provenance": provenance}
            (stage / "metadata").mkdir()
            (stage / "metadata" / "catalog.json").write_text(json.dumps(
                {"model": "mimmi", "albums": [{"id": "work", "images": [photo]}]}))
            first = publish("mimmi", stage, root=root)
            self.assertEqual(first["new_sha_verified_originals"], 1)
            row = json.loads((gallery / "stored-albums.json").read_text())["albums"][0]["images"][0]
            self.assertEqual(row["sha256"], digest)
            self.assertEqual((gallery / row["url"]).read_bytes(), raw)
            self.assertEqual(row["number"], 1)
            second = publish("mimmi", stage, root=root)
            self.assertEqual(second["new_sha_verified_originals"], 0)
            self.assertEqual(len(json.loads((gallery / "stored-albums.json").read_text())["albums"][0]["images"]), 1)
            return row

    def test_real_observed_source_number_survives_publication(self):
        row = self.run_case(45, "published_source_order")
        self.assertEqual(row["source_photo_number"], 45)
        self.assertEqual(row["source_numbering"], "public_web_filename_not_publisher_original")
        self.assertEqual(row["numbering_provenance"], "published_source_order")

    def test_forged_or_unverified_source_numbers_are_not_promoted(self):
        row = self.run_case(True, "publisher_original_edition_number")
        self.assertNotIn("source_photo_number", row)
        self.assertNotIn("source_numbering", row)
        self.assertNotIn("numbering_provenance", row)


if __name__ == "__main__":
    unittest.main()
