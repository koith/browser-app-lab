#!/usr/bin/env python3
"""Crawl public Mimmi photo-set pages on KGravure without login or paid tools.

Discover Mimmi model cards from the site's own Models index, follow set pages,
inspect normal public image elements, SHA-256 each actually fetched image and
publish external image URLs only. No ZIP, no CDN mirror, no access-control bypass.
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
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
HOST="kgravure.vip"
INDEX="https://kgravure.vip/en/models/"
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PublicGravureResearchCrawler/1.0)", "Accept":"text/html,image/webp,image/avif,image/*;q=.8,*/*;q=.5"})
T=(8,22)
ALBUM_IMAGE=re.compile(r"\.(jpe?g|png|webp|avif)(?:[?#]|$)",re.I)
BAD_IMAGE=re.compile(r"avatar|logo|favicon|icon|sprite|emoji|ad[-_/]|banner|google|tracking|1x1",re.I)

def in_site(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and (p.hostname==HOST or p.hostname.endswith("."+HOST)) and not p.username
    except Exception:return False
def public_image(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and (p.hostname==HOST or p.hostname.endswith("."+HOST)) and ALBUM_IMAGE.search(p.path) and not BAD_IMAGE.search(p.path) and not p.username
    except Exception:return False

def html(url):
    if not in_site(url):raise ValueError("Outside authorized site")
    r=S.get(url,timeout=T)
    r.raise_for_status()
    if not in_site(r.url):raise ValueError("Unexpected redirect host")
    if len(r.content)>7_000_000:raise ValueError("HTML too large")
    return BeautifulSoup(r.content,"html.parser"),r.url

def profiles():
    soup,base=html(INDEX)
    matched=[]
    for a in soup.select("a[href]"):
        title=a.get_text(" ",strip=True)
        href=urljoin(base,a.get("href",""))
        path=urlsplit(href).path
        if not in_site(href) or not re.fullmatch(r"/(?:en/)?models/[^/]+/?",path):continue
        if re.search(r"mimmi|밈미",title+" "+path,re.I) and href not in matched:
            matched.append(href)
    print("KGRAVURE_MIMMI_MODEL_LINKS",json.dumps(matched),flush=True)
    return matched

def album_links(profile,max_sets=70):
    soup,base=html(profile)
    links={}
    for a in soup.select("main a[href], article a[href], a[href]"):
        href=urljoin(base,a.get("href",""))
        p=urlsplit(href)
        if not in_site(href) or p.path==urlsplit(profile).path:continue
        if re.search(r"^/(en/)?(?:models|stats|company|search|blog|tags|categories|about|terms|privacy)/?",p.path,re.I):continue
        if not (re.search(r"/(?:en/)?(?:sets|set|albums|album|gallery|photo|photos|posts|collections)/",p.path,re.I)
                or re.search(r"/(?:en/)?[a-z0-9-]+/[0-9a-z-]{10,}",p.path,re.I)):
            continue
        context=a.find_parent(["article","li","div"])
        title=a.get_text(" ",strip=True)
        if context:
            h=context.select_one("h2,h3,h4,h5")
            if h:title=h.get_text(" ",strip=True) or title
        if not title:title=a.get("title","") or a.select_one("img").get("alt","") if a.select_one("img") else ""
        if len(title)<2:continue
        url=urlunsplit((p.scheme,p.netloc,p.path,"",""))
        links.setdefault(url,title[:230])
    print("KGRAVURE_PROFILE_SETS",profile,len(links),json.dumps(list(links.items())[:6]),flush=True)
    return [{"id":"kgravure-"+hashlib.sha256(url.encode()).hexdigest()[:12],
             "title":title,"source":url,"publisher":"DJAWA or credited source",
             "images":[],"samples":[],"status":"source_only"} for url,title in list(links.items())[:max_sets]]

def image_urls(soup,base):
    container=soup.select_one("main") or soup
    images=[]
    for e in container.select("img, source, a[href]"):
        attrs=("href",) if e.name=="a" else ("data-full","data-original","data-src","data-lazy-src","src","srcset","data-srcset")
        for attr in attrs:
            value=e.get(attr,"")
            if not value:continue
            for part in value.split(",") if "srcset" in attr else [value]:
                item=part.strip().split()[0]
                url=urljoin(base,item)
                if public_image(url) and url not in images:images.append(url)
    return images

def probe(url):
    try:
        r=S.get(url,timeout=T,stream=True)
        r.raise_for_status()
        if not in_site(r.url):return None
        buf=bytearray()
        for block in r.iter_content(65536):
            buf.extend(block)
            if len(buf)>16_000_000:return None
        if len(buf)<5000:return None
        with Image.open(BytesIO(buf)) as im:im.verify()
        with Image.open(BytesIO(buf)) as im:w,h=im.size
        if min(w,h)<300:return None
        return {"url":url,"width":w,"height":h,"bytes":len(buf),"sha256":hashlib.sha256(buf).hexdigest(),
                "origin":"kgravure_public","private_cloud_file":False}
    except (requests.RequestException,ValueError,OSError):
        return None

def collect(profile_limit=2,book_limit=45,images_per_book=45):
    result=[]
    profiles_found=[]
    errors=[]
    try:profiles_found=profiles()
    except Exception as e:
        errors.append({"stage":"model_index","error":type(e).__name__+": "+str(e)[:180]})
        print("KGRAVURE_MODEL_INDEX_FAILURE",errors[-1]["error"],flush=True)
    seen=set()
    for prof in profiles_found[:profile_limit]:
        try:sets=album_links(prof,book_limit)
        except Exception as e:
            errors.append({"stage":"profile","url":prof,"error":type(e).__name__+": "+str(e)[:180]});continue
        for a in sets:
            if a["source"] in seen:continue
            seen.add(a["source"])
            try:
                soup,base=html(a["source"])
                candidates=image_urls(soup,base)
                recorded=[]
                for src in candidates[:images_per_book*3]:
                    if len(recorded)>=images_per_book:break
                    sample=probe(src)
                    if sample and sample["sha256"] not in {r["sha256"] for r in recorded}:
                        sample["number"]=len(recorded)+1
                        recorded.append(sample)
                a["samples"]=recorded
                a["candidate_image_urls"]=len(candidates)
                a["status"]="public_images_verified" if recorded else "source_no_public_image_evidence"
                print("KGRAVURE_SET",len(result)+1,a["id"],len(recorded),"/",len(candidates),flush=True)
            except Exception as e:
                a["status"]="page_unavailable"
                errors.append({"stage":"album","url":a["source"],"error":type(e).__name__+": "+str(e)[:150]})
            result.append(a)
            time.sleep(.25)
    payload={"version":"v0.1.0-mimmi.4","model":"mimmi","generated_at":datetime.now(timezone.utc).isoformat(),
             "profiles":profiles_found,"errors":errors,
             "summary":{"sets_discovered":len(result),"verified_public_photo_occurrences":sum(len(a["samples"]) for a in result),
                        "private_cloud_originals":0},
             "albums":result}
    (ROOT/"kgravure-public-previews.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print("KGRAVURE_PUBLIC_RESULT",json.dumps(payload["summary"]),flush=True)
    return payload

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--profiles",type=int,default=2)
    p.add_argument("--sets",type=int,default=45)
    p.add_argument("--images",type=int,default=45)
    args=p.parse_args()
    if not 1<=args.profiles<=4 or not 1<=args.sets<=80 or not 1<=args.images<=100:p.error("Bounded crawler limits required")
    collect(args.profiles,args.sets,args.images)
