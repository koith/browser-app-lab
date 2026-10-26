#!/usr/bin/env python3
"""Offline tests for byte-preserving, ZIP-free individual photo cloud staging."""
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image
from ingest_verified_directories import build

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        source=root/"source"/"test-album"
        source.mkdir(parents=True)
        entries=[]
        for n,color in ((1,(20,30,40)),(2,(40,60,80))):
            file=f"{n:03d}.jpg"
            path=source/file
            Image.new("RGB",(640,960),color).save(path,format="JPEG")
            blob=path.read_bytes()
            entries.append({"n":n,"file":file,"sha256":hashlib.sha256(blob).hexdigest(),
                            "bytes":len(blob)})
        (source/"manifest.json").write_text(json.dumps({
            "id":"test-album","title":"Test Album","advertised_count":2,
            "source_page":"https://example.org/photo",
            "images":entries
        }))
        cloud=root/"staged"
        catalog=build([source],cloud)
        assert len(catalog["albums"])==1
        album=catalog["albums"][0]
        assert album["stored"]==album["expected"]==2
        assert album["complete_sequence"]
        for item in album["images"]:
            original=cloud/item["key"]
            preview=cloud/item["preview"]
            assert original.is_file() and preview.is_file()
            assert original.read_bytes()==preview.read_bytes(), "Lossy preview transformation forbidden"
            assert hashlib.sha256(original.read_bytes()).hexdigest()==item["sha256"]
            assert hashlib.sha256(preview.read_bytes()).hexdigest()==item["preview_sha256"]
            assert original.read_bytes()==(source/f"{item['number']:03d}.jpg").read_bytes()
        assert not list(root.rglob("*.zip"))
        # Bad hashes must not be accepted as a complete album.
        corrupted=json.loads((source/"manifest.json").read_text())
        corrupted["images"][0]["sha256"]="0"*64
        (source/"manifest.json").write_text(json.dumps(corrupted))
        try:
            build([source],root/"bad")
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupted individual file was accepted")
        print("ZIP_FREE_STAGING_SHA256_AND_PREVIEWS_PASS")

if __name__=="__main__":
    main()
