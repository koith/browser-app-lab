#!/usr/bin/env python3
"""Archive normally visible original creator posts from Teapawt public HTML.

Avoids X/Instagram authentication failures without a proxy or protected API.
Only public <div class="timeline-item" data-username=EXACT_OWNER> cards and
image links in those cards qualify. Retweets, quoted posts and unrelated
photographers are rejected. Pagination is followed only from visible "Load
more" anchors carrying a cursor; no guessed page offsets or endpoints.
"""
from __future__ import annotations
import collections
import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image

HOST="teapawt.net"
IMAGE_HOST="pbs.twimg.com"
MAX_PHOTO_BYTES=35 * 1024 * 1024
EXT={"JPEG":"jpg","PNG":"png","WEBP":"webp"}

def validate_source(source):
    url=urlsplit(source["url"])
    assert (source.get("kind")=="teapawt" and url.scheme=="https" and
        url.hostname==HOST and url.port is None and
        url.path=="/"+source["account"] and not url.query and not url.fragment)
    assert re.fullmatch(r"[A-Za-z0-9_]{3,30}",source["account"])

def safe_media_url(raw,base):
    u=urljoin(base,raw.strip())
    p=urlsplit(u)
    if (p.scheme!="https" or p.hostname!=IMAGE_HOST or not p.path.startswith("/media/")
        or p.port or p.username or p.password or p.fragment):
        return None
    if not re.fullmatch(r"/media/[A-Za-z0-9_-]{6,140}(?:\.(?:jpe?g|png|webp))?",p.path,re.I):
        return None
    return u

def public_images_from_author(html,source,current):
    soup=BeautifulSoup(html,"html.parser")
    found={}
    target=source["account"].casefold()
    cards=0
    for card in soup.select(".timeline-item[data-username]"):
        if card.get("data-username","").casefold()!=target:
            continue
        cards+=1
        for element in card.select("img,source,a[href]"):
            # An author card can quote another person or an event poster.
            # Those attachments are not the author's own photo attachments.
            if element.find_parent(class_=re.compile(r'^(?:quote|quoted-tweet|retweet-header)$')):continue
            nearest=element.find_parent(class_='timeline-item')
            if nearest is not card:continue
            for field in (("href",) if element.name=="a" else
                          ("data-original","data-src","data-lazy-src","src","srcset","data-srcset")):
                val=element.get(field)
                if not val:continue
                for bit in val.split(",") if "srcset" in field else [val]:
                    u=safe_media_url(bit.strip().split()[0],current)
                    if u:
                        p=urlsplit(u)
                        # One public source image per canonical media ID; CDN
                        # format/resolution variants are not distinct photos.
                        key=p.path
                        rank=lambda value:{'orig':3,'large':2,'medium':1}.get(dict(parse_qsl(urlsplit(value).query)).get('name'),0)
                        if key not in found or rank(u)>rank(found[key]):found[key]=u
    next_page=None
    for a in soup.select("a[href]"):
        label=a.get_text(" ",strip=True).casefold()
        if not ("load more" in label or label in ("older","next","more")):
            continue
        u=urljoin(current,a.get("href",""))
        p=urlsplit(u)
        allowed=(p.scheme=="https" and p.hostname==HOST and p.path=="/"+source["account"]
                 and not p.username and not p.password and not p.fragment and p.port is None)
        if allowed and "cursor" in dict(parse_qsl(p.query)):
            next_page=u
            break
    return list(found.values()),next_page,cards

def public_original_variant(url):
    p=urlsplit(url)
    if p.hostname!=IMAGE_HOST:return [url]
    query=dict(parse_qsl(p.query))
    fmt=query.get("format")
    if not fmt:
        m=re.search(r"\.(jpe?g|png|webp)$",p.path,re.I)
        fmt=m.group(1) if m else None
    if fmt and fmt.lower() in ("jpg","jpeg","png","webp"):
        proposed=urlunsplit((p.scheme,p.netloc,p.path,urlencode({"format":fmt,"name":"orig"}),""))
        return list(dict.fromkeys([proposed,url]))
    return [url]

