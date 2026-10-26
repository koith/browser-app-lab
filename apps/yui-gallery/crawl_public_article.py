#!/usr/bin/env python3
"""Scrape only publicly displayed photobook images from approved article pages.

Generic Playwright lazy scrolling, actual individual image retrieval, SHA256 and
dimensions. This does not bypass logins/paywalls or bundle files.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import ipaddress
import io
import json
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from PIL import Image
from playwright.sync_api import sync_playwright

HEART_STEAL="https://jjcos.com/post/Yui%20%EC%9C%A0%EC%9D%B4%2C%20%5BSWEETBOX%5D%20SWTB%20Vol.30%20Heart%20Steal%20Set.01/"
MAX_BYTES=30_000_000
ARTICLE_SITE="jjcos.com"
IMAGE_NUM=re.compile(r"^Image\s+(\d{1,4})$",re.I)
IMAGE_FILE=re.compile(r"\.(?:jpe?g|webp|png|avif)(?:[?#]|$)",re.I)
STRIP=re.compile(r"(?:[?&#]|$)")

def safe_remote(url):
    parsed=urlsplit(url)
    host=(parsed.hostname or "").lower()
    if parsed.scheme!="https" or not host or parsed.username or parsed.password:
        return False
    if host in ("localhost",) or host.endswith((".local",".internal")):
        return False
    try:
        address=ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global

def choose_image(item,page_url):
    alt=(item.get("alt") or "").strip()
    number=IMAGE_NUM.fullmatch(alt)
    if not number:return None
    candidates=[]
    for key in ("full","href","original","current","lazy","src"):
        raw=item.get(key)
        if not raw:continue
        url=urljoin(page_url,raw.strip())
        if not safe_remote(url):continue
        quality=4 if key in ("full","href","original") and IMAGE_FILE.search(url) else 2 if key=="current" else 1
        candidates.append((quality,url))
    if not candidates:return None
    return int(number.group(1)),max(candidates,key=lambda p:p[0])[1]

def discover(url,steps=40):
    if urlsplit(url).hostname not in (ARTICLE_SITE,"www."+ARTICLE_SITE):
        raise ValueError("Only approved public article site is allowed")
    found={}
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1300,"height":950})
            response=page.goto(url,wait_until="domcontentloaded",timeout=45000)
            page.wait_for_timeout(1200)
            print("ARTICLE_PAGE_RESPONSE",response.status if response else "none","title",page.title(),"url",page.url,flush=True)
            for step in range(steps):
                items=page.evaluate("""() => Array.from(document.querySelectorAll('img')).map(im=>({
                    alt:im.alt||'',full:im.getAttribute('data-full')||im.getAttribute('data-original'),
                    original:im.getAttribute('data-zoom-image'),href:im.closest('a[href]')?.href,
                    current:im.currentSrc,lazy:im.getAttribute('data-src')||im.getAttribute('data-lazy-src'),
                    src:im.getAttribute('src')
                }))""")
                for item in items:
                    result=choose_image(item,url)
                    if result:
                        number,target=result
                        found[number]=target
                page.evaluate("window.scrollBy(0,Math.max(700,innerHeight*0.95))")
                page.wait_for_timeout(160)
            print("ARTICLE_DISCOVERY_DIAGNOSTICS","images_in_dom",len(items),"numbered_found",len(found),\n                  "sample_alt",[(x.get("alt") or "")[:30] for x in items[:8]],\n                  "sample_url",[(x.get("src") or "")[:130] for x in items[:5]],\n                  "body_prefix",page.locator("body").inner_text(timeout=7000)[:220],flush=True)
        finally:
            browser.close()
    return found

def fetch_one(item):
    number,url,referer=item
    headers={"User-Agent":"Mozilla/5.0","Referer":referer,"Accept":"image/avif,image/webp,image/png,image/jpeg,image/*;q=0.9"}
    for attempt in range(4):
        try:
            result=requests.get(url,headers=headers,timeout=(15,50))
            result.raise_for_status()
            raw=result.content
            if not 3000<len(raw)<MAX_BYTES:
                raise ValueError("Unsupported image response length")
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                w,h=image.size
                ext={"JPEG":"jpg","WEBP":"webp","PNG":"png","AVIF":"avif"}.get(image.format)
            if not ext or min(w,h)<300:
                raise ValueError("Source file is not a full image")
            return {"number":number,"url":url,"file":f"{number:03d}.{ext}",
                    "width":w,"height":h,"bytes":len(raw),
                    "sha256":hashlib.sha256(raw).hexdigest()},raw
        except requests.RequestException:
            if attempt==3:raise
            time.sleep(1.5*(attempt+1))

def archive(url,root:Path,album_id="heart-steal-set01",title="SWEETBOX — Heart Steal Set.01"):
    images=discover(url)
    if len(images)<10:raise ValueError(f"Too few public images discovered: {len(images)}")
    folder=root/album_id
    folder.mkdir(parents=True,exist_ok=True)
    got={};fail={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch_one,(num,photo,url)):num for num,photo in sorted(images.items())}
        for future in concurrent.futures.as_completed(futures):
            number=futures[future]
            try:got[number]=future.result()
            except Exception as error:fail[number]=str(error)[:180]
    rows=[]
    hashes=set()
    for num,(row,blob) in sorted(got.items()):
        if row["sha256"] in hashes:continue
        hashes.add(row["sha256"])
        path=folder/row["file"]
        path.write_bytes(blob)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise AssertionError("Image corruption")
        rows.append(row)
    manifest={"id":album_id,"title":title,"source_page":url,
              "expected_publicly_displayed":len(images),"stored":len(rows),
              "complete_sequence":len(rows)==len(images) and sorted(x["number"] for x in rows)==list(range(1,len(images)+1)),
              "images":rows,"failures":fail,"checked_at":datetime.now(timezone.utc).isoformat(),
              "publisher_original_verified":False,"compression_used":False}
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PUBLIC_ARTICLE_REAL_PHOTOS",album_id,len(images),len(rows),"failures",len(fail),flush=True)
    if len(rows)<10:raise RuntimeError("Not enough physical image files to expose")
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default=HEART_STEAL)
    parser.add_argument("--out",type=Path,default=Path("yui-article-images"))
    args=parser.parse_args()
    archive(args.url,args.out)
