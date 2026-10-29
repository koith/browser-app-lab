#!/usr/bin/env python3
"""Test preservation of old private media when incremental source produces 1 photo."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from merge_incremental import merge

def photo(album, number, suffix, *, pixels=400):
    digest=hashlib.sha256(suffix.encode()).hexdigest()
    return {"number":number,"key":f"originals/{album}/{number:05d}-{suffix}.jpg",
            "sha256":digest,"bytes":7000,"width":pixels,"height":pixels,
            "preview":f"previews/{album}/{number:05d}-{suffix}.webp",
            "preview_sha256":digest,"preview_bytes":3000}

def catalog(model, photos):
    return {"schema_version":1,"model":model,"albums":[
        {"id":"test-album","title":"Test","expected":None,
         "images":photos}]}

def main():
    with TemporaryDirectory() as tmp:
        t=Path(tmp);stage=t/"stage";(stage/"metadata").mkdir(parents=True)
        old=photo("test-album",1,"stored")
        new=photo("test-album",2,"new")
        same=photo("test-album",1,"stored")
        fresh=catalog("yui",[same,new])
        old_data=catalog("yui",[old])
        (stage/"metadata/catalog.json").write_text(json.dumps(fresh))
        before=t/"old.json";before.write_text(json.dumps(old_data))
        for item in (same,new):
            for key in ("key","preview"):
                dest=stage/item[key];dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(b"actual-file-payload"*200)
        report=merge(stage,before,"yui")
        assert report["previous_photos"]==1 and report["new_photos"]==1
        assert not (stage/same["key"]).exists()
        assert not (stage/same["preview"]).exists()
        assert (stage/new["key"]).exists()
        assert (stage/new["preview"]).exists()
        result=json.loads((stage/"metadata/catalog.json").read_text())
        assert [i["number"] for i in result["albums"][0]["images"]]==[1,2]
        # A new source consisting of fewer photos must NOT erase the old archive.
        again=stage/"again";(again/"metadata").mkdir(parents=True)
        (again/"metadata/catalog.json").write_text(json.dumps(catalog("yui",[new])))
        previous=t/"merged.json";previous.write_text(json.dumps(result))
        second=merge(again,previous,"yui")
        assert second["total_photos"]==2
        try:merge(again,before,"mimmi")
        except ValueError:pass
        else:raise AssertionError("Mismatched owner model was imported")
        print("TERABOX_INCREMENTAL_PRESERVES_PREVIOUS_PHOTOS_AND_NUMBER_ORDER_PASS")

if __name__=="__main__":
    main()
