"""No-network regression checks: only exact original bytes become private archive files."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import collect_private_batch as collector


def fixture():
    out = io.BytesIO()
    Image.new("RGB", (640, 960), (44, 55, 66)).save(out, "JPEG")
    raw = out.getvalue()
    return raw, {
        "number": 1, "url": "https://images06.pixibb.com/source/test.jpg",
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        "width": 640, "height": 960,
    }


class Response:
    status_code = 200
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def iter_content(self, chunk_size=65536):
        yield self.raw


class Tests(unittest.TestCase):
    def test_verify_unchanged_bytes(self):
        raw, p = fixture()
        with patch.object(collector.requests, "get", return_value=Response(raw)):
            saved, err = collector.verify_one(p, "https://sexy.pixibb.com/public-post/", 1)
        self.assertIsNone(err)
        self.assertEqual(saved[1], raw)
        self.assertEqual(saved[0]["sha256"], p["sha256"])
        self.assertEqual(saved[0]["url"], "photos/" + p["sha256"] + ".jpg")

    def test_wrong_integrity_fails(self):
        raw, p = fixture()
        p["sha256"] = "0" * 64
        with patch.object(collector.requests, "get", return_value=Response(raw)):
            saved, err = collector.verify_one(p, "", 1)
        self.assertIsNone(saved)
        self.assertEqual(err["reason"], "sha256_or_byte_length_mismatch")

    def test_451_or_unapproved_rejected_before_request(self):
        raw, p = fixture()
        p["url"] = "https://cdn.jliji.com/restricted.jpg"
        with patch.object(collector.requests, "get") as get:
            self.assertEqual(collector.verify_one(p, "", 1)[1]["reason"], "origin_451_not_retried")
            get.assert_not_called()
        p["url"] = "https://127.0.0.1/pic.jpg"
        self.assertEqual(collector.verify_one(p, "", 1)[1]["reason"], "unapproved_public_source")

    def test_private_zip_and_incomplete_counters(self):
        raw, p = fixture()
        a = {"id": "fixture-public", "title": "Fixture Photo Work",
             "expected": 2, "images": [p, {**p, "number": 2, "url": "https://cdn.jliji.com/restricted.jpg"}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(collector.requests, "get", return_value=Response(raw)):
                report = collector.archive(a, Path(tmp), workers=1, timeout=1)
            self.assertEqual(report["physically_saved"], 1)
            self.assertFalse(report["complete"])
            self.assertEqual(report["failed"][0]["reason"], "origin_451_not_retried")
            import zipfile
            with zipfile.ZipFile(Path(tmp) / "fixture-public-private-import.zip") as z:
                m = json.loads(z.read("manifest.json"))
                self.assertEqual(m["physical_verified_image_count"], 1)
                self.assertEqual(m["albums"][0]["status"], "partial_downloaded")
                self.assertEqual(hashlib.sha256(z.read(m["albums"][0]["images"][0]["url"])).hexdigest(), p["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
