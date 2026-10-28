#!/usr/bin/env python3
"""Verify Mimmi public publisher-linked Gumroad PROMO images only.

The official Mimmi portfolio is the sole source of product links. Never follow
download links, cookies, login, buyer-only files or paid product assets.
Media is fetched solely from public HTML img/meta tags, not guessed URLs.
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
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PublicMimmiPromoImageResearch/1.0)","Accept":"text/html,image/webp,image/avif,image/*;q=.8,*/*;q=.5"})
IMAGE_HOSTS={"public-files.gumroad.com","assets.gumroad.com","static-2.gumroad.com"}
TIMEOUT=(10,22)

def product_url(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and p.hostname=="djawaphoto.gumroad.com" and bool(re.fullmatch(r"/l/[A-Za-z0-9_-]{2,120}/?",p.path)) and not p.username and not p.password
    except (TypeError,ValueError):return False

def preview_url(u):
    try:
        p=urlsplit(u)
        return p.scheme=="https" and p.hostname in IMAGE_HOSTS and not p.username and not p.password and not p.port and len(p.path)>8 and not re.search(r"\.(?:js|css|svg|woff\d?|ico)$",p.path,re.I)
    except (TypeError,ValueError):return False

def from_portfolio(html,base):
    doc=BeautifulSoup(html,"html.parser")
    out=[]
    for a in doc.select("a[href]"):
        url=urljoin(base,a.get("href",""))
        if product_url(url) and url not in out:out.append(url)
    return out

def promo_candidates(html,base):
    soup=BeautifulSoup(html,"html.parser")
    urls=[]
    for item in soup.select('meta[property="og:image"],meta[name="twitter:image"],img,source'):
        attrs=["content"] if item.name=="meta" else ["src","data-src","srcset"]
        for attr in attrs:
            raw=item.get(attr,"")
            if not raw:continue
            for frag in raw.split(",") if attr=="srcset" else [raw]:
                v=urljoin(base,frag.strip().split()[0])
                if preview_url(v) and v not in urls:urls.append(v)
    return urls

def html_doc(url,valid):
    if not valid(url):raise ValueError("Non-public promotional source")
    r=S.get(url,timeout=TIMEOUT,allow_redirects=False)
    r.raise_for_status()
    if r.status_code!=200 or not valid(r.url):raise ValueError("Non-public redirected page")
    if len(r.content)>4_000_000:raise ValueError("Oversized public HTML")
    return r.text

def verify_image(url):
    if not preview_url(url):return None
    try:
        with S.get(url,timeout=TIMEOUT,stream=True,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200 or not preview_url(r.url):return None
            data=bytearray()
            for part in r.iter_content(65536):
                data.extend(part)
                if len(data)>20_000_000:return None
        if len(data)<4500:return None
        with Image.open(BytesIO(data)) as pic:pic.verify()
        with Image.open(BytesIO(data)) as pic:
            w,h=pic.size;fmt=pic.format
        if min(w,h)<300 or fmt not in ("JPEG","PNG","WEBP","AVIF"):return None
        return {"url":url,"width":w,"height":h,"bytes":len(data),
                "sha256":hashlib.sha256(data).hexdigest(),
                "source_kind":"public_publisher_promo","saved_to_private_cloud":False}
    except (requests.RequestException,OSError,ValueError) as e:
        print("MIMMI_PUBLIC_GUMROAD_PROMO_UNAVAILABLE",type(e).__name__,flush=True)
        return None

def scan(max_books=70,max_per_album=5):
    catalog=json.loads((ROOT/"official-previews.json").read_text(encoding="utf-8"))
    previous={}
    outfile=ROOT/"gumroad-public-previews.json"
    if outfile.exists():
        try:
            old=json.loads(outfile.read_text(encoding="utf-8"))
            previous={a["id"]:a for a in old["albums"]}
        except (ValueError,TypeError,KeyError):pass
    results=[]
    for i,album in enumerate(catalog["albums"][:max_books],1):
        doc_url=album["source"]
        if not (doc_url.startswith("https://djawaphoto.com/portfolio/") or doc_url.startswith("https://www.djawaphoto.com/portfolio/")):continue
        urls=[];samples=[];errors=[];links=[]
        try:
            body=html_doc(doc_url,lambda u:urlsplit(u).scheme=="https" and urlsplit(u).hostname in ("djawaphoto.com","www.djawaphoto.com") and urlsplit(u).path.startswith("/portfolio/"))
            links=from_portfolio(body,doc_url)
            for product in links[:3]:
                try:
                    page=html_doc(product,product_url)
                    for url in promo_candidates(page,product):
                        if url not in urls:urls.append(url)
                except (requests.RequestException,ValueError) as exc:
                    errors.append(type(exc).__name__)
        except (requests.RequestException,ValueError) as exc:
            errors.append(type(exc).__name__)
        for u in urls[:max_per_album*4]:
            if len(samples)>=max_per_album:break
            image=verify_image(u)
            if image and image["sha256"] not in {p["sha256"] for p in samples}:samples.append(image)
        fresh_count=len(samples)
        seen={p["sha256"] for p in samples}
        # Preserve prior verified public media evidence across product page outages.
        for old in previous.get(album["id"],{}).get("samples",[]):
            if len(samples)>=max_per_album:break
            if old.get("sha256") in seen or not preview_url(old.get("url")):continue
            if (not re.fullmatch(r"[a-f0-9]{64}",old.get("sha256","")) or
                type(old.get("bytes")) is not int or old["bytes"]<4500 or
                type(old.get("width")) is not int or type(old.get("height")) is not int or
                min(old["width"],old["height"])<300):continue
            p=dict(old);p["carried_from_previous_verification"]=True;samples.append(p);seen.add(p["sha256"])
        results.append({"id":album["id"],"title":album["title"],"publisher":"DJAWA",
                        "source":album["source"],"product_urls":links,
                        "samples":samples,"images":[],"fresh_http_verified":fresh_count,
                        "errors":errors,"status":"verified_public_promo_only" if samples else "no_public_promo_photo"})
        print("MIMMI_PUBLIC_GUMROAD",i,len(results),album["id"],len(samples),flush=True)
        time.sleep(.3)
    known={r["id"] for r in results}
    results.extend(a for a in previous.values() if a["id"] not in known and a.get("samples"))
    payload={"schema_version":1,"model":"mimmi","generated_at":datetime.now(timezone.utc).isoformat(),
             "source":"only public DJAWA-linked Gumroad promo HTML, never paid files",
             "summary":{"albums_checked":len(results),"promotional_image_urls_verified":sum(len(a["samples"]) for a in results),
                        "fresh_promotional_urls_verified":sum(a.get("fresh_http_verified",0) for a in results),
                        "private_cloud_saved":0},"albums":results}
    outfile.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_PUBLIC_GUMROAD_SUMMARY",json.dumps(payload["summary"]),flush=True)
    return payload

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--books",type=int,default=70)
    p.add_argument("--images",type=int,default=5)
    args=p.parse_args()
    if not 1<=args.books<=100 or not 1<=args.images<=12:p.error("bounded public promotion scan")
    scan(args.books,args.images)
