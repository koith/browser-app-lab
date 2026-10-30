#!/usr/bin/env python3
"""Offline regression for mass social-photo bytes and owner-private ZIP batching."""
import hashlib
import io
import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw
from collect_public_social_bulk import (account_from_metadata, collect, previous_photos,
                                        sources_for, verify_bytes, public_author_timeline_limits)


def photo(index: int) -> bytes:
    img = Image.new("RGB", (420, 630), ((index * 17) % 256, (index * 23) % 256, (index * 29) % 256))
    ImageDraw.Draw(img).text((70, 105), "VALID ARCHIVED PHOTO #" + str(index), fill="white")
    data = io.BytesIO()
    img.save(data, format="JPEG", quality=85)
    return data.getvalue()


def main():
    assert public_author_timeline_limits({}) == (35, 650)
    assert public_author_timeline_limits({"GALLERY_DEEP_PUBLIC_TIMELINE": "1"}) == (100, 1800)
    with tempfile.TemporaryDirectory(prefix="gallery-social-test-") as td:
        base = Path(td)
        source = {"id": "yui-public-official-x", "title": "Yui creator test",
                  "kind": "twitter", "account": "super_yuisan",
                  "url": "https://x.com/super_yuisan/media"}
        config = {"schema_version": 1, "yui": [source]}
        digest = hashlib.sha256(photo(0)).hexdigest()
        catalog = {"schema_version": 1, "model": "yui", "albums": [
            {"id": source["id"], "images": [
                {"number": 51, "sha256": digest, "bytes": len(photo(0))}]}]}
        existing, numbers = previous_photos(catalog, "yui")
        assert digest in existing and numbers[source["id"]] == 51
        assert sources_for(config, "yui") == [source]
        bad = json.loads(json.dumps(config))
        bad["yui"][0]["url"] = "https://x.com.evil.example/super_yuisan/media"
        try:
            sources_for(bad, "yui")
        except ValueError:
            pass
        else:
            raise AssertionError("Untrusted social account host was accepted")

        def fake_run(command, item, folder):
            assert command[-1] == source["url"]
            assert "--config-ignore" in command and "--no-input" in command
            assert "--write-metadata" in command
            for n in range(345):
                path = folder / ("photo-" + str(n).zfill(5) + ".jpg")
                path.write_bytes(photo(n))
                path.with_suffix(".json").write_text(json.dumps({
                    "author": {"name": "super_yuisan"}}))
            # Unrelated photographer, despite having a valid JPEG.
            (folder / "wrong-account.jpg").write_bytes(photo(999))
            (folder / "wrong-account.json").write_text(json.dumps({
                "author": {"name": "someone_else"}}))
            (folder / "bad-file.jpg").write_bytes(b"not a photo")
            return 0

        result = collect("yui", config, catalog, base / "stage", runner=fake_run)
        assert result["actual_new_physical_images"] == 344, result
        assert result["real_private_import_zip_parts"] == 3, result
        stats = result["sources"][0]["rejected_or_previously_saved"]
        assert stats["already_sha_archived"] == 1 and stats["different_account"] == 1 and stats["bad_file"] == 1
        manifest_rows = []
        for path in sorted((base / "stage").glob("*-private-import.zip")):
            with ZipFile(path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                assert manifest["model"] == "yui"
                album = manifest["albums"][0]
                rows = album["images"]
                assert manifest["physical_verified_image_count"] == len(rows)
                assert len(rows) <= 160
                for p in rows:
                    payload = archive.read(p["url"])
                    assert hashlib.sha256(payload).hexdigest() == p["sha256"]
                    assert len(payload) == p["bytes"]
                    with Image.open(io.BytesIO(payload)) as image:
                        image.load()
                        assert (image.width, image.height) == (p["width"], p["height"])
                manifest_rows.extend(rows)
        assert [p["number"] for p in manifest_rows] == list(range(52, 396))
        assert len({p["sha256"] for p in manifest_rows}) == 344
        assert account_from_metadata(base / "stage" / "download-stage" /
                                     source["id"] / "photo-00001.jpg") == "super_yuisan"
        assert verify_bytes(base / "stage" / "download-stage" /
                            source["id"] / "photo-00001.jpg")[2:4] == (420, 630)
        print("GALLERY_SOCIAL_344_REAL_IMAGE_REGRESSION_PASS",
              json.dumps({"real_new_images": 344, "private_zip_parts": 3,
                          "existing_sha_not_duplicated": True,
                          "other_creator_rejected": True,
                          "number_sequence_preserved": True}))


if __name__ == "__main__":
    main()
