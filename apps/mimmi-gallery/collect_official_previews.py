#!/usr/bin/env python3
"""Discover Mimmi's official DJAWA photo books and live public promo samples.

No login/paywall access and NO redistribution of copyrighted photo bytes:
only official externally hosted preview URLs + verified HTTP response metadata
are published. Source originals must be legitimately purchased and kept private.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

ROOT=Path(__file__).resolve().parent
CATEGORY="https://djawaphoto.com/portfolio-cat/mimmi/"
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PersonalPhotoCatalogue/1.0; +https://github.com/koith/browser-app-lab)", "Accept":"text/html,application/xhtml+xml,image/avif,image/webp,image/*;q=.8,*/*;q=.5"})
TIMEOUT=(10,24)
def valid_official(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and p.hostname in {"djawaphoto.com","www.djawaphoto.com"} and not p.username and not p.password
    except Exception:return False

def fetch_html(url):
    if not valid_official(url):raise ValueError("Nonofficial website blocked")
    r=SESSION.get(url,timeout=TIMEOUT,allow_redirects=True)
    r.raise_for_status()
    if not valid_official(r.url):raise ValueError("Unapproved redirect")
    if len(r.content)>3_000_000:raise ValueError("Oversized HTML response")
    return BeautifulSoup(r.content,"html.parser")

def norm(text):
    return re.sub(r"[^a-z0-9]+","-",text.lower()).strip("-")[:90]

def archive(page_limit=5):
    found={}
    pages=[]
    for page in range(1,page_limit+1):
        url=CATEGORY if page==1 else urljoin(CATEGORY,f"page/{page}/")
        try:doc=fetch_html(url)
        except Exception as exc:
            print("ARCHIVE_PAGE_ERROR",url,type(exc).__name__,str(exc)[:170],flush=True)
            break
        links={}
        # The official WordPress portfolio category contains links to /portfolio/{slug}/.
        for anchor in doc.select('a[href*="/portfolio/"]'):
            href=urljoin(url,anchor.get("href",""))
            p=urlsplit(href)
            if not valid_official(href) or not re.fullmatch(r"/portfolio/[^/]+/?",p.path):
                continue
            parent=anchor.find_parent(["article","li","div"])
            title=(anchor.get("title") or anchor.get_text(" ",strip=True)
                   or (parent.find(["h2","h3","h4"]).get_text(" ",strip=True) if parent and parent.find(["h2","h3","h4"]) else "")
                   or (anchor.find("img").get("alt","") if anchor.find("img") else ""))
            title=re.sub(r"\s+"," ",title).strip()
            # Ignore invisible duplicate anchors until a descriptive title is found.
            existing=links.get(href)
            if not existing or len(title)>len(existing):links[href]=title
        for href,title in links.items():
            slug=urlsplit(href).path.rstrip("/").rsplit("/",1)[-1]
            found.setdefault(slug,{"id":"djawa-"+slug,"title":title or slug.replace("-"," ").title(),
                                   "publisher":"DJAWA","source":href,"model":"mimmi"})
        pages.append({"url":url,"links":len(links)})
        print("OFFICIAL_PORTFOLIO_PAGE",page,len(links),"unique",len(found),flush=True)
        if not links or (page>1 and len(links)<7):break
        time.sleep(.35)
    return list(found.values()),pages

def count_photo_text(text):
    # DJAWA writes e.g. 'total 75 extremely-high resolution (5000 × 5000) photos'.
    patterns=[
        r"total\s+(\d{1,4})\s+(?:extremely[- ]high resolution\s+)?(?:\([^)]*\)\s+)?photos",
        r"(?:total|contains|consists of)\s+(\d{1,4})\s+(?:high[- ]resolution\s+)?(?:\([^)]*\)\s+)?photos",
        r"(\d{1,4})\s+(?:high[- ]resolution\s+)?(?:\([^)]*\)\s+)?(?:photos|pics|pictures)",
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I)
        if m and 1<=int(m.group(1))<=1000:return int(m.group(1))
    return None

def image_candidates(doc,origin):
    found=[]
    for item in doc.select("a[href], img, source"):
        attrs=["href"] if item.name=="a" else ["data-full","data-src","data-original","data-lazy-src","src","srcset","data-srcset"]
        for attr in attrs:
            raw=item.get(attr,"")
            if not raw:continue
            values=raw.split(",") if "srcset" in attr else [raw]
            for value in values:
                value=value.strip().split(" ")[0]
                url=urljoin(origin,value)
                parsed=urlsplit(url)
                if not valid_official(url):continue
                if not re.search(r"\.(?:jpe?g|png|webp|avif)(?:$|[?#])",url,re.I):continue
                # A WordPress -WxH derivative is the same photo at lower quality,
                # not an additional image. Keep only source-sized image filenames.
                if re.search(r"-\d{2,4}x\d{2,4}\.(?:jpe?g|png|webp|avif)$",parsed.path,re.I):continue
                if re.search(r"avatar|logo|favicon|icon|spacer|pixel|emoji|banner|woff",url,re.I):continue
                path=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,parsed.query,""))
                if path not in found:found.append(path)
    # Links to full sample pages are preferred over WordPress '-300x200' thumbnails.
    return sorted(found,key=lambda u:(0 if re.search(r"sample|preview|cover|cv",u,re.I) else 1,
                                     1 if re.search(r"-\d{2,4}x\d{2,4}\.",u) else 0))

def probe_image(url):
    try:
        r=SESSION.get(url,timeout=TIMEOUT,stream=True)
        r.raise_for_status()
        if not valid_official(r.url):return None
        raw=bytearray()
        for chunk in r.iter_content(chunk_size=65536):
            raw.extend(chunk)
            if len(raw)>9_000_000:return None
        if len(raw)<4500:return None
        with Image.open(BytesIO(raw)) as im:
            im.verify()
        with Image.open(BytesIO(raw)) as im:
            width,height=im.size
            if min(width,height)<250:return None
        return {"url":url,"width":width,"height":height,"bytes":len(raw),
                "sha256":hashlib.sha256(raw).hexdigest(),"hosting":"official_publisher",
                "saved_to_private_cloud":False}
    except (requests.RequestException,OSError,ValueError) as exc:
        print("OFFICIAL_SAMPLE_SKIPPED",type(exc).__name__,url[:130],flush=True)
        return None

def reconcile_public_samples(fresh, historical, limit):
    """Keep earlier SHA evidence across temporary source outages."""
    out=[];seen=set()
    now={x.get("sha256") for x in fresh}
    for p in [*fresh,*historical]:
        h=p.get("sha256","");url=p.get("url","")
        if (not re.fullmatch("[0-9a-f]{64}",h) or not valid_official(url)
            or not urlsplit(url).path.startswith("/wp-content/uploads/")
            or type(p.get("bytes")) is not int or p["bytes"]<4500
            or type(p.get("width")) is not int or type(p.get("height")) is not int
            or min(p["width"],p["height"])<250 or h in seen):continue
        row=dict(p);seen.add(h)
        if h not in now:row["carried_from_previous_verification"]=True
        else:row.pop("carried_from_previous_verification",None)
        out.append(row)
        if len(out)>=limit:break
    return out

def collect(max_pages=8,max_books=100,max_samples=25):
    books,pages=archive(max_pages)
    books=books[:max_books]
    previous={}
    prior_file=ROOT/"official-previews.json"
    if prior_file.is_file():
        try:
            old=json.loads(prior_file.read_text(encoding="utf-8"))
            previous={x["id"]:x for x in old.get("albums",[]) if x.get("id")}
        except (ValueError,TypeError,KeyError):
            print("MIMMI_OFFICIAL_PRIOR_MANIFEST_UNAVAILABLE",flush=True)
    for i,book in enumerate(books,1):
        try:
            doc=fetch_html(book["source"])
            description=doc.get_text(" ",strip=True)
            heading=doc.find(["h1","h2"])
            if heading and heading.get_text(" ",strip=True):book["title"]=heading.get_text(" ",strip=True)[:160]
            book["advertised_photos"]=count_photo_text(description)
            candidates=image_candidates(doc,book["source"])
            book["samples"]=[]
            for url in candidates[:max_samples*4]:
                if len(book["samples"])>=max_samples:break
                result=probe_image(url)
                if result and result["sha256"] not in {p["sha256"] for p in book["samples"]}:
                    book["samples"].append(result)
            book["fresh_http_verified"]=len(book["samples"])
            book["samples"]=reconcile_public_samples(book["samples"],previous.get(book["id"],{}).get("samples",[]),max_samples)
            book["status"]="official_samples_verified" if book["samples"] else "official_source_verified_no_samples"
            book["sample_count_verified"]=len(book["samples"])
            book["images"]=[] # no user-owned archived files yet
            book["collected_image_files"]=0
        except Exception as exc:
            retained=reconcile_public_samples([],previous.get(book["id"],{}).get("samples",[]),max_samples)
            book.update(status="official_page_failed_previous_evidence_kept" if retained else "official_page_failed",
                        samples=retained,images=[],sample_count_verified=len(retained),
                        collected_image_files=0,error=type(exc).__name__+": "+str(exc)[:160])
        print("OFFICIAL_BOOK",i,len(books),book["id"],book["status"],book["sample_count_verified"],"of",book.get("advertised_photos"),flush=True)
        time.sleep(.25)
    known={b["id"] for b in books}
    for old in previous.values():
        if old["id"] not in known:
            retained=dict(old)
            retained["samples"]=reconcile_public_samples([],retained.get("samples",[]),max_samples)
            retained["status"]="previously_verified_source_unavailable"
            if retained["samples"]:books.append(retained)
    return {"model":{"id":"mimmi","name":"밈미","english":"Mimmi","aliases":["Miss u","밋슈"],"instagram":"mimmissu17"},
            "version":"v0.1.0-mimmi.2","generated_at":datetime.now(timezone.utc).isoformat(),
            "primary_source":CATEGORY,"archive_pages":pages,
            "albums":books,
            "summary":{"official_works_discovered":len(books),"official_sample_urls_verified":sum(len(b["samples"]) for b in books),
                       "individually_archived_photographs":0,
                       "official_pages_failed":sum(b["status"]=="official_page_failed" for b in books)},
            "rights":"Official public promos linked from publisher; no copying paid sets to open hosting. Source sample URLs may change."}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--pages",type=int,default=5)
    ap.add_argument("--books",type=int,default=80)
    ap.add_argument("--samples",type=int,default=16)
    ap.add_argument("--output",type=Path,default=ROOT/"official-previews.json")
    args=ap.parse_args()
    if not 1<=args.pages<=10 or not 1<=args.books<=100 or not 1<=args.samples<=40:ap.error("Out of range")
    result=collect(args.pages,args.books,args.samples)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_OFFICIAL_DISCOVERY",json.dumps(result["summary"],ensure_ascii=False),flush=True)
