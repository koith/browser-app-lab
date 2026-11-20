#!/usr/bin/env python3
"""Bounded JJTV public image/video source survey and real MP4 SHA archive.

No login, cookies, paywall or robots bypass. A search result alone never counts
as archived bytes; each video must be embedded by the exact matched article
and decode as a complete MP4 under the free Pages size budget.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
from io import BytesIO
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from PIL import Image
import requests

ROOT=Path(__file__).resolve().parents[2]
UA="PersonalGalleryPublicArchive/1.0 (respect robots; no login)"
MODELS={"yui":re.compile(r"심유이|심혜성|super_yuisan|(?:^|\W)yui(?:\W|$)",re.I),
        "mimmi":re.compile(r"밈미|mimmimimmi|mimmissu17|(?:^|\W)mimmi(?:\W|$)",re.I)}
ALIASES={"yui":("심유이","심혜성"),"mimmi":("밈미","Mimmi")}
MEDIA_LIMIT=18_000_000
PAGE_LIMIT=1_800_000
POST_RE=re.compile(r"^/(?:15|inf|15_jjal)/[0-9]+/?$")
MP4_RE=re.compile(r"\.mp4(?:\?|$)",re.I)
PHOTO_RE=re.compile(r"\.(?:jpe?g|png|webp)$",re.I)
NON_CUT=re.compile(r"(?:^|[-_.])(?:logo|avatar|icon|banner|poster|thumb|cover|favicon)(?:[-_.]|$)|_0000\.(?:jpg|jpeg|webp|png)$",re.I)
PHOTO_LIMIT=20
PHOTO_MAX_BYTES=9_000_000

class SiteError(Exception):pass

def same_public_host(url):
    try:
        p=urlsplit(url)
        h=(p.hostname or "").casefold()
        return p.scheme=="https" and h in {"jjtv.kr","www.jjtv.kr","img2.jjtv.kr","img.jjtv.kr"} and not p.username and not p.password and p.port in (None,443)
    except ValueError:return False

class Client:
    def __init__(self,session=None):
        self.session=session or requests.Session()
        self.session.headers.update({"User-Agent":UA,"Accept":"text/html,video/mp4;q=.9,*/*;q=.4"})
        self.rules={}
    def allowed(self,url):
        if not same_public_host(url):return False
        p=urlsplit(url);origin="https://"+p.netloc
        if origin not in self.rules:
            try:
                r=self.session.get(origin+"/robots.txt",timeout=(5,8),allow_redirects=False)
                if r.status_code==404:
                    self.rules[origin]=None
                elif r.status_code==200 and len(r.content)<400000:
                    parser=RobotFileParser()
                    parser.parse(r.text.splitlines())
                    self.rules[origin]=parser
                else:self.rules[origin]=False
            except requests.RequestException:self.rules[origin]=False
        rule=self.rules[origin]
        return rule is None or (rule is not False and rule.can_fetch(UA,url))
    def get(self,url,max_bytes=PAGE_LIMIT,kind="html"):
        if not self.allowed(url):raise SiteError("robots_or_nonpublic")
        try:
            r=self.session.get(url,timeout=(7,18),stream=True,allow_redirects=False)
            try:
                if r.status_code!=200:raise SiteError("http_"+str(r.status_code))
                content_type=r.headers.get("Content-Type","").lower()
                if kind=="html" and "html" not in content_type:raise SiteError("not_html")
                if kind=="video" and content_type and not any(x in content_type for x in ("video/mp4","application/octet-stream")):
                    raise SiteError("not_mp4_mime")
                if kind=="image" and content_type and not (content_type.startswith("image/") or "application/octet-stream" in content_type):
                    raise SiteError("not_image_mime")
                if int(r.headers.get("Content-Length","0") or "0")>max_bytes:raise SiteError("size_limit")
                data=bytearray()
                for chunk in r.iter_content(65536):
                    data.extend(chunk)
                    if len(data)>max_bytes:raise SiteError("size_limit")
                return bytes(data)
            finally:r.close()
        except requests.RequestException as exc:raise SiteError("network_"+type(exc).__name__) from exc

def links_from_search(raw,model):
    soup=BeautifulSoup(raw,"html.parser")
    matches=[]
    for a in soup.select("a[href]"):
        title=a.get_text(" ",strip=True)
        if not MODELS[model].search(title):continue
        url=urljoin("https://jjtv.kr/",a["href"])
        if same_public_host(url) and POST_RE.fullmatch(urlsplit(url).path):
            if url not in matches:matches.append(url)
    return matches[:70]

def actual_article(raw,url,model):
    soup=BeautifulSoup(raw,"html.parser")
    heading=" ".join([soup.title.get_text(" ",strip=True) if soup.title else "",
        *(n.get_text(" ",strip=True) for n in soup.select("h1,h2")[:3]),
        *(str(n.get("content") or "") for n in soup.select('meta[property="og:title"]')[:2])])
    if not MODELS[model].search(heading):
        return None,"model_not_in_article_heading"
    for selector in ("#bo_v_con","#bo_v_content",".view-content",".board-view-content","#view_content","article",".entry-content"):
        section=soup.select_one(selector)
        if section is not None:break
    else:return None,"article_container_not_found"
    for item in section.select("aside,footer,nav,.related,.recommend,.comments,.sidebar"):
        item.decompose()
    video_urls=[]
    for item in section.select('video[src],source[src],a[href],iframe[src]'):
        observed=item.get("src") or item.get("href")
        if not isinstance(observed,str):continue
        video_url=urljoin(url,unescape(observed).strip())
        if same_public_host(video_url) and MP4_RE.search(urlsplit(video_url).path):
            if video_url not in video_urls:video_urls.append(video_url)
    photo_urls=[]
    for item in section.select("img,source,a[href]"):
        if item.find_parent("video") is not None:continue
        values=[]
        for attr in ("data-original","data-full","data-large-file",
                     "data-hires","data-lazy-src","data-src","src","href"):
            raw_attr=item.get(attr)
            if isinstance(raw_attr,str):values.append(raw_attr)
        for attr in ("srcset","data-srcset"):
            value=item.get(attr)
            if isinstance(value,str):
                values.extend(part.strip().split()[0] for part in value.split(",") if part.strip())
        for candidate in values:
            candidate_url=urljoin(url,unescape(candidate).strip())
            path=urlsplit(candidate_url).path
            if (same_public_host(candidate_url) and PHOTO_RE.search(path)
                    and not NON_CUT.search(path.rsplit("/",1)[-1])
                    and candidate_url not in photo_urls):
                photo_urls.append(candidate_url)
    return {"title":heading[:240],"page":url,"videos":video_urls[:12],
            "photos":photo_urls[:160]},"ok"

def inspect_mp4(data):
    if len(data)<1024 or data[4:8]!=b"ftyp":
        raise SiteError("not_real_mp4_bytes")
    return hashlib.sha256(data).hexdigest()

def inspect_photo(data):
    if len(data)<4500 or len(data)>PHOTO_MAX_BYTES:
        raise SiteError("photo_bytes_out_of_bounds")
    try:
        with Image.open(BytesIO(data)) as image:
            fmt=image.format
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            width,height=image.size
    except (OSError,ValueError,Image.DecompressionBombError) as exc:
        raise SiteError("photo_not_decoded") from exc
    if fmt not in ("JPEG","PNG","WEBP") or min(width,height)<700 or width*height>100_000_000:
        raise SiteError("photo_dimensions_or_type")
    return {"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),
            "width":width,"height":height,
            "ext":{"JPEG":"jpg","PNG":"png","WEBP":"webp"}[fmt]}


def crawl(model,root=ROOT,client=None,max_pages=16,max_posts=80,archive=False,delay=.35,
          stage=None,max_photos=PHOTO_LIMIT):
    if model not in MODELS or not 1<=max_pages<=100 or not 1<=max_posts<=250 or not 1<=max_photos<=100:raise ValueError("bounded model/page/post/photos")
    client=client or Client();root=Path(root)
    base=root/"apps"/(model+"-gallery")
    catalog_path=base/"videos.json"
    catalog=json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("model")!=model:raise ValueError("wrong video catalog")
    existing=set(x.get("sha256") for x in catalog["videos"] if x.get("kind")=="local_mp4")
    seen=set()
    source_pages=["https://jjtv.kr/15/154066"] if model=="yui" else []
    counts=Counter();reasons=Counter();verified=[]
    photo_stage=Path(stage) if stage is not None else None
    photo_albums=[];photo_proofs=[];photo_seen=set()
    for term in ALIASES[model]:
        for page in range(1,max_pages+1):
            url="https://jjtv.kr/bbs/meili_search.php?"+urlencode({"stx":term,"page":page})
            try:
                raw=client.get(url)
                matches=links_from_search(raw,model)
                counts["search_pages"]+=1
                source_pages.extend(matches)
                if not matches:break
            except SiteError as e:
                reasons["search_"+str(e)]+=1
                break
            if len(set(source_pages))>=max_posts:break
            if delay:time.sleep(delay)
    for url in source_pages:
        if len(seen)>=max_posts:break
        url="https://jjtv.kr"+urlsplit(url).path
        if url in seen:continue
        seen.add(url)
        try:
            raw=client.get(url)
            proof,state=actual_article(raw,url,model)
            if not proof:
                reasons[state]+=1
                continue
            counts["verified_posts"]+=1
            counts["video_candidates"]+=len(proof["videos"])
            counts["photo_candidates"]+=len(proof["photos"])
            verified.append({"title":proof["title"],"page":url,
                             "video_candidates":len(proof["videos"]),
                             "photo_candidates":len(proof["photos"])})
            if archive and photo_stage is not None and counts["staged_photo_sha"]<max_photos:
                relative_album="jjtv-"+urlsplit(url).path.strip("/").replace("/","-")
                staged=[]
                for observed_url in proof["photos"]:
                    if len(staged)>=4 or counts["staged_photo_sha"]>=max_photos:break
                    try:
                        image_data=client.get(observed_url,PHOTO_MAX_BYTES,kind="image")
                        meta=inspect_photo(image_data)
                        if meta["sha256"] in photo_seen:
                            counts["staged_photo_duplicate"]+=1
                            continue
                        photo_seen.add(meta["sha256"])
                        key="originals/"+relative_album+"/"+meta["sha256"][:20]+"."+meta["ext"]
                        dest=photo_stage/key
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        if dest.is_file() and dest.read_bytes()!=image_data:
                            raise SiteError("photo_sha_stage_collision")
                        if not dest.is_file():
                            tmp=dest.with_suffix(".partial")
                            tmp.write_bytes(image_data)
                            tmp.replace(dest)
                        staged.append({"key":key,"sha256":meta["sha256"],
                                       "bytes":meta["bytes"],"width":meta["width"],
                                       "height":meta["height"],"number":len(staged)+1,
                                       "source_url":observed_url,
                                       "numbering_provenance":"archive_append_order_not_publisher_number"})
                        counts["staged_photo_sha"]+=1
                    except SiteError as exc:
                        reasons["photo_"+str(exc)]+=1
                if staged:
                    photo_albums.append({"id":relative_album,"title":proof["title"],
                                         "images":staged})
                    photo_proofs.append({"id":relative_album,"title":proof["title"],
                                         "source":url,"verified_same_work_pages":[url],
                                         "proof":"unique_named_work_page_model_and_edition"})
            for video_url in proof["videos"]:
                if not archive:continue
                try:
                    data=client.get(video_url,MEDIA_LIMIT,kind="video")
                    sha=inspect_mp4(data)
                    if sha in existing:
                        counts["duplicate_video"]+=1
                        continue
                    dest=base/"stored-videos"/(sha+".mp4")
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if dest.is_file() and dest.read_bytes()!=data:raise SiteError("sha_filename_collision")
                    if not dest.is_file():
                        tmp=dest.with_suffix(".mp4.partial")
                        tmp.write_bytes(data)
                        tmp.replace(dest)
                    existing.add(sha)
                    catalog["videos"].append({"id":"jjtv-"+urlsplit(url).path.rsplit("/",1)[-1]+"-"+sha[:10],
                        "title":proof["title"],"kind":"local_mp4","path":"stored-videos/"+sha+".mp4",
                        "sha256":sha,"bytes":len(data),"source_url":url,
                        "note":"JJTV 일반 공개 게시물에 직접 포함된 MP4 실파일 저장"})
                    counts["stored_files"]+=1
                    counts["stored_bytes"]+=len(data)
                except SiteError as e:reasons["video_"+str(e)]+=1
        except SiteError as e:reasons["post_"+str(e)]+=1
        if delay:time.sleep(delay)
    if photo_stage is not None:
        metadata=photo_stage/"metadata"
        metadata.mkdir(parents=True,exist_ok=True)
        (metadata/"catalog.json").write_text(json.dumps({
            "model":model,"albums":photo_albums,
            "verified_new_work_sources":photo_proofs},ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8")
    if counts["stored_files"]:
        catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"model":model,"source":"https://jjtv.kr/15/154066" if model=="yui" else "https://jjtv.kr",
            "visited_posts":len(seen),"counts":dict(counts),"errors":dict(reasons),
            "verified_post_samples":verified[:12],"archived_files":counts["stored_files"],
            "staged_photo_sha_not_published":counts["staged_photo_sha"],
            "note":"Search and source URL alone do not count as archived video bytes."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=["yui","mimmi"],required=True)
    p.add_argument("--archive",action="store_true")
    p.add_argument("--max-pages",type=int,default=16)
    p.add_argument("--max-posts",type=int,default=80)
    p.add_argument("--report",type=Path)
    p.add_argument("--stage",type=Path)
    p.add_argument("--max-photos",type=int,default=PHOTO_LIMIT)
    args=p.parse_args()
    result=crawl(args.model,max_pages=args.max_pages,max_posts=args.max_posts,
                 archive=args.archive,stage=args.stage,max_photos=args.max_photos)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("JJTV_PUBLIC_MEDIA_REAL_BYTES",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
