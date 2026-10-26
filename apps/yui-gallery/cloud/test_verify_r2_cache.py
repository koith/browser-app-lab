#!/usr/bin/env python3
"""Offline R2 preview-cache verification, adversarial integrity and quota tests."""
import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image
from ingest_verified_directories import build
from verify_r2_cache import check_previews, verify_remote_previews

with tempfile.TemporaryDirectory() as root_string:
    root = Path(root_string)
    folder = root / "individual-images"
    folder.mkdir()
    photo = folder / "001.png"
    Image.new("RGB", (900, 1300), (45, 80, 160)).save(photo, format="PNG")
    blob = photo.read_bytes()
    (folder / "manifest.json").write_text(json.dumps({
        "id": "sample-album", "title": "Sample", "advertised_count": 1,
        "images": [{"number": 1, "file": "001.png",
                    "sha256": hashlib.sha256(blob).hexdigest()}],
    }))
    stage = root / "stage"
    c = build([folder], stage)
    specs = check_previews(stage)
    assert len(specs) == 1
    key, size, digest = specs[0]
    assert key.startswith("previews/") and digest
    try:
        check_previews(stage, max_bytes=size - 1)
        raise AssertionError("Cache quota guard did not reject over-budget staging")
    except ValueError as error:
        assert "storage budget" in str(error)

    mirror = root / "r2"
    (mirror / "previews").mkdir(parents=True)
    shutil.copytree(stage / "previews", mirror / "previews", dirs_exist_ok=True)
    bin_dir = root / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "rclone"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\nfrom pathlib import Path\n"
        "key=sys.argv[2]\n"
        "prefix='previewcache:test-bucket/'\n"
        "if not key.startswith(prefix):sys.exit(3)\n"
        "p=Path(os.environ['TEST_R2_ROOT'])/key[len(prefix):]\n"
        "if not p.is_file():sys.exit(4)\n"
        "sys.stdout.buffer.write(p.read_bytes())\n"
    )
    fake.chmod(0o755)
    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(bin_dir) + os.pathsep + previous_path
    os.environ["TEST_R2_ROOT"] = str(mirror)
    try:
        report = verify_remote_previews(stage, "previewcache:test-bucket")
        assert report["previews"] == 1 and report["bytes"] == size
        assert len(report["objects"]) == 1
        assert (stage / "metadata/preview-cache-verification.json").is_file()
        # Do not ever read or upload originals via the cache.
        assert all(o["key"].startswith("previews/") for o in report["objects"])

        corrupted = mirror / key
        before = corrupted.read_bytes()
        corrupted.write_bytes(b"X" + before[1:])
        try:
            verify_remote_previews(stage, "previewcache:test-bucket")
            raise AssertionError("Accepted same-length corrupt R2 preview")
        except ValueError as error:
            assert "byte/hash mismatch" in str(error)
        corrupted.unlink()
        try:
            verify_remote_previews(stage, "previewcache:test-bucket")
            raise AssertionError("Accepted missing remote R2 object")
        except RuntimeError as error:
            assert "Remote read failed" in str(error)
        corrupted.parent.mkdir(parents=True, exist_ok=True)
        corrupted.write_bytes(before)

        try:
            verify_remote_previews(stage, "archive:YuiArchive")
            raise AssertionError("Allowed an origin remote as R2 target")
        except ValueError as error:
            assert "dedicated previewcache" in str(error)
    finally:
        os.environ["PATH"] = previous_path
        os.environ.pop("TEST_R2_ROOT", None)
print("R2_PRIVATE_PREVIEW_CACHE_TEST_PASS")
