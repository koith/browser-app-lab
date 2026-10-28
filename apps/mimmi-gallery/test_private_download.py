#!/usr/bin/env python3
"""Offline QA for source integrity and unmodified individual-photo storage."""
import hashlib
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import download_public_images_private as d

class Response:
    def __init__(self, data):
        self.data = data
        self.status_code = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def raise_for_status(self):
        pass
    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self.data), chunk_size):
            yield self.data[i:i+chunk_size]

def main():
    assert not d.permitted("https://cdn.v2ph.com.evil.test/photos/photo.jpg")
    assert not d.permitted("http://cdn.v2ph.com/photos/photo.jpg")
    assert not d.permitted("https://cdn.v2ph.com/login/photo.jpg?bad=1")
    assert d.permitted("https://cdn.v2ph.com/photos/good.jpg")
    assert d.permitted("https://images08.pixibb.com/2025/05/08/photo.jpg")
    assert not d.permitted("https://images08.pixibb.com.evil.test/photo.jpg")
    assert d.permitted("https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/123.jpg?sig=public-short-lived")
    assert not d.permitted("https://scontent-ord5-2.cdninstagram.com/login/private.jpg")
    assert not d.permitted("https://scontent-ord5-2.cdninstagram.com.evil.test/v/123.jpg")

    img = Image.new("RGB", (510, 710), (150, 130, 105))
    b = BytesIO()
    img.save(b, format="JPEG", quality=97)
    raw = b.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    url = "https://cdn.v2ph.com/photos/good.jpg"
    row = {"number":1, "sha256":sha, "bytes":len(raw), "url":url}
    with tempfile.TemporaryDirectory() as temp:
        with patch.object(d.SESSION, "get", return_value=Response(raw)) as mock:
            assert d.fetch_verified(url, sha, len(raw)) == raw
            target, fresh = d.store_one(row, "sample-album", Path(temp))
            assert fresh
            assert (Path(temp) / target).read_bytes() == raw
            target2, fresh2 = d.store_one(row, "sample-album", Path(temp))
            assert target == target2 and not fresh2
            assert mock.call_count == 2
        with patch.object(d.SESSION, "get", return_value=Response(raw + b"mod")):
            try:
                d.fetch_verified(url, sha, len(raw))
                assert False, "changed content must be rejected"
            except ValueError:
                pass
    print("MIMMI_PRIVATE_INDIVIDUAL_NO_ZIP_QA_PASS")

if __name__ == "__main__":
    main()
