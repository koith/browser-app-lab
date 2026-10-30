#!/usr/bin/env python3
"""Fallback for PUBLIC Mimmi CreamSoda photo pages on Xiutu.

Only index real public category article links, inspect the model-specific
visible page and collect individually fetched, SHA-verified public image URLs.
Do not follow VIP/login/download archives, generate photo sequences, or invent
source URLs. Missing access is an explicit zero, never a completed album.
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
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gallery-archive"))
from public_crawl_transport import build_session
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
CATEGORY="https://www.xiutu.me/korea/creamsoda"
DOMAIN={"xiutu.me","www.xiutu.me"}
NAME=re.compile(r"Mimmi|밈미|밈미|ミミ|デプワ",re.I)
ARTICLE=re.compile(r"/photo/[0-9]{3,12}/?$")
S=build_session({"User-Agent":"Mozilla/5.0 (compatible; MimmiPublicPhotoResearch/1.0)",
                  "Accept":"text/html,image/jpeg,image/png,image/webp,image/*;q=.7"})
T=(10,28)

def safe_article(url):
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.hostname in DOMAIN and not p.port
                and not p.username and not p.password and not p.query
                and not p.fragment and bool(ARTICLE.fullmatch(p.path)))
    except (ValueError,TypeError):return False

def safe_page(url,root):
    try:
        p=urlsplit(url);q=urlsplit(root)
        if not (p.scheme=="https" and p.hostname in DOMAIN and not p.port
                and not p.username and not p.password and not p.fragment):return False
        if p.path.rstrip("/")==q.path.rstrip("/") and not p.query:return True
        return bool(re.fullmatch(re.escape(q.path.rstrip("/"))+r"/(?:[2-9]|[1-9][0-9])",p.path.rstrip("/"))) and not p.query
    except (ValueError,TypeError):return False

def safe_media(url):
    try:
        p=urlsplit(url)
        host=p.hostname or ""
        # Allow only the originating photo site's image subdomains.
        # Never trust similarly named attacker suffixes.
        return (p.scheme=="https" and (host in DOMAIN or host.endswith(".xiutu.me") or host=="img-jp-a.cdnimg.vip")
                and not p.username and not p.password and not p.port and not p.fragment
                and bool(re.search(r"\.(?:jpe?g|png|webp|avif)$",p.path,re.I))
                and "/api/" not in p.path and "/private/" not in p.path
                and ".." not in p.path.split("/"))
    except (ValueError,TypeError):return False

def listing_links(html,base):
    doc=BeautifulSoup(html,"html.parser")
    out=[]
    for a in doc.select("article a[href],h2 a[href],h3 a[href],.post a[href]"):
        url=urljoin(base,a.get("href",""))
        if not safe_article(url) or url in out:continue
        parent=a.find_parent("article") or a.find_parent(class_="post") or a
        title=parent.get_text(" ",strip=True)[:260]
        if NAME.search(title) and not re.search(r"(VIP|会员专享)",title,re.I):
            out.append(url)
    return out

def article_media(html,base,article_root=None):
    doc=BeautifulSoup(html,"html.parser")
    title=doc.find("h1")
    name=title.get_text(" ",strip=True) if title else ""
    if not NAME.search(name):return [],[],False
    root=(doc.select_one(".entry-content") or doc.select_one(".post-content")
          or doc.select_one("article") or doc.select_one("main") or doc)
    photos=[];next_pages=[]
    for tag in root.select("img,source,a[href]"):
        raw=[]
        if tag.name=="a":
            val=tag.get("href","")
            if val:
                u=urljoin(base,val)
                if safe_page(u,article_root or base) and u not in next_pages:next_pages.append(u)
                raw.append(val)
        else:
            for attr in ("data-original","data-full","data-src","data-lazy-src","data-url","srcset","data-srcset","src"):
                value=tag.get(attr,"")
                if value:
                    raw.extend(v.strip().split()[0] for v in value.split(",")) if "srcset" in attr else raw.append(value)
        for val in raw:
            u=urljoin(base,val)
            if not safe_media(u) or u in photos:continue
            label=tag.get("alt","").lower()
            if re.search(r"avatar|favicon|emoji|logo|banner|placeholder|advert",label):continue
            photos.append(u)
    # Many WordPress themes put the page-2/3 navigation outside article HTML.
    for a in doc.select("nav a[href],.pagination a[href],.page-links a[href],a[rel=next]"):
        u=urljoin(base,a.get("href",""))
        if safe_page(u,article_root or base) and u not in next_pages:
            next_pages.append(u)
    return photos,next_pages,True

def verify(url):
    if not safe_media(url):return None
    try:
        with S.get(url,timeout=T,stream=True,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200 or not safe_media(r.url):return None
            blob=bytearray()
            for chunk in r.iter_content(65536):
                blob.extend(chunk)
                if len(blob)>30_000_000:return None
        if len(blob)<4500:return None
        with Image.open(BytesIO(blob)) as p:p.verify()
        with Image.open(BytesIO(blob)) as p:
            w,h=p.size;format=p.format
        if min(w,h)<300 or format not in ("JPEG","PNG","WEBP","AVIF"):return None
        return {"url":url,"sha256":hashlib.sha256(blob).hexdigest(),
                "bytes":len(blob),"width":w,"height":h,
                "publisher_original_verified":False,"private_cloud_file":False}
    except (requests.RequestException,OSError,ValueError) as exc:
        print("MIMMI_XIUTU_PUBLIC_PHOTO_UNAVAILABLE",type(exc).__name__,flush=True)
        return None

def get_html(url):
    r=S.get(url,timeout=T,allow_redirects=False)
    r.raise_for_status()
    if r.status_code!=200 or urlsplit(r.url).hostname not in DOMAIN:
        raise ValueError("Not a normal public page")
    if len(r.content)>4_000_000:raise ValueError("Oversized HTML")
    return r.text

def previous_verified_photo(url, record, day=None, refresh_every=20):
    """Use previous SHA evidence only; periodically re-fetch to detect changes."""
    if not isinstance(record,dict) or record.get("url")!=url or not safe_media(url):
        return None
    if (not re.fullmatch(r"[0-9a-f]{64}",record.get("sha256",""))
            or type(record.get("bytes")) is not int or record["bytes"]<4500
            or type(record.get("width")) is not int or type(record.get("height")) is not int
            or min(record["width"],record["height"])<300):
        return None
    current=day or datetime.now(timezone.utc).date().isoformat()
    if refresh_every<1 or int(hashlib.sha256((current+"|"+url).encode()).hexdigest()[:8],16)%refresh_every==0:
        return None
    result=dict(record)
    result["previously_verified_only"]=True
    return result


def run(max_category_pages=2,max_article_pages=12,max_images=180):
    manifest=ROOT/"xiutu-public-previews.json"
    old={}
    if manifest.exists():
        try:
            data=json.loads(manifest.read_text(encoding="utf-8"))
            old={a["id"]:a for a in data.get("albums",[])}
        except (ValueError,KeyError,TypeError):pass
    discovered=[]
    for number in range(1,max_category_pages+1):
        url=CATEGORY if number==1 else CATEGORY+"/page/"+str(number)
        try:
            for link in listing_links(get_html(url),url):
                if link not in discovered:discovered.append(link)
        except (requests.RequestException,ValueError) as err:
            print("MIMMI_XIUTU_CATEGORY_UNAVAILABLE",number,type(err).__name__,flush=True)
        time.sleep(.25)
    results=[]
    for article in discovered[:40]:
        slug=urlsplit(article).path.rstrip("/").split("/")[-1]
        aid="xiutu-public-"+slug
        queue=[article];seen_pages=set();samples=[];seen_hashes=set();source_pages=[]
        old_by_url={p.get("url"):p for p in old.get(aid,{}).get("samples",[])
                    if isinstance(p.get("url"),str)}
        fresh=0;cached=0
        title="Mimmi · public CreamSoda photo page"
        while queue and len(seen_pages)<max_article_pages and len(samples)<max_images:
            current=queue.pop(0)
            if current in seen_pages or not safe_page(current,article):continue
            seen_pages.add(current)
            try:
                html=get_html(current)
                doc=BeautifulSoup(html,"html.parser")
                header=doc.find("h1")
                if header:title=header.get_text(" ",strip=True)[:175]
                urls,next_pages,identity=article_media(html,current,article)
                if not urls:
                    # Diagnostics only: identify which public CDN the publisher
                    # page actually references, instead of guessing URLs/files.
                    dom=BeautifulSoup(html,"html.parser")
                    hostnames=set()
                    props=set()
                    for im in dom.select("img,source"):
                        for attr in ("src","srcset","data-src","data-original","data-lazy-src","data-url","data-full"):
                            raw=im.get(attr,"")
                            if raw:
                                props.add(attr)
                                u=urljoin(current,raw.split(",")[0].strip().split()[0])
                                if urlsplit(u).hostname:hostnames.add(urlsplit(u).hostname)
                    print("MIMMI_XIUTU_PUBLIC_IMAGE_DOMAINS",aid,sorted(hostnames)[:15],
                          "attributes",sorted(props),flush=True)
                if not identity:break
                for u in urls:
                    if len(samples)>=max_images:break
                    photo=previous_verified_photo(u,old_by_url.get(u))
                    if photo is None:
                        photo=verify(u)
                        if photo:fresh+=1
                        time.sleep(.3)
                    else:
                        cached+=1
                    if photo and photo["sha256"] not in seen_hashes:
                        photo["number"]=len(samples)+1;samples.append(photo)
                        seen_hashes.add(photo["sha256"])
                for nxt in next_pages:
                    if nxt not in seen_pages and nxt not in queue:queue.append(nxt)
                source_pages.append({"url":current,"images_visible":len(urls)})
                print("MIMMI_XIUTU_PUBLIC_PAGE",aid,len(seen_pages),len(urls),len(samples),flush=True)
            except (requests.RequestException,ValueError) as err:
                print("MIMMI_XIUTU_PUBLIC_PAGE_UNAVAILABLE",aid,type(err).__name__,flush=True)
                break
        # Historical HTTP hash evidence is preserved but NOT counted as newly fetched.
        for p in old.get(aid,{}).get("samples",[]):
            if len(samples)>=max_images:break
            if (p.get("sha256") in seen_hashes or not safe_media(p.get("url",""))
                or not re.fullmatch(r"[a-f0-9]{64}",p.get("sha256",""))
                or type(p.get("bytes")) is not int or p["bytes"]<4500):continue
            q=dict(p);q["previously_verified_only"]=True
            samples.append(q);seen_hashes.add(q["sha256"])
        results.append({"id":aid,"title":title,"publisher":"CreamSoda","source":article,
                        "source_pages":source_pages,"images":[],"samples":samples,
                        "fresh_http_verified":fresh,"cached_previous_sha_checks":cached,
                        "status":"public_photos_sha_verified" if samples else "no_public_images_verified"})
    for old_id,item in old.items():
        if old_id not in {a["id"] for a in results} and item.get("samples"):
            results.append(item)
    payload={"schema_version":1,"model":"mimmi",
             "source":"public Xiutu CreamSoda pages visible without login; file counts NOT asserted",
             "generated_at":datetime.now(timezone.utc).isoformat(),
             "summary":{"works":len(results),"actual_sha_verified_public_photo_urls":sum(len(a["samples"]) for a in results),
                        "fresh_http_verified":sum(a.get("fresh_http_verified",0) for a in results),
                        "cached_previous_sha_checks":sum(a.get("cached_previous_sha_checks",0) for a in results),
                        "physical_files_archived":0},"albums":results}
    manifest.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_XIUTU_PUBLIC_SUMMARY",json.dumps(payload["summary"]),flush=True)
    return payload

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--category-pages",type=int,default=2)
    p.add_argument("--article-pages",type=int,default=12)
    p.add_argument("--images",type=int,default=180)
    args=p.parse_args()
    if not 1<=args.category_pages<=4 or not 1<=args.article_pages<=30 or not 1<=args.images<=400:
        p.error("bounded, source-published publicly visible pages only")
    run(args.category_pages,args.article_pages,args.images)
