#!/usr/bin/env python3
"""Small in-memory cover, SHA readback, ETag, and private browser cache QA."""
import hashlib
import io
import json
import os

os.environ["GALLERY_ACCESS_TOKEN"] = "test-token-not-for-production"
os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"] = "fake-test-cookie"

from fastapi.testclient import TestClient
from PIL import Image
from gateway import main as gateway

source = io.BytesIO()
Image.new("RGB", (1800, 2400), (82, 106, 140)).save(source, format="JPEG", quality=92)
raw = source.getvalue()
digest = hashlib.sha256(raw).hexdigest()
fetches = {"yui": 0, "mimmi": 0}

def manifest(model):
    aid = model + "-thumbnail"
    return {
        "schema_version": 1, "model": model,
        "albums": [{"id": aid, "title": "Photo album",
                    "images": [{"number": 1, "key": f"originals/{aid}/1.jpg",
                                "bytes": len(raw), "sha256": digest}]}],
    }

async def mock_read(key, limit, *, remote=None):
    model = "yui" if remote == "archive:YuiArchive" else "mimmi"
    if key == "metadata/catalog.json":
        return json.dumps(manifest(model)).encode()
    if key == f"originals/{model}-thumbnail/1.jpg":
        fetches[model] += 1
        return raw
    raise RuntimeError(f"Unexpected read: {key!r}")

gateway.rclone_bytes = mock_read
gateway._cache.update(catalog=None, time=0)
gateway._yui_cache.update(catalog=None, time=0)

with TestClient(gateway.app) as client:
    for model in ("yui", "mimmi"):
        path = f"/api/cover/{model}/{model}-thumbnail/1?v={digest[:24]}"
        first = client.get(path)
        assert first.status_code == 200, (model, first.status_code, first.text[:200])
        assert first.headers["content-type"].startswith("image/webp")
        assert "max-age=604800" in first.headers["cache-control"]
        assert "private" in first.headers["cache-control"]
        with Image.open(io.BytesIO(first.content)) as thumb:
            assert thumb.width <= 420 and thumb.height <= 560
            assert thumb.width >= 100 and thumb.height >= 100
        assert len(first.content) < len(raw)
        same = client.get(path)
        assert same.status_code == 200 and same.content == first.content
        assert fetches[model] == 1, (model, "Cache missed", fetches)
        cached = client.get(path, headers={"If-None-Match": first.headers["etag"]})
        assert cached.status_code == 304 and not cached.content
        assert fetches[model] == 1
        assert client.get(f"/api/cover/{model}/does-not-exist/1").status_code == 404

print("BOTH_GALLERIES_SHA_VERIFIED_420PX_COVER_CACHE_AND_ETAG_PASS")
