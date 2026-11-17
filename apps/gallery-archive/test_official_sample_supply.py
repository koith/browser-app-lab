"""Offline tests: recorded DJAWA sample saturation is not full-master completion."""
import json
import tempfile
import unittest
from pathlib import Path
from official_sample_supply import exhausted_official_samples


def put(base, name, payload):
    path = base / "apps/mimmi-gallery" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class OfficialSupplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.first = "https://djawaphoto.com/wp-content/uploads/2025/05/a.jpg"
        self.second = "https://djawaphoto.com/wp-content/uploads/2025/05/b.jpg"
        self.page = "https://djawaphoto.com/portfolio/sample-edition/"
        put(self.root, "public-work-pages.json", {"albums": [
            {"id": "sample-edition", "source": self.page}]})
        put(self.root, "official-previews.json", {
            "model": {"id": "mimmi"},
            "albums": [{"id": "sample-edition", "source": self.page,
                        "publisher": "DJAWA", "samples": [
                            {"url": self.first, "sha256": "a"*64},
                            {"url": self.second, "sha256": "b"*64}]}]})
        put(self.root, "stored-albums.json", {"model": "mimmi", "albums": [
            {"id": "sample-edition", "images": [
                {"source_url": self.first, "sha256": "c"*64}]}]})
        put(self.root, "owner-index.json", {"model": "mimmi", "albums": []})

    def test_partial_source_is_not_exhausted(self):
        self.assertEqual(exhausted_official_samples(self.root), set())

    def test_alternate_encoded_public_file_satisfies_same_work_url(self):
        put(self.root, "stored-albums.json", {"model": "mimmi", "albums": [
            {"id": "sample-edition", "images": [
                {"source_url": self.first, "sha256": "c"*64},
                {"source_url": self.second, "sha256": "d"*64}]}]})
        self.assertEqual(exhausted_official_samples(self.root),
                         {"sample-edition"})

    def test_actual_sha_verified_in_owner_satisfies_missing_url(self):
        put(self.root, "owner-index.json", {"model": "mimmi", "albums": [
            {"id": "sample-edition", "images": [{"sha256": "b"*64}]}]})
        self.assertEqual(exhausted_official_samples(self.root),
                         {"sample-edition"})

    def test_wrong_album_url_does_not_satisfy_sample(self):
        put(self.root, "stored-albums.json", {"model": "mimmi", "albums": [
            {"id": "another-album", "images": [
                {"source_url": self.first, "sha256": "c"*64},
                {"source_url": self.second, "sha256": "d"*64}]}]})
        self.assertEqual(exhausted_official_samples(self.root), set())

    def test_new_official_url_reopens_supply(self):
        put(self.root, "official-previews.json", {
            "model": {"id": "mimmi"}, "albums": [{
                "id": "sample-edition", "source": self.page,
                "publisher": "DJAWA", "samples": [
                    {"url": self.first, "sha256": "a"*64},
                    {"url": self.second, "sha256": "b"*64},
                    {"url": self.page+"new.jpg", "sha256": "e"*64}]}]})
        self.assertEqual(exhausted_official_samples(self.root), set())

    def test_yui_not_automatically_marked_exhausted(self):
        self.assertEqual(exhausted_official_samples(self.root, "yui"), set())


if __name__ == "__main__":
    unittest.main()
