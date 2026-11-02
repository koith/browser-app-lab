#!/usr/bin/env python3
"""Regression tests: mirrored work IDs do not fabricate missing photo numbers."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from audit_both_models import rows


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AliasAwareCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "apps" / "mimmi-gallery"
        (self.base / "stored-albums").mkdir(parents=True)
        original = b"authentic photo bytes"
        (self.base / "stored-albums" / "one.jpg").write_bytes(original)
        self.digest = sha(original)
        self.other = sha(b"distinct missing photo")
        self.save("stored-albums.json", {
            "model": "mimmi", "physical_verified_image_count": 1,
            "albums": [{"id": "djawa-main", "images": [{
                "number": 1, "sha256": self.digest, "bytes": len(original),
                "url": "stored-albums/one.jpg"}]}]})
        self.save("source-viewer-albums.json", {"albums": [
            {"id": "pixibb-mirror", "images": [
                {"number": 99, "sha256": self.digest, "bytes": 10}]},
            {"id": "alias-source", "images": [
                {"number": 101, "sha256": self.digest, "bytes": 10}]},
            {"id": "djawa-main", "expected": 2, "images": [
                {"number": 1, "sha256": self.digest, "bytes": 10},
                {"number": 2, "sha256": self.other, "bytes": 20}]}
        ]})
        self.save("album-aliases.json", {
            "schema_version": 1, "aliases": {"alias-source": "djawa-main"}})

    def save(self, name, value):
        (self.base / name).write_text(json.dumps(value), encoding="utf-8")

    def test_mirrored_ids_not_fabricated_as_missing_numbers(self):
        r = rows(self.root, "mimmi")
        self.assertEqual(r["source_numbered_positions_not_stored"], 1)
        self.assertEqual(r["unlinked_research_work_positions_not_claimed_missing"], 1)
        self.assertEqual(r["reviewed_alias_source_positions_not_number_comparable"], 1)
        self.assertEqual(r["research_distinct_sha_not_in_saved_catalog"], 1)
        by_id = {a["id"]: a for a in r["albums_needing_review"]}
        self.assertEqual(by_id["pixibb-mirror"]["relationship"], "unlinked_research_work")
        self.assertEqual(by_id["pixibb-mirror"]["source_shas_already_stored_elsewhere"], 1)
        self.assertIsNone(by_id["pixibb-mirror"]["source_numbered_positions_not_stored"])
        self.assertEqual(by_id["alias-source"]["relationship"], "reviewed_alias_different_numbering")
        self.assertIsNone(by_id["alias-source"]["missing_numbered_positions"])
        self.assertEqual(by_id["djawa-main"]["source_numbered_positions_not_stored"], 1)
        self.assertEqual(by_id["djawa-main"]["missing_numbered_positions"], 1)

    def test_alias_cycle_rejected(self):
        self.save("album-aliases.json", {
            "schema_version": 1,
            "aliases": {"alias-source": "djawa-main", "djawa-main": "alias-source"}})
        with self.assertRaisesRegex(ValueError, "Cyclic album aliases"):
            rows(self.root, "mimmi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
