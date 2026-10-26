#!/usr/bin/env python3
"""Offline regression test: crawler saves individual, hash-verified image files, never ZIPs."""
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from archive_engine import download

def image_bytes(rgb):
    buffer = io.BytesIO()
    Image.new("RGB", (240, 360), color=rgb).save(buffer, format="PNG")
    return buffer.getvalue()

class Response:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        pass
    def iter_content(self, size):
        for i in range(0, len(self.data), size):
            yield self.data[i:i + size]

class Session:
    def __init__(self, pictures):
        self.pictures = pictures
    def mount(self, *args):
        pass
    def get(self, url, **kwargs):
        return Response(self.pictures[url])

def main():
    a, b = "https://image.example/1.png", "https://image.example/2.png"
    images = {a: image_bytes((255, 0, 0)), b: image_bytes((0, 128, 255))}
    old = Path.cwd()
    with tempfile.TemporaryDirectory() as temp:
        try:
            os.chdir(temp)
            discovery = Path("discovery.json")
            discovery.write_text(json.dumps({"sources": [{
                "id": "fixture-album", "source_url": "https://image.example/album",
                "declared_photos": 2, "images_discovered": 2,
                "pages_visited": [], "truncated": False,
                "urls_discovered": [
                    {"url": url, "origin_page": "https://image.example/album"}
                    for url in images
                ]
            }]}))
            with patch("archive_engine.requests.Session", return_value=Session(images)), patch("archive_engine.time.sleep"):
                results = download(discovery, Path("photos"), max_images=2)
            assert results["fixture-album"]["stored_files"] == 2
            manifest = json.loads(Path("photos/fixture-album/manifest.json").read_text())
            for item in manifest["downloaded"]:
                assert item["status"] == "downloaded"
                photo = Path("photos") / item["local_path"]
                assert photo.is_file()
                blob = photo.read_bytes()
                assert hashlib.sha256(blob).hexdigest() == item["sha256"]
                assert len(blob) == item["bytes"]
                with Image.open(photo) as rendered:
                    assert rendered.size == (240, 360)
            assert not list(Path(temp).rglob("*.zip")), "Archive bundling is forbidden"
            assert len(list(Path("photos").rglob("*.png"))) == 2
            print("INDIVIDUAL_FILES_NO_ZIP_SELFTEST_PASS", flush=True)
        finally:
            os.chdir(old)

if __name__ == "__main__":
    main()
