"""Check that photo positions are retained even when identical bytes appear elsewhere."""
import unittest

from missing_candidates import safe_id, saved_positions, select_missing

A = "a" * 64
B = "b" * 64
C = "c" * 64


def candidate(id, *photos):
    return {"id": id, "title": id, "images": [{"number": n, "sha256": sha}
                                                for n, sha in photos], "expected": 80}


class MissingCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.source = {"model": "mimmi", "source_link_only": True, "albums": [
            candidate("album-a", (1, A), (2, A), (3, B)),
            candidate("album-b", (1, A), (2, C)),
            candidate("album-c", (1, A))]}

    def test_reused_sha_keeps_all_photo_numbers_and_albums(self):
        batches, count = select_missing(self.source, set(), 0, 1)
        self.assertEqual(count, 6)
        self.assertEqual([len(a["images"]) for a in batches], [3, 2, 1])
        self.assertEqual([p["number"] for p in batches[0]["images"]], [1, 2, 3])

    def test_skip_exact_saved_position_not_hash_globally(self):
        existing = {("album-a", 1, A), ("album-b", 2, C)}
        batches, count = select_missing(self.source, existing, 0, 1)
        self.assertEqual(count, 4)
        self.assertEqual([[p["number"] for p in a["images"]] for a in batches],
                         [[2, 3], [1], [1]])

    def test_same_position_different_sha_requires_identity_review(self):
        batches, count = select_missing(self.source, {("album-a", 3, C)}, 0, 1)
        self.assertEqual(count, 5)
        self.assertNotIn(3, [p["number"] for p in batches[0]["images"]])

    def test_batches_partition_without_losing_duplicate_shas(self):
        first, first_total = select_missing(self.source, set(), 0, 2)
        second, second_total = select_missing(self.source, set(), 1, 2)
        self.assertEqual(first_total, second_total)
        self.assertEqual(first_total, 6)
        self.assertEqual(sum(len(a["images"]) for a in first+second), 6)

    def test_saved_manifest_implicit_number_and_scope(self):
        stored = {"model": "mimmi", "albums": [
            {"id": "album-a", "images": [{"sha256": A}, {"number": 2, "sha256": A}]},
            {"id": "album-b", "images": [{"sha256": C}]}]}
        positions = saved_positions(stored)
        self.assertEqual(positions, {("album-a", 1, A), ("album-a", 2, A),
                                      ("album-b", 1, C)})
        batches, count = select_missing(self.source, positions, 0, 1)
        self.assertEqual(count, 3)
        self.assertEqual(len(batches[0]["images"]), 1)

    def test_source_rejects_wrong_model_or_research_incomplete(self):
        with self.assertRaises(ValueError):
            select_missing({"model": "yui", "source_link_only": True}, set(), 0, 1)
        with self.assertRaises(ValueError):
            select_missing({"model": "mimmi", "source_link_only": False}, set(), 0, 1)

    def test_duplicate_number_dropped_but_other_positions_preserved(self):
        source = {"model": "mimmi", "source_link_only": True,
                  "albums": [candidate("album-a", (1, A), (1, B), (2, A))]}
        rows, total = select_missing(source, set(), 0, 1)
        self.assertEqual(total, 2)
        self.assertEqual([p["number"] for p in rows[0]["images"]], [1, 2])

    def test_encoded_id_is_stable(self):
        expected = safe_id("name%20encoded")
        rows, count = select_missing({"model": "mimmi", "source_link_only": True,
                                      "albums": [candidate("name%20encoded", (1, A))]},
                                     {(expected, 1, A)}, 0, 1)
        self.assertEqual((rows, count), ([], 0))


if __name__ == "__main__":
    unittest.main()
