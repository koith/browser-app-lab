#!/usr/bin/env python3
"""Monotonic private TeraBox catalog merge: never erase prior SHA-verified photos.

The previous catalog MUST have been published after a successful remote readback.
On rerun, unchanged image byte files are omitted from transfer; only new photo
positions or higher-resolution exact-number variants are copied and SHA audited.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

VALID = re.compile(r"[a-z0-9][a-z0-9-]{1,100}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")

def checked_row(model: str, album_id: str, image: dict):
    if not VALID.fullmatch(album_id):
        raise ValueError("Invalid prior album ID")
    number = image.get("number")
    if type(number) is not int or number < 1 or number > 20000:
        raise ValueError("Invalid prior numbered slot")
    original_thumbnail = image.get('preview_fallback') == 'verified-original'
    if original_thumbnail and (model != 'mimmi' or any(image.get(k) is not None
            for k in ('preview','preview_sha256','preview_bytes'))):
        raise ValueError('Original thumbnail requires Mimmi and no separate preview metadata')
    fields = (("key", "originals"),) if original_thumbnail else (("key", "originals"), ("preview", "previews"))
    for field, suffix in fields:
        path = image.get(field)
        if not isinstance(path, str) or not path.startswith(f"{suffix}/{album_id}/"):
            raise ValueError("Unsafe prior remote image key")
        if not SHA.fullmatch(image.get("sha256" if field == "key" else "preview_sha256", "")):
            raise ValueError("Invalid previous SHA")
        expected_size = image.get("bytes" if field == "key" else "preview_bytes")
        if type(expected_size) is not int or not 100 <= expected_size <= 35 * 1024 * 1024:
            raise ValueError("Invalid prior image length")
    if type(image.get("width")) is not int or type(image.get("height")) is not int:
        raise ValueError("Invalid prior dimensions")
    return (album_id, number)

def flatten(catalog: dict, model: str) -> dict:
    if catalog.get("schema_version") != 1 or catalog.get("model") != model:
        raise ValueError("Wrong TeraBox owner archive")
    if not isinstance(catalog.get("albums"), list):
        raise ValueError("Invalid TeraBox album list")
    albums={}
    for album in catalog["albums"]:
        aid=album["id"]
        if aid in albums:raise ValueError("Duplicate prior album")
        if not VALID.fullmatch(aid):raise ValueError("Invalid album identifier")
        album_photos={}
        for image in album.get("images", []):
            _, number=checked_row(model,aid,image)
            if number in album_photos:raise ValueError("Ambiguous prior photo slot")
            album_photos[number]=image
        albums[aid]={"title":album.get("title") or aid,
                     "expected":album.get("expected"),"images":album_photos}
    return albums

def merge(stage: Path, previous: Path, model: str):
    current_path=stage/"metadata/catalog.json"
    current=json.loads(current_path.read_text(encoding="utf-8"))
    staged=flatten(current,model)
    if not previous.is_file() or not previous.stat().st_size:
        raise ValueError("No SHA-verified previous private cloud catalog; bulk import must finish first")
    old=flatten(json.loads(previous.read_text(encoding="utf-8")),model)
    before=sum(len(v["images"]) for v in old.values())
    added=0;higher=0;unchanged=0;lower_or_conflict=0
    for aid, album in staged.items():
        historic=old.setdefault(aid,{"title":album["title"],"expected":None,"images":{}})
        for number, photo in album["images"].items():
            former=historic["images"].get(number)
            if former is None:
                historic["images"][number]=photo
                added+=1
                continue
            if former["sha256"]==photo["sha256"]:
                unchanged+=1
                for field in ("key","preview"):
                    if not photo.get(field):continue
                    old_file=stage/photo[field]
                    if old_file.exists():
                        old_file.unlink()
                continue
            old_quality=(former["width"]*former["height"],former["bytes"])
            new_quality=(photo["width"]*photo["height"],photo["bytes"])
            if new_quality>old_quality:
                historic["images"][number]=photo
                higher+=1
            else:
                lower_or_conflict+=1
                for field in ("key","preview"):
                    if not photo.get(field):continue
                    old_file=stage/photo[field]
                    if old_file.exists():
                        old_file.unlink()
    folders=[]
    for aid, item in sorted(old.items()):
        photos=[item["images"][n] for n in sorted(item["images"])]
        folders.append({"id":aid,"title":item["title"],"expected":None,
                        "complete":False,"images":photos})
    total=sum(len(a["images"]) for a in folders)
    result={"schema_version":1,"model":model,
            "storage":"owner-private-terabox-sha-verified-bytes",
            "albums":folders,
            "summary":{"physical_photo_positions":total,"albums":len(folders),
                       "new_photo_slots_this_import":added,
                       "higher_resolution_replacements":higher,
                       "previous_photos_retained":before}}
    current_path.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n")
    report={"model":model,"previous_photos":before,"new_photos":added,
            "upgraded_photos":higher,"unchanged":unchanged,
            "lower_quality_rejected":lower_or_conflict,"total_photos":total}
    (stage/"metadata/incremental-merge.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("TERABOX_INCREMENTAL_PHYSICAL_PHOTO_MERGE",json.dumps(report),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--previous",type=Path,required=True)
    p.add_argument("--model",choices=["yui","mimmi"],required=True)
    a=p.parse_args()
    merge(a.stage,a.previous,a.model)
