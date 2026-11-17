#!/usr/bin/env python3
"""Compare unindexed Yui Inven bytes with SHA-verified existing album.

Private image pixels and storage paths never leave the ephemeral runner.
Numerical similarity diagnostics are NOT automatic authorization to publish.
"""
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat
from qa_existing_owner_exact_file import read_existing

WORK="inven-public-photos"
REMOTE="archive:YuiArchive"


def signature(path):
    with Image.open(path) as raw:
        image=ImageOps.exif_transpose(raw).convert("RGB")
        if image.width<160 or image.height<160 or image.width*image.height>50_000_000:
            raise ValueError("INVALID_PIXEL_DIMENSIONS")
        small=image.resize((64,64),Image.Resampling.LANCZOS)
        gray=ImageOps.grayscale(small)
        width,height=gray.size
        px=list(gray.getdata())
        bits=0
        for y in range(8):
            for x in range(8):
                i=(y*8)*width+x*8
                bits=(bits<<1)|int(px[i]>px[i+8])
        return {"bits":bits,"color":small,"width":image.width,
                "height":image.height}


def closeness(a,b):
    diff=ImageChops.difference(a["color"],b["color"])
    mean=sum(ImageStat.Stat(diff).mean)/3
    hamming=(a["bits"]^b["bits"]).bit_count()
    return (round(mean,1),hamming)


def run(listing,catalog,saved):
    owner=next(a for a in catalog["albums"] if a["id"]==WORK)
    indexed={p["key"] for a in catalog["albums"] for p in a["images"]}
    indexed_sha={p["sha256"] for a in catalog["albums"] for p in a["images"]}
    indexed_sha.update(p.get("sha256") for a in saved.get("albums",[]) for p in a["images"])
    extra=[r for r in listing if (isinstance(r.get("Path"),str)
          and r["Path"].startswith("originals/"+WORK+"/")
          and r["Path"] not in indexed and
          r["Path"].lower().endswith((".jpg",".jpeg",".png",".webp"))
          and type(r.get("Size")) is int and 200<=r["Size"]<=10_000_000)]
    env=os.environ.copy()
    existing=[]
    rows=[]
    with tempfile.TemporaryDirectory(prefix="visual-owner-check-") as td:
        tmp=Path(td)/"image"
        for p in owner["images"]:
            tmp.unlink(missing_ok=True)
            ok,method=read_existing(REMOTE,p["key"],tmp,env)
            if not ok: raise RuntimeError("EXISTING_OWNER_ALBUM_READ_FAILED_"+method)
            with tmp.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
            if sha!=p["sha256"] or tmp.stat().st_size!=p["bytes"]:
                raise ValueError("EXISTING_OWNER_SHA_MISMATCH")
            existing.append(signature(tmp))
        for n,entry in enumerate(extra,1):
            tmp.unlink(missing_ok=True)
            ok,method=read_existing(REMOTE,entry["Path"],tmp,env)
            if not ok:
                rows.append({"row":n,"read_error":method})
                continue
            if tmp.stat().st_size!=entry["Size"]:
                rows.append({"row":n,"read_error":"size_changed"})
                continue
            with tmp.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
            if sha in indexed_sha:
                rows.append({"row":n,"is_indexed_sha":True})
                continue
            try:
                sig=signature(tmp)
                nearest=min([closeness(sig,old) for old in existing],
                            key=lambda v:(v[0],v[1]))
                nearest_hash=min([closeness(sig,old) for old in existing],
                                 key=lambda v:(v[1],v[0]))
                rows.append({"row":n,"is_indexed_sha":False,
                             "pixels":[sig["width"],sig["height"]],
                             "bytes_band":"under_500kb" if entry["Size"]<500000 else "500kb_plus",
                             "closest_color_difference":nearest[0],
                             "corresponding_dhash_distance":nearest[1],
                             "closest_dhash_distance":nearest_hash[1],
                             "corresponding_color_difference":nearest_hash[0],
                             "requires_visual_review":True})
            except (OSError,ValueError):
                rows.append({"row":n,"decode_error":True})
    return {"model":"yui","album":WORK,"existing_verified":len(existing),
            "unindexed_candidates":len(extra),"results":rows,
            "new_gallery_photos":0,"readonly":True}


if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--catalog",type=Path,required=True)
    a.add_argument("--listing",type=Path,required=True)
    a.add_argument("--saved",type=Path,required=True)
    x=a.parse_args()
    result=run(json.loads(x.listing.read_text()),json.loads(x.catalog.read_text()),
               json.loads(x.saved.read_text()))
    print("YUI_UNINDEXED_VISUAL_VERIFICATION",json.dumps(result,sort_keys=True))
