#!/usr/bin/env python3
"""Strict official publisher edition completion gate (not a photo search hit counter)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TARGETS=Path(__file__).with_name("publisher-targets.json")
NO_WATERMARK={"verified_none","verified_absent","verified_no_watermark"}

def album_photos(path,album):
    if not path.is_file():return []
    obj=json.loads(path.read_text(encoding="utf-8"))
    return next((x.get("images",[]) for x in obj.get("albums",[]) if x.get("id")==album),[])

def evaluate(root,spec,qa=None):
    base=Path(root)/"apps"/(spec["model"]+"-gallery")
    name=spec["album_id"]
    static=album_photos(base/"stored-albums.json",name)
    owner=album_photos(base/"owner-index.json",name)
    all_sha={x.get("sha256") for x in static+owner if isinstance(x.get("sha256"),str) and len(x["sha256"])==64}
    physically_verified={}
    for photo in static:
        url=photo.get("url","")
        sha=photo.get("sha256")
        if not isinstance(url,str) or not url.startswith("stored-albums/") or ".." in url.split("/") or not sha:continue
        path=base/url
        if not path.is_file():continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:continue
        physically_verified[sha]=photo
    count=spec.get("declared_photo_count")
    w,h=spec.get("declared_width"),spec.get("declared_height")
    pkg=spec.get("declared_package_bytes")
    qa=qa or {}
    checks={
        "official_quantity_verified_with_real_unique_files":type(count)==int and count>0 and len(physically_verified)>=count,
        "official_resolution_verified_for_every_file":bool(physically_verified) and bool(w and h) and all({x.get("width"),x.get("height")}=={w,h} for x in physically_verified.values()),
        "official_package_size_verified":type(pkg)==int and pkg>0 and qa.get("verified_official_package_bytes")==pkg and qa.get("full_package_sha_readback_verified") is True,
        "no_watermark_verified_for_every_file":bool(physically_verified) and all(x.get("watermark_status") in NO_WATERMARK for x in physically_verified.values()),
        "distinct_full_edition_cuts_verified":qa.get("distinct_full_edition_cuts_verified") is True,
        "all_cuts_browser_open_verified":qa.get("all_cuts_browser_open_verified") is True
    }
    complete=all(checks.values())
    return {"model":spec["model"],"album_id":name,"official_source":spec["publisher_page"],
            "declared_count":count,"declared_resolution":[w,h],
            "declared_package_bytes":pkg,"registered_unique_sha":len(all_sha),
            "repo_sha_verified_photos":len(physically_verified),
            "registered_count_gap":max(0,(count or 0)-len(all_sha)),
            "checks":checks,"complete":complete,
            "status":"COMPLETE_VERIFIED" if complete else "INCOMPLETE_OR_UNVERIFIED"}

def audit(root=ROOT,targets=TARGETS,qa=None):
    specs=json.loads(Path(targets).read_text(encoding="utf-8"))
    if specs.get("schema_version")!=1:raise ValueError("invalid_publisher_spec_schema")
    return {"schema_version":1,"results":[evaluate(root,s,(qa or {}).get(s["model"]+":"+s["album_id"])) for s in specs["works"]]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--targets",type=Path,default=TARGETS)
    p.add_argument("--qa",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    qa=json.loads(a.qa.read_text(encoding="utf-8")) if a.qa else None
    result=audit(a.root,a.targets,qa)
    if a.out:a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for row in result["results"]:
        print("OFFICIAL_EDITION_GATE",row["model"],row["album_id"],
              row["repo_sha_verified_photos"],"/",row["declared_count"],row["status"])

if __name__=="__main__":main()
