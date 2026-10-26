#!/usr/bin/env python3
"""Connect individually verified public-source web photographs to the personal viewer.

No image bytes are committed to public GitHub Pages; they stay at their original
public image hosts. The collected individual files remain in the private staging
pipeline until an owner-authenticated storage service is connected.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image

EXPECTED = {
    "yuis-present33": ("SWEETBOX — Yui's Present", 33),
    "athletic-club104": ("Yui — Athletic Club", 104),
    "wet-yui80": ("Yui — Wet Yui", 80),
    "teddy-bear97": ("SWEETBOX — Teddy Bear", 97),
    "green91": ("Yui — Green (AI 보정본)", 91),
}
PUBLIC_HOSTS = {"cdn.jliji.com", *(f"imgx{i:03d}.pixibb.com" for i in range(1, 100))}
SOURCES = {
    "yuis-present33": "yui-jliji-full-private",
    "athletic-club104": "yui-jliji-full-private",
    "wet-yui80": "yui-jliji-full-private",
    "teddy-bear97": "yui-jliji-full-private",
    "green91": "yui-verified-private-albums",
}

def validate_source_url(url: str) -> bool:
    if not isinstance(url,str):
        return False
    parsed=urlsplit(url)
    return parsed.scheme=="https" and (parsed.hostname or "").lower() in PUBLIC_HOSTS and not parsed.username and not parsed.password

def build(base:Path, output:Path) -> dict:
    albums=[]
    for album_id,(title,expected) in EXPECTED.items():
        folder=base/SOURCES[album_id]/album_id
        manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("id") != album_id:
            raise ValueError("Unexpected album manifest: "+album_id)
        rows=manifest["images"]
        if len(rows)!=expected:
            raise ValueError(f"Incomplete {album_id}: {len(rows)}/{expected}")
        observed=set()
        photos=[]
        for image in rows:
            number=image.get("number",image.get("n"))
            url=image.get("url")
            filename=image.get("file")
            checksum=image.get("sha256")
            if type(number) is not int or number in observed or not 1<=number<=expected:
                raise ValueError("Duplicate/out of bounds image number")
            if not validate_source_url(url) or "/" in filename or "\\" in filename:
                raise ValueError("Unsafe or inaccessible image URL/path")
            source=folder/filename
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=checksum:
                raise ValueError(f"Not a locally verified image: {album_id}/{number}")
            with Image.open(source) as picture:
                picture.verify()
            with Image.open(source) as picture:
                width,height=picture.size
                if min(width,height)<300:
                    raise ValueError("Invalid image resolution")
            observed.add(number)
            photos.append({
                "number":number, "url":url, "source_url":url,
                "sha256":checksum, "bytes":source.stat().st_size,
                "width":width, "height":height,
                "quality":"AI-enhanced web copy" if album_id=="green91" else "public web resolution",
                "availability":"source_hosted_not_private_cloud",
            })
        if observed!=set(range(1,expected+1)):
            raise ValueError(f"Missing numbers in {album_id}")
        albums.append({
            "id":album_id,"title":title,"expected":expected,
            "images":sorted(photos,key=lambda r:r["number"]),
            "quality":"ai_enhanced_web" if album_id=="green91" else "public_web",
            "source":manifest.get("source_page") or (manifest.get("source_pages") or [""])[0],
            "status":"verified_collected_individual_files_source_hosted_online_view",
        })
    payload={
        "schema_version":1,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "kind":"external_origin_viewer_not_persistently_hosted",
        "not_private_cloud":True,
        "note":"405 collected and SHA256 validated individual web-resolution images. Viewer points at originating publicly accessible sites until private owner-authenticated storage is connected.",
        "albums":albums,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SOURCE_VIEWER_405_PHYSICAL_IMAGES_VERIFIED",len(albums),sum(len(a["images"]) for a in albums),flush=True)
    return payload

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--base",type=Path,default=Path("."))
    parser.add_argument("--out",type=Path,default=Path("apps/yui-gallery/source-viewer-albums.json"))
    args=parser.parse_args()
    build(args.base,args.out)
