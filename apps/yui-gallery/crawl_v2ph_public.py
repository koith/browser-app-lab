#!/usr/bin/env python3
"""Fetch only free public preview photographs on approved Yui V2PH album pages.

Do not log in, bypass per-album free limits, or access payment/subscription pages.
Preserve individual JPEG bytes and verify SHA256. A partial set is never a full
photobook, and these images are not uploaded to public Pages media folders.
"""
import concurrent.futures
import hashlib
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

TARGETS=[
    {"id":"thru-thru-public-preview","title":"SWEETBOX — Thru Thru (무료 공개 사진)","source":"https://www.v2ph.com/album/a84nmo7a.html?hl=ko","advertised":117},
    {"id":"ramen-public-preview","title":"SWEETBOX — RAMEN (무료 공개 사진)","source":"https://www.v2ph.com/album/z48oe7ez.html?hl=ko","advertised":122},
    {"id":"sweet-dream-public-preview","title":"SWEETBOX — Sweet Dream (무료 공개 사진)","source":"https://www.v2ph.com/album/ae84383z.html?hl=ko","advertised":109},
    {"id":"heart-steal-public-preview","title":"SWEETBOX — Heart Steal (무료 공개 사진)","source":"https://www.v2ph.com/album/ax7m5n4z.html?hl=ko","advertised":78},
]
MAX_FREE_IMAGES=5
CDN="cdn.v2ph.com"

def public_photo_url(raw,base):
    if not raw:return None
    url=urljoin(base,raw)
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in (CDN,"www.v2ph.com","v2ph.com"):
        return None
    if not re.search(r"\\.(?:jpg|jpeg|png|webp)(?:[?#]|$)",url,re.I):
        return None
    if "/photos/" not in p.path and p.hostname==CDN:
        return None
    return url

def discover(target):
    url=target["source"]
    found=[]
    with sync_playwright() as browser_lib:
        browser=browser_lib.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1280,"height":960})
            response=page.goto(url,wait_until="domcontentloaded",timeout=40000)
            page.wait_for_timeout(900)
            for step in range(12):
                rows=page.locator("img").evaluate_all("""els=>els.map(im=>({
                    current:im.currentSrc,src:im.getAttribute('src'),
                    full:im.getAttribute('data-original')||im.getAttribute('data-full'),
                    lazy:im.getAttribute('data-src')||im.getAttribute('data-lazy-src'),
                    alt:im.getAttribute('alt')||''
                }))""")
                for row in rows:
                    for field in ("full","lazy","current","src"):
                        asset=public_photo_url(row.get(field),url)
                        if asset and asset not in found:
                            found.append(asset)
                            break
                if len(found)>=MAX_FREE_IMAGES:break
                page.evaluate("window.scrollBy(0,Math.max(innerHeight,850))")
                page.wait_for_timeout(200)
            print("V2PH_PUBLIC_DISCOVERY",target["id"],response.status if response else "none",len(found),[(x[:110]) for x in found[:2]],flush=True)
        finally:
            browser.close()
    return found[:MAX_FREE_IMAGES]

def get_one(spec):
    number,url,origin=spec
    for attempt in range(3):
        try:
            response=requests.get(url,headers={"Referer":origin,"User-Agent":"Mozilla/5.0","Accept":"image/*"},timeout=(15,40))
            response.raise_for_status()
            raw=response.content
            if not 5000<len(raw)<25000000:raise ValueError("Image bytes invalid")
            with Image.open(io.BytesIO(raw)) as im:im.verify()
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                width,height=im.size
                ext={"JPEG":"jpg","PNG":"png","WEBP":"webp"}.get(im.format)
                if not ext or min(width,height)<300:raise ValueError("Tiny/unsupported image")
            return {"number":number,"url":url,"file":f"{number:03d}.{ext}",
                    "sha256":hashlib.sha256(raw).hexdigest(),
                    "width":width,"height":height,"bytes":len(raw)},raw
        except requests.RequestException:
            if attempt==2:raise
            time.sleep(attempt+1)

def archive(targets=TARGETS,dest=Path("yui-v2ph-public-previews")):
    records=[]
    for target in targets:
        images=discover(target)
        folder=dest/target["id"]
        folder.mkdir(parents=True,exist_ok=True)
        found={}
        errors=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            jobs={executor.submit(get_one,(i,url,target["source"])):i for i,url in enumerate(images,1)}
            for job in concurrent.futures.as_completed(jobs):
                try:
                    row,raw=job.result()
                    path=folder/row["file"]
                    path.write_bytes(raw)
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise AssertionError("Hash mismatch")
                    found[row["number"]]=row
                except Exception as error:
                    errors.append(str(error)[:150])
        data={"id":target["id"],"title":target["title"],"source_page":target["source"],
              "expected_publicly_displayed":min(len(images),MAX_FREE_IMAGES),
              "declared_full_album":target["advertised"],
              "stored":len(found),"images":[found[k] for k in sorted(found)],
              "full_album_complete":False,"quality":"public_web_preview","failures":errors,
              "checked_at":datetime.now(timezone.utc).isoformat()}
        (folder/"manifest.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        records.append({"id":target["id"],"discovered":len(images),"downloaded":len(found),"failures":len(errors)})
        print("V2PH_VERIFIED_PUBLIC_FILES",target["id"],len(found),"/",len(images),flush=True)
    (dest/"summary.json").write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return records

if __name__=="__main__":
    result=archive()
    if not any(x["downloaded"] for x in result):
        raise SystemExit("No verified public V2PH photos acquired; do not claim an additional album")
