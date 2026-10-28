#!/usr/bin/env python3
"""Verified Mimmi official X public-media images from Twoucan's public profile.

Never rely on unrelated hashtags or broad face similarity. The profile must
identify @Mimmi_official and mimmissu17. Only pbs.twimg.com/media images linked
in its public HTML are accepted. No authenticated API, cookies or paid access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit,urljoin,urlunsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parent
PROFILE="https://twoucan.com/profile/Mimmi_official"
T=(10,28)
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PublicMimmiOfficialSocialArchive/1.0)",
                        "Accept":"text/html,image/jpeg,image/png,image/webp,image/*;q=.8"})

def social_page(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and p.hostname=="twoucan.com" and p.path.startswith("/profile/Mimmi_official") and not p.username and not p.password
    except (ValueError,TypeError):return False

def public_image(url):
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.hostname=="pbs.twimg.com"
            and p.path.startswith("/media/") and not p.username and not p.password and not p.port
            and bool(re.search(r"\.(?:jpe?g|png|webp)$",p.path,re.I))
            and not p.fragment)
    except (TypeError,ValueError):return False

def photos_in_profile(html,base):
    soup=BeautifulSoup(html,"html.parser")
    identity=soup.get_text(" ",strip=True)[:4000]
    if not re.search(r"@?Mimmi_official",identity,re.I) or "mimmissu17" not in identity.lower():
        return [],False
    values=[]
    for tag in soup.select("a[href],img[src],img[data-src],img[data-original],source[srcset]"):
        attrs=("href",) if tag.name=="a" else ("data-original","data-src","src","srcset")
        for key in attrs:
            raw=tag.get(key,"")
            for bit in raw.split(",") if key=="srcset" else [raw]:
                val=bit.strip().split()[0] if bit.strip() else ""
                url=urljoin(base,val)
                if public_image(url) and url not in values:values.append(url)
    return values,True

def image_evidence(url):
    if not public_image(url):return None
    try:
        with SESSION.get(url,timeout=T,stream=True,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200 or not public_image(r.url):return None
            raw=bytearray()
            for part in r.iter_content(65536):
                raw.extend(part)
                if len(raw)>15_000_000:return None
        if len(raw)<4500:return None
        with Image.open(BytesIO(raw)) as im:im.verify()
        with Image.open(BytesIO(raw)) as im:
            w,h=im.size
            typ=im.format
        if min(w,h)<280 or typ not in ("JPEG","PNG","WEBP"):return None
        return {"url":url,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                "width":w,"height":h,"origin":"public_verified_mimmi_official_social",
                "publisher_original_verified":False,"private_cloud_file":False}
    except (requests.RequestException,ValueError,OSError) as err:
        print("MIMMI_SOCIAL_IMAGE_UNAVAILABLE",type(err).__name__,flush=True)
        return None

def collect(max_pages=3,max_images=130):
    file=ROOT/"social-public-previews.json"
    historical=[]
    if file.exists():
        try:historical=json.loads(file.read_text(encoding="utf-8"))["albums"][0]["samples"]
        except (KeyError,ValueError,TypeError,IndexError):pass
    found=[];seen_urls=set();seen_hashes=set();pages=[]
    for n in range(1,max_pages+1):
        # Only follow profile pagination already visible in the public HTML.
        url=PROFILE if n==1 else PROFILE+"?page="+str(n)
        try:
            r=SESSION.get(url,timeout=T,allow_redirects=False)
            r.raise_for_status()
            if r.status_code!=200 or not social_page(r.url):break
            urls,verified=photos_in_profile(r.text,r.url)
            if not verified:break
            new=[x for x in urls if x not in seen_urls]
            if n>1 and not new:break
            seen_urls.update(new)
            before=len(found)
            for image in new:
                if len(found)>=max_images:break
                meta=image_evidence(image)
                if meta and meta["sha256"] not in seen_hashes:
                    meta["number"]=len(found)+1
                    found.append(meta);seen_hashes.add(meta["sha256"])
                time.sleep(.25)
            pages.append({"page":n,"public_media_links":len(new),"verified_new":len(found)-before})
            print("MIMMI_OFFICIAL_SOCIAL_PAGE",n,len(new),len(found)-before,flush=True)
            if len(found)>=max_images:break
        except requests.RequestException as err:
            pages.append({"page":n,"error":type(err).__name__})
            print("MIMMI_SOCIAL_PROFILE_ERROR",n,type(err).__name__,flush=True)
            break
    fresh=len(found)
    for p in historical:
        h=p.get("sha256","");u=p.get("url","")
        if len(found)>=max_images:break
        if (h in seen_hashes or not public_image(u) or not re.fullmatch("[a-f0-9]{64}",h)
            or type(p.get("bytes")) is not int or p["bytes"]<4500
            or type(p.get("width")) is not int or type(p.get("height")) is not int
            or min(p["width"],p["height"])<280):continue
        saved=dict(p);saved["carried_from_previous_verification"]=True
        found.append(saved);seen_hashes.add(h)
    for n,p in enumerate(found,1):p["number"]=n
    a={"id":"mimmi-official-social-public","title":"Mimmi (@Mimmi_official) · 공개 코스프레 SNS",
       "publisher":"Mimmi","source":PROFILE,"advertised_photos":None,
       "images":[],"samples":found,"pages":pages,
       "status":"verified_public_mimmi_social" if found else "no_public_social_media",
       "fresh_http_verified":fresh}
    data={"schema_version":1,"model":"mimmi","source":"Twoucan publicly indexed Mimmi_official X images",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "summary":{"official_social_images_verified":len(found),"new_http_verified":fresh,
                   "private_cloud_archived":0},"albums":[a]}
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_OFFICIAL_SOCIAL_VERIFIED",json.dumps(data["summary"]),flush=True)
    return data

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--pages",type=int,default=3)
    ap.add_argument("--images",type=int,default=130)
    args=ap.parse_args()
    if not 1<=args.pages<=8 or not 1<=args.images<=250:ap.error("bounded public social scan")
    collect(args.pages,args.images)
