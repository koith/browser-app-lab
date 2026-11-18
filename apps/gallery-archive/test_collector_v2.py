#!/usr/bin/env python3
"""Offline regression tests for the independent V2 collection path."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from collector_v2 import (DownloadFailure, QueueDB, collect, inspect_photo,
                          load_inventory, page_candidates, public_https)


class FakeHTTP:
    def __init__(self, resources):
        self.resources = resources
        self.calls = []

    def fetch(self, url, *, kind, max_bytes):
        self.calls.append((url, kind))
        if url not in self.resources:
            raise DownloadFailure("not_available")
        raw = self.resources[url]
        if len(raw) > max_bytes:
            raise DownloadFailure("too_large")
        return raw


class CollectorV2Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "apps/mimmi-gallery"
        self.base.mkdir(parents=True)
        self.work = "djawa-pop-kitty-party"
        self.page = "https://example.org/photos/pop-kitty-party/"
        self.one = "https://images.example.org/1.jpg"
        self.two = "https://images.example.org/2.jpg"
        (self.base / "public-work-pages.json").write_text(json.dumps(
            {"albums": [{"id": self.work, "title": "Pop Kitty Party",
                         "advertised_photos": 123, "source": self.page}]}))
        for name in ("owner-index.json", "stored-albums.json"):
            (self.base / name).write_text(json.dumps(
                {"albums": [{"id": self.work, "images": []}]}))
        im = Image.effect_noise((800, 600), 100).convert("RGB")
        buf = BytesIO()
        im.save(buf, "JPEG", quality=91)
        self.first_bytes = buf.getvalue()
        second = Image.effect_noise((800, 600), 150).convert("RGB")
        buf = BytesIO()
        second.save(buf, "JPEG", quality=91)
        self.second_bytes = buf.getvalue()
        self.html = (f'<html><main><article><h1>Pop Kitty Party</h1>'
                     f'<img src="{self.one}"><img data-src="{self.two}">'
                     f'</article></main><aside><img src="https://bad.example.org/a.jpg">'
                     f'</aside></html>').encode()

    def test_public_url_restrictions(self):
        for bad in ("http://example.org/1.jpg", "https://localhost/a.jpg",
                    "https://127.0.0.1/1.jpg", "https://[::1]/1.jpg",
                    "https://metadata.google.internal/a.jpg",
                    "https://example.org:444/a.jpg", "https://user:pass@example.org/1.jpg",
                    "file:///etc/passwd", "https://abc.local/a.jpg"):
            self.assertFalse(public_https(bad), bad)
        self.assertTrue(public_https(self.page))

    def test_only_main_content_images(self):
        urls = page_candidates(self.html, self.page)
        self.assertEqual(urls, [self.one, self.two])
        self.assertNotIn("https://bad.example.org/a.jpg", urls)
        banner = (f'<main><article><img src="https://example.org/Yui_Meow_bn.webp">'
                  f'<img src="{self.one}"></article></main>').encode()
        self.assertEqual(page_candidates(banner, self.page), [self.one])

    def test_inventory_and_gap(self):
        works, existing = load_inventory(self.root, "mimmi")
        self.assertEqual(works[0]["gap"], 123)
        self.assertEqual(existing, set())

    def test_real_bytes_stage_and_durable_retry(self):
        state = self.root / "checkpoints/mimmi.json"
        stage = self.root / "stage"
        http = FakeHTTP({self.page: self.html,
                         self.one: self.first_bytes, self.two: self.second_bytes})
        result = collect(self.root, "mimmi", stage, state, max_works=2,
                         max_photos=4, http=http, now=100000.0)
        self.assertEqual(result["new_physical_sha_staged"], 2)
        self.assertFalse(result["gallery_verified"])
        self.assertEqual(result["works"][0]["status"], "new_staged")
        report = json.loads((stage / "metadata/catalog.json").read_text())
        photos = report["albums"][0]["images"]
        self.assertEqual(len(photos), 2)
        for item in photos:
            raw = (stage / item["key"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])
            self.assertEqual(len(raw), item["bytes"])
            self.assertEqual((item["width"], item["height"]), (800, 600))
        self.assertTrue(state.is_file())
        repeat = collect(self.root, "mimmi", self.root / "next", state,
                         max_works=2, max_photos=4, http=http, now=100010.0)
        self.assertEqual(repeat["eligible_works"], 0)
        self.assertEqual(repeat["new_physical_sha_staged"], 0)
        self.assertEqual(len(http.calls), 3)

    def test_existing_sha_is_not_an_acquisition(self):
        digest = hashlib.sha256(self.first_bytes).hexdigest()
        (self.base / "owner-index.json").write_text(json.dumps(
            {"albums": [{"id": self.work,
                         "images": [{"sha256": digest, "number": 1}]}]}))
        http = FakeHTTP({self.page: self.html, self.one: self.first_bytes,
                         self.two: self.second_bytes})
        result = collect(self.root, "mimmi", self.root / "stage2",
                         self.root / "seen.json", http=http, now=200000.0)
        self.assertEqual(result["new_physical_sha_staged"], 1)
        self.assertEqual(result["works"][0]["known_sha"], 1)

    def test_blocked_source_is_checkpointed(self):
        http = FakeHTTP({})
        result = collect(self.root, "mimmi", self.root / "stage3",
                         self.root / "blocked.json", http=http, now=300000.0)
        self.assertEqual(result["new_physical_sha_staged"], 0)
        self.assertEqual(result["works"][0]["status"], "fetch_error")
        db = QueueDB(":memory:", self.root / "blocked.json", now=300010.0)
        self.assertEqual(db.eligible(load_inventory(self.root, "mimmi")[0], 4), [])

    def test_same_frame_recompression_does_not_use_staging_budget(self):
        from photo_visual_dedupe import WorkVisualIndex
        original = self.first_bytes
        image = Image.open(BytesIO(original))
        other = BytesIO()
        image.save(other, "JPEG", quality=80)
        reencoded = other.getvalue()
        digest = hashlib.sha256(original).hexdigest()
        folder = self.base / "stored-albums" / self.work
        folder.mkdir(parents=True)
        (folder / "original.jpg").write_bytes(original)
        (self.base / "stored-albums.json").write_text(json.dumps({
            "albums": [{"id": self.work, "images": [{
                "sha256": digest, "number": 1,
                "url": "stored-albums/" + self.work + "/original.jpg"}]}]}))
        self.assertNotEqual(digest, hashlib.sha256(reencoded).hexdigest())
        http = FakeHTTP({self.page: self.html, self.one: reencoded,
                         self.two: self.second_bytes})
        result = collect(self.root, "mimmi", self.root / "reencode-stage",
                         self.root / "reencode-checkpoint.json",
                         max_photos=2, http=http, now=400000.0)
        self.assertEqual(result["new_physical_sha_staged"], 1)
        self.assertEqual(result["works"][0]["same_frame_filtered"], 1)
        self.assertEqual(result["works"][0]["files_staged"], 1)

    def test_bad_photo_does_not_become_sha(self):
        with self.assertRaises(DownloadFailure):
            inspect_photo(b"<html>not a photo</html>")


if __name__ == "__main__":
    unittest.main(verbosity=2)
