#!/usr/bin/env python3
"""Offline Mimmi private archive incremental, integrity and cross-model tests."""
import hashlib
import json
import tempfile
from pathlib import Path
from stage_private_archive import build

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);original=b"individual-public-source-image"*200
        digest=hashlib.sha256(original).hexdigest()
        album="mimmi-sample"
        source={"model":"mimmi","albums":[{"id":album,"title":"Sample Mimmi",
            "publisher":"Studio","images":[{"sha256":digest,"number":1,"bytes":len(original),
                "width":600,"height":900,"url":"https://cdn.v2ph.com/photos/sample.jpg"}]}]}
        photo=root/"private/albums/mimmi-sample/0001-test.jpg"
        photo.parent.mkdir(parents=True);photo.write_bytes(original)
        index={"model":"mimmi","files":[{"album_id":album,"number":1,"sha256":digest,
            "bytes":len(original),"path":"albums/mimmi-sample/0001-test.jpg"}]}
        write(root/"source.json",source)
        write(root/"private/private-archive-index.json",index)
        fresh=build(root/"source.json",root/"private",root/"stage")
        assert fresh["summary"]["private_photo_records"]==1
        assert (root/"stage/originals/mimmi-sample/0001-test.jpg").read_bytes()==original
        assert fresh["albums"][0]["images"][0]["sha256"]==digest
        # Re-run when source is offline and no new files were acquired:
        write(root/"private/private-archive-index.json",{"model":"mimmi","files":[]})
        append=build(root/"source.json",root/"private",root/"newstage",
                     root/"stage/metadata/catalog.json")
        assert append["summary"]["private_photo_records"]==1
        assert append["summary"]["new_file_verification_pending"]==0
        assert append["albums"][0]["images"][0]["key"]=="originals/mimmi-sample/0001-test.jpg"
        # Reject wrong-model previous archive before any remote metadata write.
        wrong={"schema_version":1,"model":"yui","albums":[]}
        write(root/"wrong.json",wrong)
        try:
            build(root/"source.json",root/"private",root/"unsafe",root/"wrong.json")
        except ValueError:pass
        else:raise AssertionError("Mixed model archive accepted")
        # Corrupt one byte; no publishable catalog may count this file.
        write(root/"private/private-archive-index.json",index)
        photo.write_bytes(original[:-1]+b"X")
        try:build(root/"source.json",root/"private",root/"corrupt")
        except ValueError:pass
        else:raise AssertionError("Tampered source photo accepted")
    print("MIMMI_PRIVATE_ARCHIVE_STAGE_QA_PASS")

if __name__=="__main__":main()
