#!/usr/bin/env python3
"""Save unchanged, already-indexed public photo bytes into a PRIVATE upload artifact.

Never count a URL, HTTP 200, resized preview or title as archived bytes.
No login/paywall, geographic-restriction bypass, third-party proxy or publication to Pages.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, io, json, re, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests
from PIL import Image

ROOT=Path(__file__).resolve().parent
MAX_FILE=24_000_000
ALLOWED_HOST=re.compile(r"^(?:imgx\d{3}|images\d{2})\.pixibb\.com$",re.I)

def verify(item,source):
    url=item.get("url") or ""
    u=urlsplit(url)
    if u.scheme!="https" or not ALLOWED_HOST.fullmatch(u.hostname or "") or u.username or u.password:
        return None,{"number":item.get("number"),"reason":"host_not_allowed"}
    try:
        with requests.get(url,headers={
            "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
            "Referer":source,
            "Accept":"image/avif,image/webp,image/*,*/*;q=0.8",
        },timeout=(12,35),stream=True,allow_redirects=False) as response:
            if response.status_code!=200:
                return None,{"number":item["number"],"reason":f"http_{response.status_code}"}
            data=bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>MAX_FILE:raise ValueError("file_over_24mb")
        raw=bytes(data)
        if len(raw)!=item["bytes"] or hashlib.sha256(raw).hexdigest()!=item["sha256"]:
            raise ValueError("byte_length_or_sha256_mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if [image.width,image.height]!=[item["width"],item["height"]]:raise ValueError("dimensions_mismatch")
            ext={"JPEG":"jpg","WEBP":"webp","PNG":"png"}.get(image.format)
            if not ext:raise ValueError("unsupported_image_format")
        row={
            "number":int(item["number"]),
            "url":f"photos/{item['sha256']}.{ext}",
            "sha256":item["sha256"],
            "bytes":len(raw),
            "width":item["width"],
            "height":item["height"],
        }
        return (row,raw),None
    except (requests.RequestException,ValueError,OSError) as error:
        return None,{"number":item.get("number"),"reason":str(error)[:180]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--album",default="green91",choices=("green91",))
    p.add_argument("--out",default="/tmp/yui-private-archive")
    p.add_argument("--workers",type=int,default=2)
    args=p.parse_args()
    source=json.loads((ROOT/"source-viewer-albums.json").read_text(encoding="utf-8"))
    album=next(a for a in source["albums"] if a["id"]==args.album)
    images=album["images"]
    assert len(images)==len(set(p["number"] for p in images)) and len(images)>10
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    passed=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(args.workers,1),3)) as ex:
        tasks={ex.submit(verify,image,album["source"]):image["number"] for image in images}
        for i,f in enumerate(concurrent.futures.as_completed(tasks),1):
            result,error=f.result()
            if result:passed.append(result)
            else:errors.append(error)
            if i%20==0 or i==len(tasks):print("PUBLIC_BYTES_CHECKED",i,"of",len(tasks),"saved",len(passed),flush=True)
    passed.sort(key=lambda x:x[0]["number"])
    manifest={"version":1,"updated":datetime.now(timezone.utc).isoformat(),"model":"yui",
              "storage":"real SHA256 verified public source bytes, private ZIP artifact not published to Pages",
              "physical_verified_image_count":len(passed),
              "albums":[{"id":album["id"],"title":album["title"],"expected":len(images),
                         "status":"complete_downloaded" if len(passed)==len(images) else "partial_downloaded",
                         "images":[row for row,_ in passed]}] if passed else []}
    audit={"verified_saved_bytes":len(passed),"expected":len(images),"missing_or_rejected":errors,"album":args.album}
    (out/"audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if passed:
        path=out/(args.album+"-private-import.zip")
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as z:
            z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
            for row,raw in passed:z.writestr(row["url"],raw)
        with zipfile.ZipFile(path) as z:
            for row,_ in passed:
                b=z.read(row["url"])
                assert len(b)==row["bytes"] and hashlib.sha256(b).hexdigest()==row["sha256"]
        print("PRIVATE_ARCHIVE_CREATED",path,"verified",len(passed),"of",len(images),flush=True)
    else:print("NO_VERIFIED_SOURCE_BYTES",args.album,flush=True)

if __name__=="__main__":main()
