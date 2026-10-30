#!/usr/bin/env python3
"""Collect individually SHA-verified, public, on-page Mimmi PixiBB images.

Traverses ordinary WordPress pagination, only site-rendered img/lazy/srcset
attributes, with no archive-download endpoints, payment, login or protected
credentials. Image bytes are NEVER put into publicly deployed repository files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent
HOST = "cosplay.pixibb.com"
SOURCE = [
    {"id":"pixibb-nikke-alice","title":"Nikke : Alice",
     "source":"https://cosplay.pixibb.com/djawa-photo-mimmi-nikke-alice-s-ver-170-photos-cosplay/","advertised_photos":170,
     "pages":18},
    {"id":"pixibb-your-fishe-gawr-gura","title":"Your Fishe (Gawr Gura)",
     "source":"https://cosplay.pixibb.com/djawa-photo-mimmi-your-fishe-gawr-gura-123-photos-cosplay/","advertised_photos":123,
     "pages":13},
    {"id":"pixibb-rudy-midnight","title":"Rudy : The Wolf of Midnight",
     "source":"https://cosplay.pixibb.com/djawa-photo-mimmi-rudy-the-wolf-of-midnight-230-photos-cosplay/","advertised_photos":230,
     "pages":24},
    {"id":"pixibb-rudy-codename","title":"Rudy² – Codename : Wolfgirl",
     "source":"https://cosplay.pixibb.com/djawa-photo-mimmi-rudy-codename-wolfgirl-201-photos-cosplay/","advertised_photos":201,
     "pages":21},
]
DISCOVERED_TITLES={
    "nikke-elegg":"Nikke : Elegg",
    "christmas-special-2021":"Christmas Special 2021 : Mimmi",
    "girls-frontline-hk416":"Girls' Frontline HK416",
    "azur-lane-ijn-atago":"Mimmi - Azur Lane IJN Atago & Takao",
    "witchs-witchcraft":"Witch's Witchcraft",
    "cyberpunk-girl":"Cyberpunk Girl",
    "kitsune-miko-a-ver":"Kitsune Miko (A ver)",
}

def all_sources():
    """Combine trusted seeded albums and identity-checked public search findings."""
    rows=list(SOURCE);have={x["source"].rstrip("/") for x in rows}
    path=ROOT/"pixibb-discovered-seeds.json"
    if not path.is_file():return rows
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("model")!="mimmi":raise ValueError("Wrong-model source index")
    from discover_pixibb_search import allowed_article
    for item in data.get("albums",[])[:100]:
        url=item.get("source","")
        if not allowed_article(url) or url.rstrip("/") in have:continue
        name=item.get("title","")
        if not re.search(r"Mimmi|밈미|밈미",name,re.I):continue
        slug=urlsplit(url).path.strip("/")
        if not re.fullmatch(r"[a-z0-9-]{8,200}",slug):continue
        subject=next((t for k,t in DISCOVERED_TITLES.items() if k in slug),name)
        claimed=item.get("advertised_photos")
        if type(claimed) is not int or claimed<1:
            m=re.search(r"(\d{2,4})[ -]photos?",name+" "+slug,re.I)
            claimed=int(m.group(1)) if m else None
        pages=min(35,max(item.get("pages",12),(claimed+9)//10+2 if claimed else 12))
        rows.append({"id":"pixibb-auto-"+slug[:80],"title":subject,
                     "source":url,"pages":pages,"advertised_photos":claimed})
        have.add(url.rstrip("/"))
    return rows

T=(9,28)
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PersonalMimmiPublicAlbumPreview/1.0)",
    "Accept":"text/html,image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.4"})

def safe_page(url,root=None):
    try:
        p=urlsplit(url)
        if not (p.scheme=="https" and p.hostname==HOST and not p.username and not p.password
                and not p.port and not p.query and not p.fragment):return False
        if root:
            canonical=urlsplit(root).path.rstrip("/")
            return p.path.rstrip("/")==canonical or bool(re.fullmatch(re.escape(canonical)+r"/\d{1,3}",p.path.rstrip("/")))
        return p.path.startswith("/djawa-photo-mimmi-")
    except (TypeError,ValueError):return False

def safe_photo(url):
    try:
        p=urlsplit(url)
        if (p.scheme!="https" or p.username or p.password or p.port or p.fragment):return False
        h=(p.hostname or "").lower()
        if h==HOST:allowed=p.path.startswith("/wp-content/uploads/")
        elif re.fullmatch(r"imgx\d{2,4}\.pixibb\.com|images\d{1,4}\.pixibb\.com|(?:cdn|img|files)\.pixibb\.com",h):
            allowed=True
        else:allowed=False
        return bool(allowed and re.search(r"\.(?:jpe?g|png|webp|avif)$",p.path,re.I))
    except (ValueError,TypeError):return False

def page_photos(html,base):
    doc=BeautifulSoup(html,"html.parser")
    # Reject unrelated pages/redirects: page must identify the original
    # photographer set and cosplayer, not the website's global recommendations.
    title=(doc.title.get_text(" ",strip=True) if doc.title else "")
    header=doc.find("h1")
    heading=(header.get_text(" ",strip=True) if header else "")
    if not re.search(r"Mimmi|밈미|밈미",title+" "+heading,re.I):
        return [],False
    root=doc.select_one("article") or doc.select_one("main") or doc
    ordered=[]
    for tag in root.select("img,source,a[href]"):
        # A lightbox can wrap a thumbnail; prioritize the linked public image.
        values=[]
        if tag.name=="a":
            val=tag.get("href","")
            if val:values.append(val)
        else:
            for attr in ("data-original","data-full","data-src","data-lazy-src","data-large-file","srcset","data-srcset","src"):
                val=tag.get(attr,"")
                if val:
                    if "srcset" in attr:values.extend(s.strip().split()[0] for s in val.split(",") if s.strip())
                    else:values.append(val)
        for raw in values:
            url=urljoin(base,raw.strip())
            if not safe_photo(url):continue
            # WordPress and page chrome have generic avatars, emoji and logos;
            # prefer photos with album keywords in alt/path.
            label=(tag.get("alt","")+" "+urlsplit(url).path).lower()
            if re.search(r"avatar|logo|favicon|emoji|wp-smiley|comment|banner|tracking|placeholder|advert",label):continue
            if url not in ordered:ordered.append(url)
    return ordered,True

def public_image(url):
    if not safe_photo(url):return None
    try:
        with SESSION.get(url,timeout=T,stream=True,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200 or not safe_photo(r.url):return None
            raw=bytearray()
            for piece in r.iter_content(65536):
                raw.extend(piece)
                if len(raw)>30_000_000:return None
        if len(raw)<4500:return None
        with Image.open(BytesIO(raw)) as im:im.verify()
        with Image.open(BytesIO(raw)) as im:
            w,h=im.size
            typ=im.format
        if min(w,h)<300 or typ not in ("JPEG","PNG","WEBP","AVIF"):return None
        return {"url":url,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
            "width":w,"height":h,"quality":"public_watermarked_web_preview",
            "publisher_original_verified":False,"private_cloud_file":False}
    except (requests.RequestException,OSError,ValueError) as exc:
        print("MIMMI_PIXIBB_IMAGE_UNAVAILABLE",type(exc).__name__,flush=True)
        return None

def verified_history(rows,limit):
    seen=set();out=[]
    for p in rows:
        h=p.get("sha256","");url=p.get("url","")
        if (not re.fullmatch(r"[0-9a-f]{64}",h) or not safe_photo(url)
            or type(p.get("bytes")) is not int or p["bytes"]<4500
            or type(p.get("width")) is not int or type(p.get("height")) is not int
            or min(p["width"],p["height"])<300 or h in seen):continue
        seen.add(h);out.append(dict(p))
        if len(out)>=limit:break
    return out

def cached_verified_photo(url, prior, day=None, rotation=20):
    """Reuse previous genuine SHA checks; rotate 1/20 of known URLs daily.

    A cached record is explicitly tagged historical and NEVER counted as
    freshly verified or physically downloaded. Actual backfill independently
    downloads and checks exact bytes before owner-private storage.
    """
    if prior is None or prior.get("url") != url:
        return None
    valid = verified_history([prior], 1)
    if not valid:
        return None
    today = day or datetime.now(timezone.utc).date().isoformat()
    slot = int(hashlib.sha256((url + "|" + today).encode()).hexdigest()[:8], 16)
    if rotation < 1 or slot % rotation == 0:
        return None
    output = dict(valid[0])
    output["carried_from_previous_verification"] = True
    return output


def collect(max_pages=25,max_photos=250,delay=.25,browser_scroll=False):
    previous={}
    manifest=ROOT/"pixibb-public-previews.json"
    if manifest.exists():
        try:
            old=json.loads(manifest.read_text(encoding="utf-8"))
            previous={a["id"]:a.get("samples",[]) for a in old.get("albums",[])}
        except (ValueError,KeyError,TypeError):pass
    results=[]
    for album in all_sources():
        seen_urls=set();sha=set();photos=[];pages=[];browser_attempts=0
        by_url={p["url"]:p for p in verified_history(previous.get(album["id"],[]), max_photos)
                if isinstance(p.get("url"),str)}
        actual_new_checks=0;reused_checks=0
        limit=min(max_pages,album["pages"])
        for n in range(1,limit+1):
            url=album["source"] if n==1 else album["source"]+str(n)+"/"
            try:
                r=SESSION.get(url,timeout=T,allow_redirects=False)
                r.raise_for_status()
                if r.status_code!=200 or not safe_page(r.url,album["source"]):
                    pages.append({"page":n,"status":"nonpublic_or_redirect"});break
                urls,matched=page_photos(r.text,url)
                if matched and browser_scroll and browser_attempts<2 and (n==1 or len(urls)<6):
                    browser_attempts+=1
                    try:
                        from reveal_lazy_images import reveal
                        extra=reveal(url,album["source"],max_scrolls=28)
                        for v in extra:
                            if v not in urls:urls.append(v)
                        print("MIMMI_PIXIBB_SCROLL_REVEALED",album["id"],n,len(extra),len(urls),flush=True)
                    except Exception as error:
                        print("MIMMI_PIXIBB_BROWSER_SCROLL_UNAVAILABLE",album["id"],n,type(error).__name__,flush=True)
                if not matched:
                    pages.append({"page":n,"status":"not_mimmi_page"});break
                new=[u for u in urls if u not in seen_urls]
                seen_urls.update(new)
                page_verified=0;page_cached=0
                for image_url in new:
                    if len(photos)>=max_photos:break
                    result=cached_verified_photo(image_url,by_url.get(image_url))
                    if result is None:
                        result=public_image(image_url)
                        if result:
                            page_verified+=1;actual_new_checks+=1
                        time.sleep(delay)
                    else:
                        page_cached+=1;reused_checks+=1
                    if result and result["sha256"] not in sha:
                        sha.add(result["sha256"]);result["number"]=len(photos)+1
                        photos.append(result)
                pages.append({"page":n,"url":url,"candidates":len(new),
                              "sha_verified":page_verified,"cached_from_previous_sha_checks":page_cached})
                print("MIMMI_PIXIBB_PAGE",album["id"],n,len(new),page_verified,len(photos),flush=True)
                if len(photos)>=max_photos:break
                time.sleep(delay)
            except requests.RequestException as exc:
                pages.append({"page":n,"status":type(exc).__name__})
                print("MIMMI_PIXIBB_PAGE_UNAVAILABLE",album["id"],n,type(exc).__name__,flush=True)
                break
        fresh=actual_new_checks
        for old in verified_history(previous.get(album["id"],[]),max_photos):
            if len(photos)>=max_photos:break
            if old["sha256"] not in sha:
                old["carried_from_previous_verification"]=True
                photos.append(old);sha.add(old["sha256"])
        for i,photo in enumerate(photos,1):photo["number"]=i
        results.append({**album,"samples":photos,"images":[],"visited_pages":pages,
                        "fresh_http_verified":fresh,"reused_previous_sha_checks":reused_checks,
                        "status":"verified_public_web_previews" if photos else "no_public_images_verified"})
    data={"schema_version":1,"model":"mimmi","source":"public visible multi-page PixiBB web previews only",
          "generated_at":datetime.now(timezone.utc).isoformat(),
          "summary":{"works":len(results),"images_verified":sum(len(a["samples"]) for a in results),
                     "fresh_verified":sum(a["fresh_http_verified"] for a in results),
                     "cached_previous_sha_checks":sum(a["reused_previous_sha_checks"] for a in results),
                     "private_cloud_archived":0},
          "albums":results}
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_PIXIBB_SUMMARY",json.dumps(data["summary"]),flush=True)
    return data

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--pages",type=int,default=25)
    p.add_argument("--images",type=int,default=250)
    p.add_argument("--scroll",action="store_true",help="Scroll normal public album HTML")
    args=p.parse_args()
    if not 1<=args.pages<=35 or not 1<=args.images<=400:p.error("bounded public preview collection")
    collect(args.pages,args.images,browser_scroll=args.scroll)
