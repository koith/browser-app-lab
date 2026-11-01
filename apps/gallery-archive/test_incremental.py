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
        # The older merge compared only inflated dimensions and file size.
        # They cannot justify overwriting a different image in the same slot.
        overstated=stage/'bigger';(overstated/'metadata').mkdir(parents=True)
        fake=photo('test-album',1,'fakeupscale',pixels=4000)
        fake['bytes']=24000000
        (overstated/'metadata/catalog.json').write_text(json.dumps(catalog('yui',[fake])))
        bogus=overstated/fake['key'];bogus.parent.mkdir(parents=True,exist_ok=True)
        bogus.write_bytes(b'not-a-proven-upgrade')
        bogus_preview=overstated/fake['preview'];bogus_preview.parent.mkdir(parents=True,exist_ok=True)
        bogus_preview.write_bytes(b'not-a-proven-preview')
        negative=merge(overstated,before,'yui')
        assert negative['upgraded_photos']==0 and negative['lower_quality_rejected']==1
        retained=json.loads((overstated/'metadata/catalog.json').read_text())
        assert retained['albums'][0]['images'][0]['sha256']==old['sha256']
        assert not bogus.exists() and not bogus_preview.exists()

        # Actual same-photo measured evidence is necessary for an upgrade.
        improved=stage/'measured';(improved/'metadata').mkdir(parents=True)
        genuine=photo('test-album',1,'fine-texture',pixels=800)
        genuine['visual_quality']={
            'method':'paired-decoded-pixel-v1','confidence':'measured',
            'same_photo_verified':True,'compared_to_sha256':old['sha256'],
            'relation':'higher','previous_detail':0.03,'candidate_detail':0.07}
        genuine['variant_of_sha256']=old['sha256']
        genuine['higher_visual_quality_replacement']=True
        (improved/'metadata/catalog.json').write_text(json.dumps(catalog('yui',[genuine])))
        good=merge(improved,before,'yui')
        assert good['upgraded_photos']==1
        result=json.loads((improved/'metadata/catalog.json').read_text())
        assert result['albums'][0]['images'][0]['sha256']==genuine['sha256']
        # The same flags must not qualify for replacing a DIFFERENT hash.
        forged=stage/'wrong-reference';(forged/'metadata').mkdir(parents=True)
        bad={**genuine,'variant_of_sha256':'f'*64}
        (forged/'metadata/catalog.json').write_text(json.dumps(catalog('yui',[bad])))
        verdict=merge(forged,before,'yui')
        assert verdict['upgraded_photos']==0

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
