#!/usr/bin/env python3
"""Stage verified individual image files for a personal cloud gallery.

Accept only folders with manifest.json + individually stored image files.
Never create, read or write compressed archives. No paid provider needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps

MAX_IMAGE_BYTES=140_000_000
ALBUM_ID=re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
SAFE_FILENAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,180}$")
FORMATS={"JPEG":"jpg","PNG":"png","WEBP":"webp","AVIF":"avif"}

def expected_count(manifest):
    for key in ("advertised_count","declared","display_count","advertised","expected"):
        if type(manifest.get(key)) is int:
            return manifest[key]
    raise ValueError("Manifest missing expected photo count")

def stage_album(input_dir:Path, dest:Path, quality:str):
    input_dir=Path(input_dir)
    manifest_file=input_dir/"manifest.json"
    if not input_dir.is_dir() or not manifest_file.is_file():
        raise ValueError(f"Expected individual files and manifest: {input_dir}")
    manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    aid=manifest.get("id")
    if not isinstance(aid,str) or not ALBUM_ID.fullmatch(aid):
        raise ValueError("Invalid album ID")
    images=manifest.get("images")
    expected=expected_count(manifest)
    if not isinstance(images,list) or len(images)!=expected or not images:
        raise ValueError(f"Incomplete image list for {aid}")
    originals=dest/"originals"/aid
    previews=dest/"previews"/aid
    originals.mkdir(parents=True,exist_ok=True)
    previews.mkdir(parents=True,exist_ok=True)
    output=[]
    seen_numbers=set()
    seen_hashes=set()
    for item in images:
        number=item.get("number",item.get("n"))
        filename=item.get("file")
        declared_sha=item.get("sha256")
        if type(number) is not int or number<1 or number>expected or number in seen_numbers:
            raise ValueError(f"Duplicate or invalid photo number: {aid}/{number}")
        if not isinstance(filename,str) or not SAFE_FILENAME.fullmatch(filename):
            raise ValueError(f"Invalid filename: {aid}")
        if not isinstance(declared_sha,str) or not re.fullmatch("[0-9a-f]{64}",declared_sha):
            raise ValueError(f"Invalid SHA256: {aid}/{number}")
        raw_path=input_dir/filename
        if not raw_path.is_file() or not 2000<raw_path.stat().st_size<MAX_IMAGE_BYTES:
            raise ValueError(f"Missing, empty or oversized photo: {aid}/{number}")
        digest=hashlib.file_digest(raw_path.open("rb"),"sha256").hexdigest()
        if digest!=declared_sha or digest in seen_hashes:
            raise ValueError(f"Photo SHA mismatch or duplicate bytes: {aid}/{number}")
        seen_numbers.add(number)
        seen_hashes.add(digest)
        with Image.open(raw_path) as im:
            im.verify()
        with Image.open(raw_path) as im:
            im.load()
            width,height=im.size
            ext=FORMATS.get(im.format)
            if not ext or min(width,height)<300:
                raise ValueError(f"Unsupported image type or resolution: {aid}/{number}")
            thumb=ImageOps.exif_transpose(im).convert("RGB")
            thumb.thumbnail((520,900))
            preview_path=previews/f"{number:04d}.jpg"
            thumb.save(preview_path,format="JPEG",quality=82,optimize=True)
        name=f"{number:04d}-{digest[:16]}.{ext}"
        image_path=originals/name
        if image_path.exists():
            if hashlib.file_digest(image_path.open("rb"),"sha256").hexdigest()!=digest:
                raise ValueError(f"Conflicting existing image: {aid}/{number}")
        else:
            # Copy unchanged publisher/web image bytes; no transcoding of original.
            with raw_path.open("rb") as src,image_path.open("wb") as target:
                while data:=src.read(256*1024):
                    target.write(data)
        assert image_path.stat().st_size==raw_path.stat().st_size
        preview_blob=preview_path.read_bytes()
        output.append({"number":number,"key":f"originals/{aid}/{name}",
                       "preview":f"previews/{aid}/{number:04d}.jpg",
                       "preview_bytes":len(preview_blob),
                       "preview_sha256":hashlib.sha256(preview_blob).hexdigest(),
                       "width":width,"height":height,
                       "bytes":raw_path.stat().st_size,"sha256":digest,
                       "origin_url":item.get("url",""),
                       "quality":quality})
    if seen_numbers!=set(range(1,expected+1)):
        raise ValueError(f"Photo sequence has gaps: {aid}")
    source=manifest.get("source_page") or manifest.get("source") or next(iter(manifest.get("source_pages",[])),"")
    return {"id":aid,"title":manifest.get("title") or aid,"source":source,
            "expected":expected,"stored":len(output),"complete_sequence":True,
            "quality_label":"public_web_resolution" if quality=="web" else "rights_confirmed_source",
            "publisher_original_verified":False,
            "images":sorted(output,key=lambda row:row["number"])}

def build(folders,output,quality="web"):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=True)
    albums=[stage_album(Path(p),root,quality) for p in folders]
    if len({a["id"] for a in albums})!=len(albums):
        raise ValueError("Duplicate album IDs")
    catalog={"schema_version":1,
             "created_at":datetime.now(timezone.utc).isoformat(),
             "access":"private authenticated gallery, not public CDN",
             "storage_provider":"pending_external_upload",
             "quality_policy":"Only label publisher original after explicit source verification.",
             "albums":sorted(albums,key=lambda a:a["title"].casefold())}
    metadata=root/"metadata"
    metadata.mkdir(parents=True,exist_ok=True)
    (metadata/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("VERIFIED_INDIVIDUAL_IMAGE_STAGE",len(albums),
          sum(a["stored"] for a in albums),flush=True)
    return catalog

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folders",nargs="+")
    p.add_argument("--out",default="cloud-stage")
    p.add_argument("--quality",choices=("web","licensed"),default="web")
    options=p.parse_args()
    build(options.folders,options.out,options.quality)