def download_one(url,source):
    errors=[]
    for variant in public_original_variant(url):
        if not safe_media_url(variant,source["url"]):continue
        try:
            with requests.get(variant,timeout=(8,24),stream=True,allow_redirects=False,headers={
                "User-Agent":"Mozilla/5.0 (compatible; PersonalPublicPhotoArchive/1.0)",
                "Accept":"image/jpeg,image/png,image/webp,image/*"}) as response:
                if response.status_code!=200:
                    raise ValueError("HTTP_"+str(response.status_code))
                if urlsplit(response.url).hostname!=IMAGE_HOST:
                    raise ValueError("Unexpected media redirect host")
                data=bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data)>MAX_PHOTO_BYTES:
                        raise ValueError("Oversized public photograph")
            if len(data)<3500:raise ValueError("Image too small")
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                ext=EXT.get(img.format)
                if not ext or min(img.size)<320:raise ValueError("Invalid photo dimensions/format")
                width,height=img.size
            digest=hashlib.sha256(data).hexdigest()
            return {"bytes":bytes(data),"sha256":digest,"width":width,
                    "height":height,"extension":ext},None
        except (requests.RequestException,OSError,ValueError) as err:
            errors.append(str(err)[:60] if isinstance(err,ValueError) else type(err).__name__)
    return None,errors[-1] if errors else "unsupported_media"


def get_public_page_with_retry(client, url, headers, attempts=3):
    """Only retry transient transport/5xx errors, never access denial."""
    if attempts < 1 or attempts > 4:
        raise ValueError("Unbounded retry budget")
    for attempt in range(attempts):
        try:
            response = client.get(url, timeout=(8, 32), headers=headers,
                                  allow_redirects=False)
            if response.status_code in (502, 503, 504) and attempt + 1 < attempts:
                time.sleep(min(2 * (attempt + 1), 6))
                continue
            return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt + 1 == attempts:
                raise
            time.sleep(min(2 * (attempt + 1), 6))
    raise ValueError("Unexpected public page retry exit")


def capture(source,folder,max_pages=40,max_photos=650,workers=3,client=None,fetch=download_one):
    validate_source(source)
    client=client or requests.Session()
    headers={"User-Agent":"Mozilla/5.0 (compatible; PersonalPublicPhotoArchive/1.0)",
             "Accept":"text/html,application/xhtml+xml"}
    page=source["url"]
    visited=set()
    photo_urls={}
    errors=[]
    articles=0
    while page and page not in visited and len(visited)<max_pages:
        visited.add(page)
        try:
            response=get_public_page_with_retry(client,page,headers)
            if (response.status_code!=200 or urlsplit(response.url).hostname!=HOST
                or "html" not in response.headers.get("Content-Type","").lower()
                or len(response.content)>3_000_000):
                raise ValueError("Public feed unavailable, not HTML or oversized")
            urls,next_page,cards=public_images_from_author(response.text,source,page)
            articles+=cards
            for u in urls:
                if len(photo_urls)>=max_photos:break
                photo_urls.setdefault(urlsplit(u).path,u)
            print("PUBLIC_AUTHOR_MEDIA_PAGE",source["id"],len(visited),
                  "author_posts",cards,"media_candidates",len(photo_urls),flush=True)
            if len(photo_urls)>=max_photos:break
            page=next_page
            time.sleep(.4)
        except (requests.RequestException,ValueError) as exc:
            errors.append(type(exc).__name__)
            break
    folder.mkdir(parents=True,exist_ok=True)
    success=0
    failed=0
    failure_causes=collections.Counter()
    hashes=set()
    with ThreadPoolExecutor(max_workers=max(1,min(workers,4))) as pool:
        futures=[pool.submit(fetch,url,source) for url in photo_urls.values()]
        for future in as_completed(futures):
            result,error=future.result()
            if result is None:
                failed+=1
                failure_causes[str(error or "unknown")[:60]]+=1
                continue
            sha=result["sha256"]
            if sha in hashes:continue
            hashes.add(sha)
            filename=folder/(sha+"."+result["extension"])
            filename.write_bytes(result["bytes"])
            filename.with_suffix(".json").write_text(
                json.dumps({"author":{"screen_name":source["account"]}},
                            ensure_ascii=False),encoding="utf-8")
            success+=1
    report={"source":source["id"],"source_pages":len(visited),
            "owner_authored_posts":articles,"distinct_public_media_urls":len(photo_urls),
            "physical_decoded_files":success,"failed_media":failed,
            "media_failure_types":dict(failure_causes.most_common()),
            "page_error_types":errors,
            "site_media_links_are_not_saved_images":True}
    print("PUBLIC_CREATOR_MIRROR_PHYSICAL_BYTES",json.dumps(report),flush=True)
    return report
