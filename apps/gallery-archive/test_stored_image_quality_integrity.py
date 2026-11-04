#!/usr/bin/env python3
"""G-08: a claimed megapixel size must never hide wrong archived bytes."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from audit_stored_image_quality import verify_saved_sha

with TemporaryDirectory() as tmp:
    sample = Path(tmp) / "sample.jpg"
    original = b"\xff\xd8\xff\xe0original-saved-photo-test"
    sample.write_bytes(original)
    good = sha256(original).hexdigest()
    verify_saved_sha(sample, good)
    for expected, reason in (
        ("", "manifest_sha_missing_or_invalid"),
        ("x" * 64, "manifest_sha_missing_or_invalid"),
        ("0" * 64, "committed_file_sha256_mismatch"),
    ):
        try:
            verify_saved_sha(sample, expected)
            raise AssertionError("inconsistent SHA was accepted")
        except ValueError as exc:
            assert str(exc) == reason, (expected, str(exc))
    sample.write_bytes(original + b"tampered-bytes")
    try:
        verify_saved_sha(sample, good)
        raise AssertionError("changed bytes passed without new digest")
    except ValueError as exc:
        assert str(exc) == "committed_file_sha256_mismatch"
print("GALLERY_G08_PHYSICAL_SAVED_SHA_INTEGRITY_GATE_PASS")
