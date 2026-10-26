#!/usr/bin/env python3
"""Build incremental browser-viewable album manifest from real individual public files.

Newly collected photos live in private staging. Public Pages has only URLs to
their originating freely accessible image servers, not copyrighted image bytes.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
from urllib.parse import urlsplit
from PIL import Image

def build(root=Path("yui-v2ph-public-previews"),out=Path("apps/yui-gallery/expanded-source-albums.json")):
    albums=[]
    for folder in sorted(root.iterdir()):
        manifest=folder/"manifest.json"
        if not manifest.is_file():continue
        m=json.loads(manifest.read_text(encoding="utf-8"))
        photos=[]
        hashes=set()
        for item in m["images"]:
            path=folder/item["file"]
            if not path.is_file() or path.stat().st_size!=item["bytes"]:
                raise ValueError("Missing/altered public photo file")
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest!=item["sha256"] or digest in hashes:
                raise ValueError("Photo hash mismatch or duplicate")
            hashes.add(digest)
            source=item["url"]
            p=urlsplit(source)
            if p.scheme!="https" or p.hostname!="cdn.v2ph.com" or not re.fullmatch(r"/photos/[A-Za-z0-9_.-]+\\.(?:jpg|jpeg|png|webp)",p.path,re.I):
                raise ValueError("Untrusted external image URL")
            with Image.open(path) as image:
                image.verify()
            photos.append({"number":item["number"],"url":source,"source_url":source,
                           "sha256":digest,"bytes":item["bytes"],
                           "width":item["width"],"height":item["height"],
                           "quality":"public web preview, not publisher master",
                           "availability":"source_hosted_not_private_cloud"})
        if not photos:continue
        albums.append({"id":m["id"],"title":m["title"],"source":m["source_page"],
                       "expected":m["declared_full_album"],"images":photos,
                       "quality":"public_web_preview","full_album_complete":False,
                       "status":"verified_collected_individual_files_source_hosted_online_view"})
    if not albums:
        raise ValueError("No physically verified extra public photos")
    payload={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
             "kind":"external_origin_viewer_not_persistently_hosted",
             "not_private_cloud":True,"albums":albums}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EXPANDED_REAL_PUBLIC_PHOTO_ALBUMS",len(albums),sum(len(a["images"]) for a in albums),flush=True)
    return payload

if __name__=="__main__":
    build()
