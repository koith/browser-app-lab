#!/usr/bin/env python3
"""Optional open-source gallery-dl extractor for verified public Yui source pages.

gallery-dl is a local GPL-licensed project, not a commercial crawling SaaS.
Each supported extractor writes unchanged image files and per-source SHA-256
metadata. Unknown websites are passed to the existing scoped Playwright crawler.
This does not log in, bypass paid content, or publish any collected bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image

IMAGE_SUFFIXES={".jpg",".jpeg",".png",".webp",".avif"}
MAX_BYTES=50_000_000
NAME=re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")

def verify_files(folder:Path)->list[dict]:
    images=[]
    seen=set()
    for item in sorted(folder.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if item.stat().st_size<5_000 or item.stat().st_size>MAX_BYTES:
            raise ValueError(f"Invalid image bytes: {item}")
        blob=item.read_bytes()
        digest=hashlib.sha256(blob).hexdigest()
        if digest in seen:
            continue
        with Image.open(item) as im:
            im.verify()
        with Image.open(item) as im:
            im.load()
            width,height=im.size
        if min(width,height)<300:
            continue
        seen.add(digest)
        metadata={}
        for sidecar in (item.with_suffix(item.suffix+".json"),item.with_suffix(".json")):
            if sidecar.is_file():
                metadata=json.loads(sidecar.read_text());break
        images.append({"number":metadata.get("num",int(item.stem) if item.stem.isdecimal() else None),
                       "url":metadata.get("image_url",""),"source_page":metadata.get("source_page",""),
                       "title":metadata.get("title",""),"ai_enhanced":metadata.get("ai_enhanced",False),
                       "path":str(item.relative_to(folder)),"sha256":digest,
                       "width":width,"height":height,"bytes":len(blob)})
    return images

def crawl_one(target:dict, base:Path, *, executable="gallery-dl", max_images=40, timeout=240):
    site_id=target["id"]
    url=target["url"]
    parsed=urlsplit(url)
    if (not NAME.fullmatch(site_id) or parsed.scheme!="https"
            or not parsed.hostname or parsed.username or parsed.password):
        raise ValueError("Unsafe source ID or HTTPS URL")
    folder=base/"photos"/site_id
    folder.mkdir(parents=True,exist_ok=True)
    db=base/"state"/(site_id+".sqlite3")
    db.parent.mkdir(parents=True,exist_ok=True)
    # Gallery-dl's --download-archive is a SQLite download HISTORY, not a ZIP.
    # The --directory option writes individual files; no postprocessing / reencoding.
    cmd=[executable,"--extractors",str(Path(__file__).with_name("gallery_dl_extractors").resolve()),"--ignore-config","--no-input","--no-mtime",
         "--write-metadata","--directory",str(folder),"--download-archive",str(db),
         "--filesize-min","5k","--filesize-max","50M",
         "--sleep-request","1.0","--sleep","0.5",
         "--range",f"1-{max_images}",url]
    started=time.monotonic()
    try:
        done=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False)
        status="ok" if done.returncode==0 else "extractor_failed_or_unsupported"
        detail=(done.stderr or "")[-500:]
        code=done.returncode
    except (subprocess.TimeoutExpired,OSError) as error:
        status="timeout_or_missing_extractor"
        detail=type(error).__name__
        code=-1
    photos=verify_files(folder)
    if photos:
        status="verified_physical_images" if status=="ok" else "partial_verified_images"
    record={"id":site_id,"url":url,"status":status,"return_code":code,
            "expected":target.get("expected"),"images":photos,"physical_verified":len(photos),
            "elapsed_seconds":round(time.monotonic()-started,2),
            "errors":detail,"collector":"gallery-dl"}
    (folder/"manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    if list(folder.rglob("*.zip")) or list(folder.rglob("*.cbz")):
        raise AssertionError("Compression output forbidden")
    expected=target.get("expected")
    if expected and len(photos)==expected and {p["number"] for p in photos}==set(range(1,expected+1)):
        dest=base/"verified-albums"/site_id
        dest.mkdir(parents=True,exist_ok=True)
        entries=[]
        for photo in photos:
            filename=f"{photo['number']:04d}"+Path(photo['path']).suffix
            shutil.copyfile(folder/photo['path'],dest/filename)
            entries.append({**photo,"file":filename})
        manifest={"id":site_id,"expected":expected,"title":photos[0].get("title") or site_id,
                  "source_page":url,"ai_enhanced":photos[0].get("ai_enhanced",False),
                  "publisher_original_verified":False,"images":sorted(entries,key=lambda p:p['number'])}
        (dest/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
        if not all(p.get("url") for p in entries):
            raise ValueError("Acquired images lack source metadata; gallery registration refused")
        from build_additional_source_manifest import build
        build([dest],Path(__file__).with_name("additional-source-albums.json"))
    return record

def run(targets:Path, base:Path, max_sources:int=4,max_images:int=40,executable="gallery-dl"):
    if shutil.which(executable) is None:
        raise FileNotFoundError("gallery-dl not installed; pip install gallery-dl")
    config=json.loads(targets.read_text(encoding="utf-8"))
    rows=[]
    for src in config.get("sources",[])[:max_sources]:
        row=crawl_one(src,base,executable=executable,max_images=max_images)
        print("OPEN_SOURCE_EXTRACTOR",row["id"],row["status"],row["physical_verified"],row["errors"][:250],flush=True)
        rows.append({k:v for k,v in row.items() if k!="images"})
    summary={"collected_at":datetime.now(timezone.utc).isoformat(),
             "configured_source_pages":len(config.get("sources",[])),
             "attempted_source_pages":len(rows),
             "physical_files":sum(x["physical_verified"] for x in rows),
             "extractors":rows,"fallback":"archive_engine.py Playwright verified source pages"}
    (base/"gallery-dl-report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--strict",action="store_true",help="Fail on zero files or an incomplete full-album run")
    parser.add_argument("--targets",type=Path,default=Path("apps/yui-gallery/gallery_dl_targets.json"))
    parser.add_argument("--out",type=Path,default=Path("yui-open-source-crawler"))
    parser.add_argument("--max-sources",type=int,default=4)
    parser.add_argument("--max-images",type=int,default=40)
    args=parser.parse_args()
    if not 1<=args.max_sources<=500 or not 1<=args.max_images<=1000:
        parser.error("Expected 1..500 source pages and 1..1000 images per page")
    report=run(args.targets,args.out,args.max_sources,args.max_images)
    if args.strict and any(x['return_code']!=0 or x['physical_verified']==0 or
            (x.get('expected') and args.max_images>=x['expected'] and x['physical_verified']!=x['expected'])
            for x in report['extractors']):
        raise SystemExit('Extractor failed/incomplete; see gallery-dl-report.json')
