#!/usr/bin/env python3
"""Copy actual creator-post photo bytes to owner-private verified TeraBox ZIPs.

Existing SNS photos from the old owner-private TeraBox catalog keep their exact
photobook photo numbers. Only NEW SHA-256 physical bytes are appended. No URL
discovery or public-photo research entry is counted as a saved photograph.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
from PIL import Image

ALBUM="public-yui-sns"
FORMAT={"JPEG":"jpg","PNG":"png","WEBP":"webp"}


def pack(inputs: Path, prior: Path, destination: Path):
    catalog=json.loads(prior.read_text(encoding="utf-8"))
    if catalog.get("model")!="yui" or catalog.get("schema_version")!=1:
        raise ValueError("Expected the real owner-private Yui TeraBox catalog")
    all_albums=catalog.get("albums",[])
    album=next((x for x in all_albums if x["id"]==ALBUM),None)
    known={im["sha256"] for a in all_albums for im in a["images"]}
    max_number=max((p["number"] for p in (album or {"images":[]})["images"]),default=0)
    src=json.loads((inputs/"manifest.json").read_text(encoding="utf-8"))
    if src.get("kind")!="public_social_attachments" or not isinstance(src.get("images"),list):
        raise ValueError("Not a verified public creator post physical image manifest")
    chosen=[]
    witnessed=set()
    for row in src["images"]:
        if row.get("author")!="super_yuisan":
            continue
        digest=row.get("sha256")
        if (not isinstance(digest,str) or len(digest)!=64
                or any(ch not in "0123456789abcdef" for ch in digest)):
            raise ValueError("Invalid photo SHA in publisher-post manifest")
        if digest in known or digest in witnessed:
            continue
        rel=row.get("file","")
        if not isinstance(rel,str) or not rel.startswith("images/") or ".." in Path(rel).parts:
            raise ValueError("Unsafe creator-post stored image")
        physical=(inputs/rel).resolve()
        if not physical.is_relative_to((inputs/"images").resolve()):
            raise ValueError("Cannot reference anything beyond downloaded photo bytes")
        content=physical.read_bytes()
        if hashlib.sha256(content).hexdigest()!=digest or len(content)!=row.get("bytes"):
            raise ValueError("Actual creator-post file digest/bytes mismatch")
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            if (image.width,image.height)!=(row.get("width"),row.get("height")):
                raise ValueError("Original photo dimensions mismatch")
            ext=FORMAT.get(image.format)
            if not ext:raise ValueError("Unsupported original image format")
        chosen.append((row,content,ext))
        witnessed.add(digest)
    # New posts may appear in discovery order on different runs. Sorting keeps
    # numbering deterministic within this batch, while the previous remote
    # catalog makes all numbers monotonic across batches and future runs.
    chosen.sort(key=lambda triple:(triple[0].get("post") or "",triple[0]["sha256"]))
    rows=[]
    for row,raw,ext in chosen:
        max_number+=1
        if max_number>20000:raise ValueError("SNS photobook numbering upper bound")
        rows.append({"number":max_number,"url":"photos/"+row["sha256"]+"."+ext,
                     "sha256":row["sha256"],"bytes":len(raw),
                     "width":row["width"],"height":row["height"]})
    report={"previous_photos_in_sns_album":len(album["images"]) if album else 0,
            "actual_creator_post_input":len(src["images"]),
            "actually_new_sha256_physical_pictures":len(rows),
            "existing_sha_photos_skipped":len(src["images"])-len(rows)}
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"sns-physical-delta.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    if rows:
        out=destination/"yui-sns-new-private-import.zip"
        manifest={"model":"yui","physical_verified_image_count":len(rows),
                  "albums":[{"id":ALBUM,"title":"심유이 공식 공개 SNS 사진",
                             "images":rows}]}
        with ZipFile(out,"w",ZIP_STORED) as z:
            z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False))
            for rec,raw,_ in chosen:
                name=next(x["url"] for x in rows if x["sha256"]==rec["sha256"])
                z.writestr(name,raw)
        with ZipFile(out) as z:
            check=json.loads(z.read("manifest.json"))
            for photo in check["albums"][0]["images"]:
                payload=z.read(photo["url"])
                assert hashlib.sha256(payload).hexdigest()==photo["sha256"]
                assert len(payload)==photo["bytes"]
    print("REAL_NEW_PUBLIC_SNS_BYTES_PACKED_PRIVATELY",json.dumps(report),flush=True)
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--previous",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    pack(a.source,a.previous,a.out)
