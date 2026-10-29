#!/usr/bin/env python3
"""Archive only actually downloaded public individual-shoot photos, not event notices.

Public event photographer posts and historical official cosplay photo links are
strictly attributed before downloading. Never access authenticated feeds, paid
masters, or model-unrelated photobooks. Existing private photo SHA digests are
read first from the owner's TeraBox catalog. Only new full media bytes are
numbered, packed and submitted to the existing remote SHA-checking importer.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qs
from zipfile import ZIP_STORED, ZipFile

import requests
from bs4 import BeautifulSoup
from PIL import Image

FORMATS={"JPEG":"jpg","PNG":"png","WEBP":"webp"}
MAX_BYTES=35_000_000
UA="Mozilla/5.0 (compatible; PersonalPhotoArchive/1.0; publicly-visible-images-only)"
VALID_ID=re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
PUBLIC_IMG=re.compile(r"https?://[^\"'<>\\\s]+?\.(?:jpe?g|png|webp)(?:\?[^\"'<>\\\s]*)?",re.I)
INVEN_IMG=re.compile(r"^/upload/2019/11/20/bbs/[^/?]+?\.(?:jpg|jpeg|png|webp)$",re.I)

def allowed_image(url: str, source: dict) -> bool:
    try:
        p=urlsplit(url)
        domain=(p.hostname or "").lower()
        if p.scheme!="https" or domain!=source["photo_host"]:return False
        if domain=="pbs.twimg.com":
            return p.path.startswith("/media/") and bool(re.search(r"\.(?:jpg|jpeg|png|webp)$",p.path,re.I))
        if domain=="upload2.inven.co.kr":
            return bool(INVEN_IMG.fullmatch(p.path))
        return False
    except ValueError:
        return False

def origin_variant(url: str) -> list[str]:
    """Ask for the normal publicly exposed original image variant, not a paid one."""
    p=urlsplit(url)
    if p.hostname=="pbs.twimg.com":
        return [urlunsplit((p.scheme,p.netloc,p.path,"name=orig","")),url]
    if p.hostname=="upload2.inven.co.kr":
        return [urlunsplit((p.scheme,p.netloc,p.path,"","")),url]
    return [url]

def text_of(soup):
    return soup.get_text(" ",strip=True)

def source_images(source:dict, page_html: str) -> list[str]:
    """Extract only photo URLs from a verified model+photographer context."""
    mode=source["kind"]
    soup=BeautifulSoup(page_html,"html.parser")
    page_text=text_of(soup)
    if mode=="inven-article":
        if not ("밈미" in page_text and "SANA" in page_text and "M4 SOPMOD" in page_text):
            # Offline unavailability alone is not a license to misidentify
            # a new photo: direct links are manually verified Inven embeds of
            # the exact SANA/Mimmi article and never guessed paywall URLs.
            if not (page_html=="" and source.get("verified_independent_public_article")):
                return []
        found=list(source.get("direct_public_images",[]))
        for tag in soup.find_all(["img","a","source"]):
            for attr in ("src","data-src","data-original","href"):
                value=html.unescape(tag.get(attr,""))
                if value.startswith("//"):value="https:"+value
                if value.startswith("http://upload2.inven.co.kr/"):
                    value="https:"+value[len("http:"):]
                if allowed_image(value,source):found.append(value)
        for match in PUBLIC_IMG.findall(html.unescape(page_html)):
            if allowed_image(match,source):found.append(match)
        return list(dict.fromkeys(x for x in found if allowed_image(x,source)))
    if mode=="twoucan-author":
        if source["required_mention"].casefold() not in page_text.casefold():
            return []
        found=[]
        for element in soup.select("a[href],img[src],img[data-src]"):
            for attr in ("href","src","data-src"):
                value=html.unescape(element.get(attr,""))
                if allowed_image(value,source):found.append(value)
        return list(dict.fromkeys(found))
    if mode in ("teapawt-tagged","sotwe-tagged"):
        mention=source["required_mention"].casefold()
        author=source["author"].casefold()
        found=[]
        if mode=="teapawt-tagged":
            cards=soup.select(".timeline-item[data-username],article[data-username]")
        else:
            cards=soup.select("article,.tweet,.status,.tweet-container,.tweet-card")
        for card in cards:
            text=text_of(card).casefold()
            # Photographer's exact author AND the particular model's exact
            # @handle are both mandatory, to reject other cosplayers.
            if mention not in text:
                continue
            card_author=(card.get("data-username","") or "").casefold().lstrip("@")
            if mode=="teapawt-tagged":
                if card_author!=author:continue
            else:
                author_nodes=card.select(".username,.user-name,.screen-name,.tweet-user,.author")
                combined=" ".join(text_of(x) for x in author_nodes).casefold()
                if "@"+author not in combined and not re.search(r"(?<![a-z0-9_])@"+re.escape(author)+r"(?![a-z0-9_])",text):
                    continue
            for element in card.select("a[href],img[src],img[data-src],img[data-original]"):
                for attr in ("href","src","data-src","data-original"):
                    url=html.unescape(element.get(attr,""))
                    if allowed_image(url,source):found.append(url)
        return list(dict.fromkeys(found))
    raise ValueError("Source mode not implemented")

def check_photo(data:bytes) -> tuple[str,int,int,str]:
    if not 1024<=len(data)<=MAX_BYTES:raise ValueError("Invalid physical image length")
    sha=hashlib.sha256(data).hexdigest()
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        if img.width<200 or img.height<200:raise ValueError("Below minimum original photo dimensions")
        ext=FORMATS.get(img.format)
        if not ext:raise ValueError("Unsupported photo byte encoding")
        return sha,img.width,img.height,ext

def get_page(client,source,page_url=None):
    requested=page_url or source["url"]
    if urlsplit(requested).hostname!=urlsplit(source["url"]).hostname:
        raise ValueError("Untrusted pagination domain")
    response=client.get(requested,timeout=32,headers={"User-Agent":UA})
    response.raise_for_status()
    if urlsplit(response.url).hostname!=urlsplit(source["url"]).hostname:
        raise ValueError("Unexpected public source redirect host")
    return response.text

def visible_next_page(page_html, current_url, source, visited):
    """Only follow explicitly visible same-collection pagination; no URL guessing."""
    here=urlsplit(current_url)
    soup=BeautifulSoup(page_html,"html.parser")
    found=[]
    for a in soup.select("a[href]"):
        href=urljoin(current_url,a.get("href",""))
        p=urlsplit(href)
        if p.scheme!="https" or p.hostname!=here.hostname or p.path!=here.path:
            continue
        if href in visited:continue
        params=parse_qs(p.query)
        if not any(k in params for k in ("cursor","page","paged","max_position")):
            continue
        label=text_of(a).lower()
        if ("cursor" in params or
                any(x in label for x in ("next","load more","more","다음","다음 페이지","»","›","older")) or
                (params.get("page") and params["page"][0].isdigit())):
            found.append(href)
    return found[0] if found else None

def source_photo_pages(client,source):
    max_pages=min(max(int(source.get("max_pages",1)),1),50)
    current=source["url"]
    visited=set()
    combined=[]
    errors=[]
    while current and current not in visited and len(visited)<max_pages:
        visited.add(current)
        try:
            html=get_page(client,source,current)
        except (requests.RequestException,ValueError) as exc:
            errors.append(str(exc)[:130])
            if len(visited)==1 and source["kind"]=="inven-article" and source.get("verified_independent_public_article"):
                combined.extend(source_images(source,""))
            break
        combined.extend(source_images(source,html))
        if len(combined)>=350:break
        current=visible_next_page(html,current,source,visited)
    return list(dict.fromkeys(combined)),len(visited),errors

def get_photo(client,url,source):
    last_error=None
    for candidate in dict.fromkeys(origin_variant(url)):
        try:
            response=client.get(candidate,timeout=35,
                headers={"User-Agent":UA,"Referer":source["url"]},stream=True)
            response.raise_for_status()
            if not allowed_image(response.url,source):
                raise ValueError("Image redirected off authorized public media host")
            data=bytearray()
            for chunk in response.iter_content(chunk_size=64*1024):
                if not chunk:continue
                data.extend(chunk)
                if len(data)>MAX_BYTES:raise ValueError("Image exceeds maximum bytes")
            fmt=check_photo(bytes(data))
            return bytes(data),fmt
        except (requests.RequestException,OSError,ValueError) as exc:
            last_error=exc
        finally:
            if "response" in locals():response.close()
    raise ValueError("No valid publicly readable photo bytes: "+str(last_error)[:120])

def archive(model:str, source_index:dict, previous_catalog:dict, client, destination:Path):
    if model not in ("yui","mimmi") or previous_catalog.get("model")!=model or previous_catalog.get("schema_version")!=1:
        raise ValueError("Model owner archive mismatch")
    if not isinstance(previous_catalog.get("albums"),list):
        raise ValueError("Existing owner catalog not readable")
    existing={p["sha256"] for a in previous_catalog["albums"] for p in a["images"]}
    past={a["id"]:a for a in previous_catalog["albums"]}
    results=[]
    all_data={}
    audit=[]
    for source in source_index[model]["source_jobs"]:
        album_id=source["id"]
        if not VALID_ID.fullmatch(album_id):raise ValueError("Unsafe independent album identifier")
        previous=past.get(album_id,{"images":[]})
        current_num=max((p["number"] for p in previous["images"]),default=0)
        rows=[]
        rejected=0
        links,pages_seen,page_errors=source_photo_pages(client,source)
        if not links:
            audit.append({"source":album_id,"identified_public_photo_links":0,
                          "physically_new_photos":0,"pages_visited":pages_seen,
                          "errors":page_errors[:3]})
            continue
        for url in links[:350]:
            try:
                raw,(digest,width,height,ext)=get_photo(client,url,source)
                if digest in existing or digest in all_data:
                    continue
                current_num+=1
                if current_num>20000:raise ValueError("Album numbering cap")
                name=f"photos/{digest}.{ext}"
                rows.append({"number":current_num,"url":name,"sha256":digest,"bytes":len(raw),
                             "width":width,"height":height})
                all_data[digest]=(name,raw)
            except (requests.RequestException,OSError,ValueError):
                rejected+=1
        audit.append({"source":album_id,"identified_public_photo_links":len(links),
                      "physically_new_photos":len(rows),"pages_visited":pages_seen,
                      "page_errors":page_errors[:3],
                      "inaccessible_or_bad_images":rejected,
                      "photo_links_are_not_stored_counts":True})
        if rows:
            results.append({"id":album_id,"title":source["title"],"images":rows})
    destination.mkdir(parents=True,exist_ok=True)
    count=sum(len(a["images"]) for a in results)
    (destination/"independent-shoot-audit.json").write_text(
        json.dumps({"model":model,"actual_new_stored_images_in_actions_zip":count,
                    "source_results":audit},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if count:
        prefix="yui-indie" if model=="yui" else "mimmi-indie"
        path=destination/f"{prefix}-private-import.zip"
        manifest={"model":model,"physical_verified_image_count":count,"albums":results}
        with ZipFile(path,"w",compression=ZIP_STORED) as z:
            z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False))
            for name,raw in all_data.values():z.writestr(name,raw)
        with ZipFile(path) as z:
            for album in results:
                for row in album["images"]:
                    payload=z.read(row["url"])
                    if len(payload)!=row["bytes"] or hashlib.sha256(payload).hexdigest()!=row["sha256"]:
                        raise ValueError("Physical private photo ZIP failed SHA audit")
    print("INDEPENDENT_PHOTOS_ACTUAL_BYTES",json.dumps({
        "model":model,"new_real_image_files":count,"source_results":audit
    },ensure_ascii=False),flush=True)
    return count

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True,choices=["yui","mimmi"])
    parser.add_argument("--sources",type=Path,default=Path("apps/gallery-archive/independent_shoot_sources.json"))
    parser.add_argument("--previous",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    sources=json.loads(args.sources.read_text(encoding="utf-8"))
    previous=json.loads(args.previous.read_text(encoding="utf-8"))
    archive(args.model,sources,previous,requests.Session(),args.output)

if __name__=="__main__":main()
