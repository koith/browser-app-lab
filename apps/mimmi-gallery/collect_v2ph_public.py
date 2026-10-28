#!/usr/bin/env python3
"""Second-source Mimmi public photo preview collector, independent of DJAWA.

Parses publicly accessible V2PH album pages, follows normal pagination only,
and SHA-verifies actual image responses without requiring login or paywall.
Keeps ONLY source URLs + metadata in publicly deployed gallery manifests.
Does NOT copy licensed photos into public GitHub Pages or create ZIP bundles.
"""
import argparse
import hashlib
import json
import re
import time
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
SOURCE_ROOT="https://www.v2ph.com"
IMAGE_HOST="cdn.v2ph.com"
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PersonalPublicPhotoViewer/1.0)",
                  "Accept":"text/html,image/avif,image/webp,image/*;q=.8,*/*;q=.5"})
T=(10,25)
def safe_source(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and p.hostname in ("www.v2ph.com","v2ph.com") and not p.username
    except Exception:return False

def safe_photo(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and p.hostname==IMAGE_HOST and p.path.startswith("/photos/") and re.search(r"\.(jpg|jpeg|webp|png)$",p.path,re.I)
    except Exception:return False

def photos_on_page(soup,base):
    out=[]
    for tag in soup.select("img,source,a[href]"):
        attrs=("href",) if tag.name=="a" else ("data-original","data-src","data-lazy-src","data-full","src","srcset")
        for attr in attrs:
            raw=tag.get(attr,"")
            if not raw:continue
            for bit in raw.split(",") if "srcset" in attr else (raw,):
                v=urljoin(base,bit.strip().split()[0])
                if safe_photo(v) and v not in out:out.append(v)
    return out

def get_bytes_verified(url):
    try:
        r=S.get(url,stream=True,timeout=T)
        r.raise_for_status()
        if not safe_photo(r.url):return None
        chunks=bytearray()
        for block in r.iter_content(65536):
            chunks.extend(block)
            if len(chunks)>15_000_000:return None
        if len(chunks)<4500:return None
        with Image.open(BytesIO(chunks)) as im:
            im.verify()
        with Image.open(BytesIO(chunks)) as im:
            w,h=im.size
        if min(w,h)<300:return None
        return {"url":url,"bytes":len(chunks),"sha256":hashlib.sha256(chunks).hexdigest(),
                "width":w,"height":h,"origin":"v2ph_public_page","private_cloud_file":False}
    except (requests.RequestException,OSError,ValueError) as error:
        print("V2PH_IMAGE_SKIPPED",type(error).__name__,url[:100],flush=True)
        return None

def run(max_pages=10,max_per_album=40):
    d=json.loads((ROOT/"v2ph-targets.json").read_text())
    found=[]
    for album in d["albums"]:
        aid=album["id"]
        raw_url=album["source"]
        if not safe_source(raw_url):
            continue
        title=album["title"]
        entries=[]
        visited_pages=[]
        seen_urls=set()
        for page in range(1,max_pages+1):
            sep="&" if "?" in raw_url else "?"
            url=raw_url if page==1 else f"{raw_url}{sep}page={page}"
            try:
                response=S.get(url,timeout=T)
                response.raise_for_status()
                if not safe_source(response.url):break
                soup=BeautifulSoup(response.content,"html.parser")
                if page>1 and not soup.find(["h1"]):break
                urls=photos_on_page(soup,response.url)
                newly=[u for u in urls if u not in seen_urls]
                if page>1 and not newly:break
                seen_urls.update(urls)
                visited_pages.append({"page":page,"url":url,"candidates":len(newly)})
                for image_url in newly:
                    if len(entries)>=max_per_album:break
                    result=get_bytes_verified(image_url)
                    if result and result["sha256"] not in {x["sha256"] for x in entries}:
                        result["number"]=len(entries)+1
                        entries.append(result)
                print("V2PH_PAGE",aid,page,len(newly),"verified",len(entries),flush=True)
                if len(entries)>=max_per_album:break
                time.sleep(.2)
            except Exception as err:
                print("V2PH_PAGE_ERROR",aid,page,type(err).__name__,str(err)[:120],flush=True)
                break
        found.append({"id":"v2ph-"+aid,"title":title+" · 공개 웹판","publisher":"DJAWA",
                      "source":raw_url,"advertised_photos":album.get("advertised_photos"),
                      "images":[],"samples":entries,"pages":visited_pages,
                      "status":"v2ph_public_samples_verified" if entries else "no_public_samples_verified"})
    payload={"schema_version":1,"version":"v0.1.0-mimmi.2",
             "generated_at":datetime.now(timezone.utc).isoformat(),
             "source":"public V2PH photobook pages, no private downloads or paid content",
             "summary":{"albums":len(found),"preview_images_verified":sum(len(a["samples"]) for a in found),
                        "publicly_rehosted_images":0},
             "albums":found}
    p=ROOT/"v2ph-public-previews.json"
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print("MIMMI_V2PH_PUBLIC_PREVIEW_RESULT",json.dumps(payload["summary"]),flush=True)
    return payload

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--pages",type=int,default=10)
    p.add_argument("--images",type=int,default=40)
    args=p.parse_args()
    if not 1<=args.pages<=20 or not 1<=args.images<=250:p.error("bounded crawl only")
    run(args.pages,args.images)
