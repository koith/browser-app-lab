#!/usr/bin/env python3
"""Mimmi catalogue audit and authorized-photo ingestion (no ZIP, no re-encoding).

This script indexes public DJAWA/V2PH album metadata and may register individual
images ONLY when user has the right to store and serve them. No paywall bypass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image

ROOT=Path(__file__).resolve().parent
EXT={".jpg",".jpeg",".png",".webp",".avif"}
def audit(path=ROOT/"albums.json"):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    assert d["model"]["id"]=="mimmi"
    seen=set()
    for a in d["albums"]:
        assert a["id"] not in seen and re.fullmatch(r"[a-z0-9-]+",a["id"])
        seen.add(a["id"])
        assert urlparse(a["source"]).scheme=="https"
        assert a["advertised_photos"]>0
        for im in a.get("images",[]):
            assert im["sha256"] and im["bytes"]>0
    return len(seen),sum(a["advertised_photos"] for a in d["albums"]),sum(len(a.get("images",[])) for a in d["albums"])

def ingest(album_id,source_dir:Path,allow_authorized=False):
    if not allow_authorized:
        raise PermissionError("Set --authorized only for photos you have permission to store and display.")
    path=ROOT/"albums.json"; data=json.loads(path.read_text(encoding="utf-8"))
    album=next((x for x in data["albums"] if x["id"]==album_id),None)
    if album is None:raise ValueError("Unknown album")
    rows=[]
    for file in sorted(source_dir.iterdir()):
        if not file.is_file() or file.suffix.lower() not in EXT:continue
        raw=file.read_bytes()
        if len(raw)<5000:continue
        with Image.open(file) as im:
            im.verify()
        with Image.open(file) as im:
            width,height=im.size
        digest=hashlib.sha256(raw).hexdigest()
        target=ROOT/"stored-albums"/album_id/(digest+file.suffix.lower())
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes(raw) # unchanged image bytes
        rows.append({"url":"stored-albums/"+album_id+"/"+target.name,"sha256":digest,
                     "bytes":len(raw),"width":width,"height":height,"number":len(rows)+1})
    album["images"]=rows
    album["status"]="authorized_individual_files_verified" if rows else "source_indexed_not_archived"
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return len(rows)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--album")
    p.add_argument("--directory",type=Path)
    p.add_argument("--authorized",action="store_true")
    a=p.parse_args()
    if a.album or a.directory:
        if not a.album or not a.directory:p.error("Both --album and --directory are required")
        print("INDIVIDUAL_IMAGES_VERIFIED",ingest(a.album,a.directory,a.authorized))
    print("CATALOG_AUDIT",audit())
