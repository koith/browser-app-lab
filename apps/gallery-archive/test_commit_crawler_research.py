#!/usr/bin/env python3
"""Regression coverage for non-destructive collector commits."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commit_crawler_research import merge_evidence


def album(aid, digest, source=None):
    return {"id": aid, "title": aid,
            "source": source or f"https://cosplay.pixibb.com/{aid}/",
            "images": [], "samples": [{
                "number": 1, "sha256": digest * 64, "url": f"https://images01.pixibb.com/{digest}.jpg",
                "bytes": 11000, "width": 640, "height": 900,
            }], "visited_pages": []}


def doc(*albums):
    return {"model": "mimmi", "schema_version": 1, "albums": list(albums),
            "summary": {"works": len(albums), "images_verified": len(albums),
                        "private_cloud_archived": 0}}


class Cases(unittest.TestCase):
    def test_disjoint_albums_do_not_disappear(self):
        a, b = album("album-one", "a"), album("album-two", "b")
        merged = merge_evidence(doc(a), doc(b))
        self.assertEqual([r["id"] for r in merged["albums"]], ["album-one", "album-two"])
        self.assertEqual(merged["summary"]["images_verified"], 2)
        self.assertEqual(merged["summary"]["private_cloud_archived"], 0)

    def test_transient_failed_refresh_keeps_verifiable_history(self):
        first = album("album-one", "a")
        second = album("album-one", "b")
        merged = merge_evidence(doc(first), doc(second))
        self.assertEqual([p["sha256"] for p in merged["albums"][0]["samples"]],
                         ["b"*64, "a"*64])
        self.assertEqual([p["number"] for p in merged["albums"][0]["samples"]], [1,2])
        self.assertTrue(merged["albums"][0]["samples"][1]["carried_from_previous_verification"])
        gone = album("album-one", "f")
        gone["samples"] = []
        merged_again = merge_evidence(merged, doc(gone))
        self.assertEqual(len(merged_again["albums"][0]["samples"]), 2)

    def test_identical_hash_collapses(self):
        one = album("album-one", "a")
        both = merge_evidence(doc(one), doc(one))
        self.assertEqual(len(both["albums"][0]["samples"]), 1)

    def test_never_merge_two_different_album_urls(self):
        one = album("album-one", "a")
        conflicting = album("album-one", "b", "https://cosplay.pixibb.com/different/")
        with self.assertRaisesRegex(ValueError, "distinct photo sources"):
            merge_evidence(doc(one), doc(conflicting))

    def test_reject_wrong_model_and_false_stored_images(self):
        a = album("a", "a")
        with self.assertRaises(ValueError):
            merge_evidence(None, {"model": "yui", "albums": [a]})
        a["images"] = [{"sha256": "x"*64}]
        with self.assertRaises(ValueError):
            merge_evidence(None, doc(a))


if __name__ == "__main__":
    unittest.main(verbosity=2)
