#!/usr/bin/env python3
"""Find further Mimmi albums by multiple public search names and titles.

Only publicly linked PixiBB article URLs are examined; no generated photo
addresses, login, paywall or protected endpoint access.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote,urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
BASE="https://cosplay.pixibb.com"
TERMS=["Mimmi","밈미","Mimmissu17","Miss u DJAWA","ミミ DJAWA","CreamSoda Mimmi"]
USER_AGENT="Mozilla/5.0 (compatible; PublicMimmiAlbumSearch/1.0)"
S=requests.Session()
S.headers.update({"User-Agent":USER_AGENT,"Accept":"text/html,application/xhtml+xml"})
T=(9,24)
PATH=re.compile(r"^/[a-z0-9][a-z0-9-]{8,200}/?$",re.I)
MIMMI=re.compile(r"Mimmi|밈미|밈미|mimmissu17",re.I)

def allowed_article(url):
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.hostname=="cosplay.pixibb.com"
                and not p.username and not p.password and not p.port
                and not p.query and not p.fragment and bool(PATH.fullmatch(p.path))
                and not any(p.path.startswith("/"+x) for x in ("page/","category/","tag/","author/","wp-","feed/")))
    except (TypeError,ValueError):return False

def links(html,base):
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    for a in soup.select("article a[href],h2 a[href],h3 a[href]"):
        u=urljoin(base,a.get("href",""))
        if not allowed_article(u) or u in out:continue
        text=a.get_text(" ",strip=True)
        # Search returns other cosplayers; require Mimmi identity from visible
        # search result title, not category labels or page sidebar.
        parent=a.find_parent("article")
        context=parent.get_text(" ",strip=True)[:300] if parent else text
        if MIMMI.search(text+" "+context):
            out.append(u)
    return out

def inspect_work(url):
    if not allowed_article(url):raise ValueError("Not a public article URL")
    r=S.get(url,timeout=T,allow_redirects=False)
    r.raise_for_status()
    if r.status_code!=200 or not allowed_article(r.url):
        raise ValueError("Article redirected")
    soup=BeautifulSoup(r.text,"html.parser")
    h=soup.find("h1")
    title=(h.get_text(" ",strip=True) if h else "")
    if not MIMMI.search(title):raise ValueError("Not Mimmi subject")
    pagination=soup.get_text(" ",strip=True)[:3000]
    m=re.search(r"Page\s+\d+\s+of\s+(\d{1,3})",pagination,re.I)
    pages=min(30,int(m.group(1))) if m else 12
    slug=urlsplit(url).path.strip("/")
    return {"id":"pixibb-auto-"+slug[:80],
            "title":re.sub(r"\s*\(\d{1,4}\s+photos?\)\s*Cosplay\s*$","",title,flags=re.I)[:180],
            "source":url,"pages":pages,
            "publisher":"DJAWA" if "DJAWA" in title.upper() else "other public photographer",
            "source_evidence":"search_link_and_live_article_heading"}

def search(max_search_pages=2,max_candidates=80):
    found={};status=[]
    for word in TERMS:
        for page in range(1,max_search_pages+1):
            url=f"{BASE}/?s={quote(word)}"
            if page>1:url+=f"&paged={page}"
            try:
                r=S.get(url,timeout=T,allow_redirects=False)
                r.raise_for_status()
                if r.status_code!=200 or urlsplit(r.url).hostname!="cosplay.pixibb.com":
                    raise ValueError("Search redirected")
                candidates=links(r.text,BASE)
                status.append({"term":word,"page":page,"found_links":len(candidates)})
                for u in candidates:
                    if len(found)>=max_candidates:break
                    if u not in found:found[u]=None
                print("MIMMI_MULTILINGUAL_SEARCH",word,page,len(candidates),flush=True)
                if not candidates or len(found)>=max_candidates:break
            except (requests.RequestException,ValueError) as exc:
                status.append({"term":word,"page":page,"error":type(exc).__name__})
                print("MIMMI_MULTILINGUAL_SEARCH_ERROR",word,type(exc).__name__,flush=True)
                break
            time.sleep(.35)
    results=[]
    for url in found:
        try:
            data=inspect_work(url)
            results.append(data)
            print("MIMMI_MULTILINGUAL_ALBUM_FOUND",url,flush=True)
        except (requests.RequestException,ValueError):
            continue
        time.sleep(.35)
    result={"schema_version":1,"model":"mimmi","generated_at":datetime.now(timezone.utc).isoformat(),
            "source":"actual public PixiBB search results in six model-language variants",
            "summary":{"search_terms":TERMS,"candidates":len(found),"verified_mimmi_album_pages":len(results),
                       "verified_photo_files":0},"albums":results,"search_pages":status}
    out=ROOT/"pixibb-discovered-seeds.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_SEARCH_DISCOVERY_RESULT",json.dumps(result["summary"],ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--pages",type=int,default=2)
    p.add_argument("--limit",type=int,default=80)
    args=p.parse_args()
    if not 1<=args.pages<=5 or not 1<=args.limit<=150:p.error("bounded public work search")
    search(args.pages,args.limit)
