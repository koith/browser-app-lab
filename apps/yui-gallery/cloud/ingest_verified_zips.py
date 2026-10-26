#!/usr/bin/env python3
"""Build a VERIFIED, non-public cloud upload staging tree from photo-album ZIPs.

Never publish commercial originals through GitHub Pages. Always preserve original
file bytes. This command is local/offline and makes no cloud access. Upload is
performed separately only if a user-authorized storage connection exists.

Each input archive must have a manifest.json with one hash per physical image.
Multiple archives may be ingested, with dedup by SHA256 *within each work*.
Quality is measured, never inferred from filename or site advertisement.
"""
from __future__ import annotations
import argparse, hashlib, io, json, re, shutil, zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps

MAX_FILE_BYTES = 140_000_000
VALID_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
FORMATS = {"JPEG":"jpg","PNG":"png","WEBP":"webp","AVIF":"avif"}

def safe_id(s):
    s=re.sub("[^a-z0-9-]+","-",str(s).casefold()).strip("-")
    if not VALID_ID.fullmatch(s):raise ValueError("Album ID invalid: "+s)
    return s

def file_entries(manifest):
    entries=manifest.get("images") or manifest.get("files")
    if not isinstance(entries,list) or not entries:raise ValueError("Archive has no declared image list")
    return entries

def expected_count(manifest):
    for key in ("declared","advertised_count","advertised","display_count","expected"):
        if isinstance(manifest.get(key),int):
            return manifest[key]
    return None

def read_album(input_zip, folder, quality):
    input_zip=Path(input_zip)
    with zipfile.ZipFile(input_zip) as archive:
        if archive.testzip() is not None:raise ValueError("Corrupt ZIP: "+str(input_zip))
        if "manifest.json" not in archive.namelist():raise ValueError("Missing manifest "+str(input_zip))
        m=json.loads(archive.read("manifest.json"))
        aid=safe_id(m.get("id") or input_zip.stem)
        title=m.get("title") or aid
        source=m.get("source_page") or m.get("source") or (m.get("source_pages") or [""])[0]
        count=expected_count(m)
        items=file_entries(m)
        album_id=aid
        dest=folder/"originals"/album_id
        preview_dest=folder/"previews"/album_id
        dest.mkdir(parents=True,exist_ok=True)
        preview_dest.mkdir(parents=True,exist_ok=True)
        output=[]
        seen_hashes=set()
        for i,row in enumerate(items,1):
            photo_num=int(row.get("number") or row.get("n") or i)
            declared_path=row.get("file")
            if not declared_path or "/" in declared_path or "\\" in declared_path:raise ValueError("Unsafe photo file name")
            candidate="images/"+declared_path
            if candidate not in archive.namelist():
                raise ValueError("Missing image physically inside ZIP: "+candidate)
            blob=archive.read(candidate)
            if not 2000<len(blob)<MAX_FILE_BYTES:raise ValueError("Invalid image size "+candidate)
            digest=hashlib.sha256(blob).hexdigest()
            if digest != row["sha256"]:raise ValueError("SHA mismatch "+candidate)
            if digest in seen_hashes:raise ValueError("Duplicate content within album "+candidate)
            seen_hashes.add(digest)
            with Image.open(io.BytesIO(blob)) as im:
                im.verify()
            with Image.open(io.BytesIO(blob)) as im:
                im.load()
                w,h=im.size;ext=FORMATS.get(im.format)
                if ext is None:raise ValueError("Unknown image type")
                if min(w,h)<300:raise ValueError("Suspicious small image")
                out_name=f"{photo_num:04d}-{digest[:16]}.{ext}"
                obj=dest/out_name
                if obj.exists() and obj.read_bytes()!=blob:raise ValueError("Existing source collision")
                obj.write_bytes(blob)
                thumb_path=preview_dest/f"{photo_num:04d}.jpg"
                with Image.open(io.BytesIO(blob)) as im:
                    thumb=ImageOps.exif_transpose(im).convert("RGB")
                    thumb.thumbnail((520,900))
                    thumb.save(thumb_path,format="JPEG",quality=82,optimize=True)
                preview_blob=thumb_path.read_bytes()
                output.append({"number":photo_num,"key":f"originals/{album_id}/{out_name}",
                               "preview":f"previews/{album_id}/{photo_num:04d}.jpg",
                               "preview_bytes":len(preview_blob),
                               "preview_sha256":hashlib.sha256(preview_blob).hexdigest(),
                               "width":w,"height":h,"bytes":len(blob),"sha256":digest,
                               "origin_url":row.get("url",""),"quality":"web" if quality=="web" else quality})
        order=[x["number"] for x in output]
        if len(set(order))!=len(order):raise ValueError("Duplicate image sequence number")
        return {"id":album_id,"title":title,"source":source,"expected":count,
                "stored":len(output),"complete_sequence":count==len(output) if count else False,
                "quality_label":"public_web_resolution" if quality=="web" else "rights_confirmed_source",
                "publisher_original_verified":False,"images":sorted(output,key=lambda x:x["number"])}

def build(inputs,output,quality="web"):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    albums=[]
    for inp in inputs:
        album=read_album(inp,output,quality)
        if any(a["id"]==album["id"] for a in albums):raise ValueError("Duplicate album ID")
        albums.append(album)
    catalog={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),
             "access":"private authenticated gallery, not public CDN",
             "storage_provider":"pending_external_upload",
             "quality_policy":"Only label publisher original after explicit source verification.",
             "albums":sorted(albums,key=lambda x:x["title"].casefold())}
    destination=output/"metadata"
    destination.mkdir(exist_ok=True)
    (destination/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={"albums":len(albums),"images":sum(a["stored"] for a in albums),
             "total_bytes":sum(x.stat().st_size for x in output.rglob("*") if x.is_file())}
    print("CLOUD_STAGE_VERIFIED",json.dumps(summary),flush=True)
    return catalog

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("zips",nargs="+")
    ap.add_argument("--out",default="cloud-stage")
    ap.add_argument("--quality",choices=["web","licensed"],default="web")
    a=ap.parse_args()
    build(a.zips,a.out,a.quality)
