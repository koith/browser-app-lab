#!/usr/bin/env python3
"""Offline QA for 5 complete album manifests; reject missing or tampered photos."""
from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image
from build_source_viewer_manifest import EXPECTED,SOURCES,build

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for aid,(_,expected) in EXPECTED.items():
            dest=root/SOURCES[aid]/aid
            dest.mkdir(parents=True,exist_ok=True)
            entries=[]
            for index in range(1,expected+1):
                filename=f"{index:03d}.jpg"
                image=dest/filename
                Image.new("RGB",(600,900),(index%255,55,88)).save(image,"JPEG")
                blob=image.read_bytes()
                url=(f"https://imgx005.pixibb.com/public/{index:03d}.jpg" if aid=="green91"
                     else f"https://cdn.jliji.com/public/{aid}/{index:03d}.jpg")
                entries.append({"n":index,"file":filename,"sha256":hashlib.sha256(blob).hexdigest(),
                                "bytes":len(blob),"url":url})
            (dest/"manifest.json").write_text(json.dumps({
                "id":aid,"advertised_count":expected,
                "images":entries,"source_page":"https://example.org/page"
            }))
        target=root/"manifest-out.json"
        payload=build(root,target)
        assert len(payload["albums"])==5
        assert sum(len(a["images"]) for a in payload["albums"])==405
        assert len({a["id"] for a in payload["albums"]})==5
        assert payload["not_private_cloud"] is True
        assert all(x["url"].startswith("https://") for a in payload["albums"] for x in a["images"])
        assert not list(root.rglob("*.zip"))
        bad=root/SOURCES["green91"]/"green91"/"001.jpg"
        bad.write_bytes(b"Corrupt photo")
        try:
            build(root,root/"bad.json")
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted tampered album")
        print("ALL_405_SOURCE_VIEWER_MANIFEST_TEST_PASS")
if __name__=="__main__":
    main()
