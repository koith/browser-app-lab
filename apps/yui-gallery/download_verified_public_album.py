#!/usr/bin/env python3
"""Acquires a user-requested personal, non-public archive of freely VIEWABLE
individual photobook image pages. Do not publish downloaded files to GitHub Pages.

Only fetches explicit, previously observed, consecutively numbered image links
in public-complete-album-targets.json. No paywall, DRM or authentication bypass.
Requires actual bytes and strictly verifies 1..N before emitting COMPLETE.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from collections import Counter
import json, os, re, requests, time, zipfile
from PIL import Image, UnidentifiedImageError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path("apps/yui-gallery")
DATABASE=ROOT/"public-complete-album-targets.json"
OUTPUT=Path("yui-verified-private-albums")
OUTPUT.mkdir(parents=True,exist_ok=True)
MAX_FILE_BYTES=24_000_000
MAX_WORKERS=5

def download_one(index:int, url:str, source:str):
    session=requests.Session()
    session.mount("https://",HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
    headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
             "Referer":source,"Accept":"image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}
    with session.get(url,headers=headers,timeout=(12,35),stream=True) as response:
        response.raise_for_status()
        buf=BytesIO()
        for part in response.iter_content(65536):
            buf.write(part)
            if buf.tell()>MAX_FILE_BYTES:raise ValueError("Too large (>24MB)")
        data=buf.getvalue()
    if len(data)<8000:raise ValueError(f"Invalid tiny response: {len(data)} bytes")
    with Image.open(BytesIO(data)) as im:
        im.verify()
    with Image.open(BytesIO(data)) as im:
        im.load()
        w,h=im.size
        fmt=im.format
    if min(w,h)<300:raise ValueError(f"Too small: {w}x{h}")
    ext={"JPEG":"jpg","WEBP":"webp","PNG":"png"}.get(fmt)
    if not ext:raise ValueError(f"Unsupported format {fmt}")
    row={"number":index,"url":url,"file":f"{index:03d}.{ext}","bytes":len(data),"width":w,"height":h,"sha256":sha256(data).hexdigest()}
    return row,data

def main():
    config=json.loads(DATABASE.read_text(encoding="utf-8"))
    index_report=[]
    for album in config["albums"]:
        n=album["display_count"]
        urls=album["image_urls"]
        if len(urls)!=n or len(set(urls))!=n:raise ValueError("Discovery count mismatch")
        numbers=[]
        for url in urls:
            if urlsplit(url).hostname!="imgx001.pixibb.com":raise ValueError("Non-allowlisted download host")
            match=re.search(r"-(\d{3})\.jpg$",url)
            if not match:raise ValueError("Unverified URL pattern "+url)
            numbers.append(int(match.group(1)))
        if sorted(numbers)!=list(range(1,n+1)):raise ValueError("Photobook numbering has gaps")
        src=album["pages"][0]["url"]
        print("ALBUM_DOWNLOAD_BEGIN",album["id"],n,flush=True)
        successful={}; failed={}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            jobs={pool.submit(download_one,i,url,src):i for i,url in zip(numbers,urls)}
            for future in as_completed(jobs):
                number=jobs[future]
                try:
                    row,raw=future.result()
                    successful[number]=(row,raw)
                except Exception as e:
                    failed[number]=str(e)
                if (len(successful)+len(failed))%15==0:
                    print("ALBUM_DOWNLOAD_PROGRESS",len(successful),"/",n,"fail",len(failed),flush=True)
        folder=OUTPUT/album["id"]
        folder.mkdir(exist_ok=True,parents=True)
        for k,(row,raw) in sorted(successful.items()):
            (folder/row["file"]).write_bytes(raw)
        manifest={"id":album["id"],"title":album["title"],"source_pages":[x["url"] for x in album["pages"]],
                  "declared":n,"retrieved":len(successful),"failed":failed,
                  "checked_at":datetime.now(timezone.utc).isoformat(),
                  "images":[v[0] for _,v in sorted(successful.items())],
                  "complete_public_web_sequence":len(successful)==n and not failed,
                  "is_original_publisher_file":False,
                  "note":"Publicly displayed site images, NOT verified publisher original-size photos."}
        (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        hashes=[x["sha256"] for x in manifest["images"]]
        collisions=[k for k,c in Counter(hashes).items() if c>1]
        if collisions:raise ValueError("Duplicate actual photo content, investigate: "+str(collisions[:5]))
        zip_path=OUTPUT/(album["id"]+"_public_web_album.zip")
        with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
            for i,(row,raw) in sorted(successful.items()):z.writestr("images/"+row["file"],raw)
            z.write(folder/"manifest.json",arcname="manifest.json")
        with zipfile.ZipFile(zip_path) as z:
            assert z.testzip() is None
            assert len([name for name in z.namelist() if name.startswith("images/")])==len(successful)
        record={"id":album["id"],"expected":n,"files":len(successful),"failed":failed,"zip":str(zip_path),"size":zip_path.stat().st_size,
                "smallest_width":min((a[0]["width"] for a in successful.values()),default=0),
                "largest_width":max((a[0]["width"] for a in successful.values()),default=0)}
        index_report.append(record)
        print("ALBUM_DOWNLOAD_RESULT",json.dumps(record,ensure_ascii=False),flush=True)
        if len(successful)!=n:
            raise RuntimeError(f"Incomplete actual files: {len(successful)}/{n}. Refusing successful status.")
    (OUTPUT/"summary.json").write_text(json.dumps(index_report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FULL_PUBLIC_PAGE_ARCHIVE_VERIFIED",len(index_report),"albums",flush=True)
if __name__=="__main__":main()
