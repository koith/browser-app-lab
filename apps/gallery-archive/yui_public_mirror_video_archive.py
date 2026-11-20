#!/usr/bin/env python3
"""Archive publicly embedded Yui MP4s with verified media SHA and playable bytes.

Source URLs are independently observed in one model-named public article.
Only exact catalogued URLs on the approved public media host can be downloaded.
No login, paywall, cookies, robots bypass or guessed media filenames.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser
import requests

ROOT=Path(__file__).resolve().parents[2]
VIDEO_MAX=6
BYTE_LIMIT=60_000_000
INDIVIDUAL_LIMIT=18_000_000
ARTICLE="https://www.mimint.co.kr/bbs/view/tvnews/influencer/484168"
UA="PersonalYuiPublicVideoArchive/1.0 (robots-respecting)"
PHOTOBOOK_VIDEO_HOST="manpeace.org"

class MediaError(Exception):pass

def is_observed_public_video(value):
    if not isinstance(value,str) or len(value)>650:return False
    try:
        p=urlsplit(value)
        return (p.scheme=="https" and p.hostname==PHOTOBOOK_VIDEO_HOST
                and not p.username and not p.password and p.port in (None,443)
                and not p.fragment
                and re.fullmatch(r"/data/video/\d{6}/[^/]+\.mp4",unquote(p.path),re.I) is not None)
    except (ValueError,UnicodeError):return False

class PublicMediaClient:
    def __init__(self,session=None):
        self.session=session or requests.Session()
        self.session.headers.update({"User-Agent":UA})
        self._robots=None
    def permitted(self,url):
        if not is_observed_public_video(url):return False
        if self._robots is None:
            try:
                r=self.session.get("https://"+PHOTOBOOK_VIDEO_HOST+"/robots.txt",
                                   timeout=(7,10),allow_redirects=False)
                if r.status_code==404:self._robots=True
                elif r.status_code==200 and len(r.content)<300000:
                    # Some sites use duplicate wildcard User-agent blocks.
                    # RobotFileParser may honor the FIRST block only; fail
                    # closed if ANY published group disallows the media /data/
                    # directory instead of silently taking the permissive one.
                    lines=r.text.splitlines()
                    if any(re.match(r"\\s*Disallow:\\s*/data/(?:\\s|$)",line,re.I)
                           for line in lines):
                        self._robots=False
                    else:
                        parser=RobotFileParser()
                        parser.parse(lines)
                        self._robots=parser
                else:self._robots=False
            except requests.RequestException:self._robots=False
        return self._robots is True or (self._robots is not False
                                      and self._robots.can_fetch(UA,url))
    def get(self,url,max_bytes):
        if not self.permitted(url):raise MediaError("robots_or_public_host_denied")
        try:
            r=self.session.get(url,stream=True,timeout=(8,35),allow_redirects=False)
            try:
                if r.status_code!=200:raise MediaError("http_"+str(r.status_code))
                mime=r.headers.get("Content-Type","").split(";")[0].lower()
                if mime and mime not in ("video/mp4","application/octet-stream"):
                    raise MediaError("not_mp4_mime")
                length=r.headers.get("Content-Length")
                if length and int(length)>max_bytes:raise MediaError("size_limit")
                data=bytearray()
                for chunk in r.iter_content(65536):
                    data.extend(chunk)
                    if len(data)>max_bytes:raise MediaError("size_limit")
                if length and int(length)!=len(data):raise MediaError("content_length_mismatch")
                return bytes(data)
            finally:r.close()
        except requests.RequestException as e:raise MediaError("network_"+type(e).__name__) from e

def video_bytes_digest(raw):
    if len(raw)<4096 or raw[4:8]!=b"ftyp":
        raise MediaError("not_mp4")
    return hashlib.sha256(raw).hexdigest()

def playable_mp4(raw):
    """Require a real decodable video stream before claiming a saved video."""
    if not shutil.which("ffprobe"):
        raise MediaError("ffprobe_unavailable")
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(raw);tmp.flush()
        try:
            r=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
               "-show_entries","stream=codec_type","-of","default=noprint_wrappers=1:nokey=1",
               tmp.name],timeout=25,capture_output=True,text=True,check=False)
        except (OSError,subprocess.TimeoutExpired) as e:
            raise MediaError("video_decode_probe_failed") from e
        if r.returncode!=0 or "video" not in r.stdout.splitlines():
            raise MediaError("invalid_video_stream")
    return True

def archive(root=ROOT,client=None,probe=playable_mp4,max_files=VIDEO_MAX,budget=BYTE_LIMIT):
    if not 1<=max_files<=6 or not 1024<=budget<=60_000_000:raise ValueError("video budget")
    root=Path(root);base=root/"apps/yui-gallery"
    catalog_file=base/"videos.json"
    catalog=json.loads(catalog_file.read_text(encoding="utf-8"))
    if catalog.get("schema_version")!=1 or catalog.get("model")!="yui":
        raise ValueError("catalog mismatch")
    client=client or PublicMediaClient()
    stats=Counter();errors=Counter();saved=[]
    for row in catalog["videos"]:
        if row.get("kind")!="remote_mp4":continue
        url=row.get("media_url")
        if row.get("source_url")!=ARTICLE or not is_observed_public_video(url):
            errors["untrusted_observation"]+=1
            continue
        if stats["stored"]>=max_files:
            errors["max_video_count"]+=1
            break
        try:
            raw=client.get(url,min(INDIVIDUAL_LIMIT,budget-stats["bytes"]))
            sha=video_bytes_digest(raw)
            if not probe(raw):
                raise MediaError("not_playable")
            dest=base/"stored-videos"/(sha+".mp4")
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.is_file() and dest.read_bytes()!=raw:
                raise MediaError("physical_sha_collision")
            if not dest.is_file():
                temporary=dest.with_suffix(".mp4.partial")
                temporary.write_bytes(raw)
                temporary.replace(dest)
            row.update({"kind":"local_mp4","path":"stored-videos/"+sha+".mp4",
                "sha256":sha,"bytes":len(raw),
                "note":"공개 게시물 영상 실파일을 SHA-256·ffprobe로 검증해 저장"})
            stats["stored"]+=1;stats["bytes"]+=len(raw)
            saved.append({"id":row["id"],"sha256":sha,"bytes":len(raw)})
        except MediaError as e:
            errors[str(e)]+=1
    if stats["stored"]:
        dest=catalog_file.with_suffix(".json.partial")
        dest.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        dest.replace(catalog_file)
    report={"model":"yui","source":ARTICLE,
       "observed_media_urls":sum(x.get("kind")=="remote_mp4" for x in catalog["videos"])+stats["stored"],
       "new_stored_video_files":stats["stored"],"new_stored_bytes":stats["bytes"],
       "remaining_remote_source_links":sum(x.get("kind")=="remote_mp4" for x in catalog["videos"]),
       "errors":dict(errors),"saved":saved,
       "note":"Only complete ffprobe-verified MP4 bytes count as stored video files."}
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",type=Path)
    p.add_argument("--max-files",type=int,default=VIDEO_MAX)
    args=p.parse_args()
    report=archive(max_files=args.max_files)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("YUI_PUBLIC_MIRROR_VIDEO_REAL_BYTES",json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
