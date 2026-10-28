#!/usr/bin/env python3
"""Mimmi Instagram-public-page individual photo byte evidence, no login/cookies.

Public profile mirror has lazy-load 'More' and per-post carousel galleries.
These CDN source URLs can expire; they are NOT durable private originals.
Never click purchase/login/download-all controls or generate hidden API URLs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qs
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
PROFILE="https://imginn.com/mimmissu17/"
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PublicMimmiInstagramIndividualPreview/1.0)",
                  "Accept":"text/html,image/jpeg,image/png,image/webp,image/*;q=0.8"})
T=(10,28)
POST=re.compile(r"^/p/[A-Za-z0-9_-]{5,35}/?$")

def allowed_page(u):
    try:
        p=urlsplit(u)
        return (p.scheme=="https" and p.hostname=="imginn.com" and not p.username and not p.password
                and not p.query and not p.fragment and not p.port
                and (p.path.rstrip("/")=="/mimmissu17" or bool(POST.fullmatch(p.path))))
    except (ValueError,TypeError):return False

def allowed_media(u):
    try:
        p=urlsplit(u)
        h=p.hostname or ""
        valid=bool(re.fullmatch(r"scontent-[a-z0-9.-]+\.cdninstagram\.com|scontent-[a-z0-9.-]+\.fbcdn\.net",h))
        return (p.scheme=="https" and valid and len(p.path)>15 and not p.username and not p.password
                and not p.port and not p.fragment and not p.path.startswith("/private/"))
    except (ValueError,TypeError):return False

def profile_verified(html):
    doc=BeautifulSoup(html,"html.parser")
    headline=(doc.title.get_text(" ",strip=True) if doc.title else "")
    body=doc.get_text(" ",strip=True)[:7000]
    return ("@mimmissu17" in headline.lower() or "@mimmissu17" in body.lower()) and bool(re.search(r"Mimmi|밈미",headline+" "+body,re.I))

def media_and_posts(html,base,post=False):
    doc=BeautifulSoup(html,"html.parser")
    if not post and not profile_verified(html):return [],[],False
    if post and not (re.search("mimmissu17",doc.get_text(" ",strip=True)[:2400],re.I) or
                     re.search("mimmissu17",doc.title.get_text(" ",strip=True) if doc.title else "",re.I)):
        return [],[],False
    photos=[];posts=[]
    for a in doc.select("a[href]"):
        url=urljoin(base,a.get("href",""))
        if allowed_page(url) and POST.fullmatch(urlsplit(url).path) and url not in posts:posts.append(url)
        # Prefer explicit on-page media download links, not anonymous avatars.
        if allowed_media(url) and "download" in a.get_text(" ",strip=True).casefold() and url not in photos:
            photos.append(url)
    # In post carousels all public image elements may be present as lazy DOM tags.
    if post:
        for im in doc.select("img,source"):
            for att in ("data-original","data-full","data-src","data-lazy-src","srcset","src"):
                raw=im.get(att,"")
                for bit in raw.split(",") if "srcset" in att else [raw]:
                    val=bit.strip().split()[0] if bit.strip() else ""
                    u=urljoin(base,val)
                    if allowed_media(u) and u not in photos:photos.append(u)
    return photos,posts,True

def lazy_profile(max_more=10,max_scrolls=35):
    from playwright.sync_api import sync_playwright
    pages=[];urls=[];seen=set();posts=set()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        try:
            page=browser.new_page(viewport={"width":1120,"height":880},service_workers="block")
            page.goto(PROFILE,wait_until="domcontentloaded",timeout=35000)
            for i in range(max_scrolls):
                photos,new_posts,ok=media_and_posts(page.content(),page.url)
                if not ok:break
                for u in photos:
                    if u not in seen:seen.add(u);urls.append(u)
                posts.update(new_posts)
                # Scroll like an ordinary visitor, letting images become visible.
                page.evaluate("window.scrollBy(0, Math.max(window.innerHeight*0.88,550))")
                page.wait_for_timeout(360)
                if (i+1)%4==0 and max_more>0:
                    # Only click a visible 'More' control; no download/login links.
                    more=page.get_by_text(re.compile(r"^More$|^더 보기$|^更多$"),exact=True)
                    if more.count()>0 and more.first.is_visible():
                        try:more.first.click(timeout=4000);page.wait_for_timeout(500);max_more-=1
                        except Exception:pass
                pages.append({"pass":i+1,"candidate_media":len(urls),"post_links":len(posts)})
            return urls,sorted(posts),pages
        finally:
            browser.close()

def image_evidence(url):
    if not allowed_media(url):return None
    try:
        with S.get(url,stream=True,timeout=T,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200 or not allowed_media(r.url):return None
            data=bytearray()
            for part in r.iter_content(65536):
                data.extend(part)
                if len(data)>30_000_000:return None
        if len(data)<4500:return None
        with Image.open(BytesIO(data)) as im:im.verify()
        with Image.open(BytesIO(data)) as im:
            w,h=im.size;fmt=im.format
        if fmt not in ("JPEG","PNG","WEBP","AVIF") or min(w,h)<280:return None
        return {"url":url,"sha256":hashlib.sha256(data).hexdigest(),
                "width":w,"height":h,"bytes":len(data),
                "origin":"public_instagram_mirror_source_link_may_expire",
                "publisher_original_verified":False,"private_cloud_file":False}
    except (requests.RequestException,ValueError,OSError) as err:
        print("MIMMI_IMG_INSTA_SOURCE_UNAVAILABLE",type(err).__name__,flush=True)
        return None

def collect(max_posts=120,max_photos=450,scroll=True):
    manifest=ROOT/"imginn-public-previews.json"
    history=[]
    if manifest.exists():
        try:history=json.loads(manifest.read_text(encoding="utf-8"))["albums"][0]["samples"]
        except (ValueError,KeyError,TypeError,IndexError):pass
    urls=[];posts=[];page_evidence=[];err=[]
    try:
        r=S.get(PROFILE,timeout=T,allow_redirects=False)
        r.raise_for_status()
        if r.status_code==200 and allowed_page(r.url):
            urls,posts,ok=media_and_posts(r.text,r.url)
            if not ok:raise ValueError("Not the verified Mimmi profile")
        else:raise ValueError("Unexpected public profile redirect")
    except (requests.RequestException,ValueError) as exc:
        err.append(type(exc).__name__)
    if scroll:
        try:
            more,more_posts,evidence=lazy_profile(max_more=15,max_scrolls=55)
            for u in more:
                if u not in urls:urls.append(u)
            posts=list(dict.fromkeys(posts+more_posts))
            page_evidence.extend(evidence)
        except Exception as exc:
            err.append("Browser:"+type(exc).__name__)
    images=[];hashes=set();seen_urls=set()
    # Only linked public account media, no guessed filenames or hidden API.
    for i,post in enumerate(posts[:max_posts],1):
        try:
            r=S.get(post,timeout=T,allow_redirects=False)
            r.raise_for_status()
            if r.status_code!=200 or not allowed_page(r.url):continue
            found,_,ok=media_and_posts(r.text,r.url,post=True)
            if ok:
                for url in found:
                    if url not in urls:urls.append(url)
            print("MIMMI_IMG_INSTA_POST",i,len(found) if ok else 0,flush=True)
        except (requests.RequestException,ValueError):
            continue
        time.sleep(.18)
    for u in urls:
        if len(images)>=max_photos:break
        if u in seen_urls:continue
        seen_urls.add(u)
        meta=image_evidence(u)
        if meta and meta["sha256"] not in hashes:
            meta["number"]=len(images)+1;images.append(meta);hashes.add(meta["sha256"])
        time.sleep(.24)
    fresh=len(images)
    for p in history:
        if len(images)>=max_photos:break
        u=p.get("url","");digest=p.get("sha256","")
        if (not allowed_media(u) or not re.fullmatch("[a-f0-9]{64}",digest)
            or digest in hashes or type(p.get("bytes")) is not int or p["bytes"]<4500
            or type(p.get("width")) is not int or type(p.get("height")) is not int
            or min(p["width"],p["height"])<280):continue
        old=dict(p);old["carried_from_previous_verification"]=True
        images.append(old);hashes.add(digest)
    for n,p in enumerate(images,1):p["number"]=n
    album={"id":"mimmi-instagram-public","title":"Mimmi (@mimmissu17) · 공개 Instagram",
           "publisher":"Mimmi","source":PROFILE,"samples":images,"images":[],
           "advertised_photos":None,"fresh_http_verified":fresh,
           "pages":page_evidence,"status":"verified_public_instagram_photos" if images else "no_verifiable_public_photos"}
    data={"schema_version":1,"model":"mimmi",
          "generated_at":datetime.now(timezone.utc).isoformat(),
          "source":"Publicly served Instagram-mirror images; URLs may expire and require fresh verification",
          "summary":{"public_media_verified":len(images),"fresh_verified":fresh,
                     "public_post_pages_visited":min(len(posts),max_posts),
                     "private_cloud_archived":0,"errors":err},"albums":[album]}
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_PUBLIC_INSTAGRAM_VERIFIED",json.dumps(data["summary"]),flush=True)
    return data

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--posts",type=int,default=120)
    ap.add_argument("--images",type=int,default=450)
    ap.add_argument("--no-scroll",action="store_true")
    args=ap.parse_args()
    if not 1<=args.posts<=250 or not 1<=args.images<=800:ap.error("bounded public only")
    collect(args.posts,args.images,not args.no_scroll)
