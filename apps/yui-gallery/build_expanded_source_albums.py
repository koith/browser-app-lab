#!/usr/bin/env python3
"""Publish only source URL/metadata for newly verified individual public images."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from crawl_public_article import safe_remote

def build(folder:Path,out:Path):
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    rows=[]
    for item in manifest["images"]:
        image=folder/item["file"]
        if not image.is_file():
            raise ValueError("Missing photographed file")
        if hashlib.sha256(image.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("Local image SHA-256 mismatch")
        if not safe_remote(item["url"]):
            raise ValueError("Unsafe source URL")
        with Image.open(image) as opened:
            opened.verify()
        rows.append({
            "number":item["number"],"url":item["url"],"source_url":item["url"],
            "sha256":item["sha256"],"bytes":item["bytes"],
            "width":item["width"],"height":item["height"],
            "quality":"public web resolution",
            "availability":"source_hosted_not_private_cloud",
        })
    if len(rows)<10:raise ValueError("Insufficient physical images")
    expected=manifest.get("expected_publicly_displayed")
    complete=manifest["complete_sequence"] and len(rows)==expected
    album={"id":manifest["id"],"title":manifest["title"],"source":manifest["source_page"],
           "expected":expected,"images":rows,"quality":"public_web",
           "complete_sequence":complete,
           "status":"verified_collected_individual_files_source_hosted_online_view"}
    payload={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
             "kind":"external_origin_viewer_not_persistently_hosted",
             "not_private_cloud":True,"albums":[album]}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EXPANDED_SOURCE_ALBUM_ACTUAL_IMAGE_FILES",album["id"],len(rows),"/",expected,flush=True)
    return payload

if __name__=="__main__":
    build(Path("yui-article-images/heart-steal-set01"),
          Path("apps/yui-gallery/expanded-source-albums.json"))
