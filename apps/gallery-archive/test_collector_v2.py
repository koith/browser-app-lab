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
from collector_v2_strategy import source_evidence_pages, best_observed_variants


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
        self.html = (f'<html><main><article><h1>Pop Kitty Party</h1><p>Mimmi DJAWA</p>'
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

    def test_publisher_count_overrides_preview_count(self):
        p = self.root / "apps/gallery-archive/publisher-targets.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"schema_version": 1, "works": [{
            "model": "mimmi", "album_id": self.work,
            "declared_photo_count": 213, "declared_width": 8640,
            "declared_height": 5760}]}))
        works, _ = load_inventory(self.root, "mimmi")
        self.assertEqual(works[0]["expected"], 213)
        self.assertEqual(works[0]["gap"], 213)
        self.assertEqual(works[0]["target_basis"], "publisher")
        self.assertEqual(works[0]["declared_resolution"], [8640, 5760])

    def test_wrong_edition_not_collected_even_on_registered_page(self):
        changed = self.html.replace(b"Pop Kitty Party", b"Nikke Yuni")
        result = collect(self.root, "mimmi", self.root / "wrong-edition",
                         self.root / "wrong-edition.json",
                         http=FakeHTTP({self.page: changed, self.one: self.first_bytes}),
                         now=510000.0)
        self.assertEqual(result["new_physical_sha_staged"], 0)
        self.assertEqual(result["works"][0]["status"], "unverified_page")
        self.assertIn("identity_different_edition", result["works"][0]["errors"])

    def test_wrong_model_not_collected_despite_exact_album_title(self):
        changed = self.html.replace(b"Mimmi DJAWA", b"Yui DJAWA")
        result = collect(self.root, "mimmi", self.root / "wrong-model",
                         self.root / "wrong-model.json",
                         http=FakeHTTP({self.page: changed, self.one: self.first_bytes}),
                         now=510001.0)
        self.assertEqual(result["new_physical_sha_staged"], 0)
        self.assertIn("identity_model_not_proven_in_article", result["works"][0]["errors"])

    def test_image_srcset_prefers_only_observed_native_full_variant(self):
        native = "https://images.example.org/wp-content/uploads/2026/03/sample_01.jpg"
        scaled = "https://images.example.org/wp-content/uploads/2026/03/sample_01-800x1200.jpg"
        small = "https://images.example.org/wp-content/uploads/2026/03/sample_01-400x600.jpg"
        result = best_observed_variants([small, scaled, native])
        self.assertEqual(result, [native])
        self.assertEqual(best_observed_variants([small, scaled]), [scaled])

    def test_each_work_gets_own_staging_quota(self):
        second_id = "djawa-nikke-yuni"
        second_page = "https://example.org/photos/nikke-yuni/"
        second_img = "https://images.example.org/third.jpg"
        (self.base / "public-work-pages.json").write_text(json.dumps({
            "albums": [
                {"id": self.work, "title": "Pop Kitty Party", "source": self.page},
                {"id": second_id, "title": "Nikke Yuni", "source": second_page}]}))
        second_html = (f'<main><article><h1>Nikke Yuni</h1><p>Mimmi</p>'
                       f'<img src="{second_img}"></article></main>').encode()
        http = FakeHTTP({self.page: self.html, self.one: self.first_bytes,
                         self.two: self.second_bytes, second_page: second_html,
                         second_img: self.second_bytes})
        result = collect(self.root, "mimmi", self.root / "fair",
                         self.root / "fair.json", http=http, max_works=2,
                         max_photos=2, max_per_work=1, now=520000.0)
        self.assertEqual(result["new_physical_sha_staged"], 2)
        self.assertEqual([w["files_staged"] for w in result["works"]], [1, 1])

    def test_discovered_page_requires_valid_work_evidence_and_live_identity(self):
        discovered = "https://public.example.org/works/pop-kitty-party/"
        record = {"schema_version": 1, "model": "mimmi", "search_results": [{
            "id": self.work, "urls": [discovered], "observations": [{
                "model": "mimmi", "album_id": self.work, "source": discovered,
                "proof": "unique_named_work_page_model_and_edition"}]}]}
        evidence = self.root / "evidence.json"
        evidence.write_text(json.dumps(record))
        html = self.html.replace(self.two.encode(), b"")
        http = FakeHTTP({discovered: html, self.one: self.first_bytes})
        result = collect(self.root, "mimmi", self.root / "discovered",
                         self.root / "discovered.json", discovery_evidence=evidence,
                         http=http, now=540000.0)
        self.assertEqual(result["admitted_discovered_pages"], 1)
        self.assertEqual(result["new_physical_sha_staged"], 1)
        self.assertEqual(result["works"][0]["discovered_sources"], 1)
        record["search_results"][0]["observations"][0]["proof"] = "unverified_search_card"
        evidence.write_text(json.dumps(record))
        negative = collect(self.root, "mimmi", self.root / "untrusted",
                           self.root / "untrusted.json", discovery_evidence=evidence,
                           http=http, now=540010.0)
        self.assertEqual(negative["admitted_discovered_pages"], 0)
        self.assertEqual(negative["new_physical_sha_staged"], 0)

    def test_unpublished_candidate_url_can_retry_after_cooldown(self):
        state = self.root / "retry.json"
        fake = FakeHTTP({self.page: self.html, self.one: self.first_bytes})
        first = collect(self.root, "mimmi", self.root / "first",
                        state, http=fake, now=100000.0)
        second = collect(self.root, "mimmi", self.root / "second",
                         state, http=fake, now=100000.0 + 86401)
        self.assertEqual(first["new_physical_sha_staged"], 1)
        self.assertEqual(second["new_physical_sha_staged"], 1)

    def test_bad_photo_does_not_become_sha(self):
        with self.assertRaises(DownloadFailure):
            inspect_photo(b"<html>not a photo</html>")


if __name__ == "__main__":
    unittest.main(verbosity=2)
