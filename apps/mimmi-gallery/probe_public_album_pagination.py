#!/usr/bin/env python3
"""Investigate actual album pagination links; never guess/force protected content."""
from __future__ import annotations
import json,re,sys
from urllib.parse import urljoin,urlsplit,parse_qs
import requests
from bs4 import BeautifulSoup
from pathlib import Path
ROOT=Path(__file__).resolve().parent
targets=json.loads((ROOT/"v2ph-targets.json").read_text())["albums"]
def scoped(url):
    p=urlsplit(url)
    return p.scheme=="https" and p.hostname in {"www.v2ph.com","v2ph.com"} and p.path.startswith("/album/")
s=requests.Session();s.headers.update({"User-Agent":"Mozilla/5.0 (compatible; GalleryResearch/1.0)"})
for a in targets[:3]:
    u=a["source"]
    try:
        r=s.get(u,timeout=(10,20));r.raise_for_status()
        doc=BeautifulSoup(r.text,"html.parser")
        links=[]
        for tag in doc.select("a[href]"):
            href=urljoin(r.url,tag.get("href",""))
            if not scoped(href):continue
            text=tag.get_text(" ",strip=True)
            cls=" ".join(tag.get("class",[]))
            rel=" ".join(tag.get("rel",[]))
            if any(k in (cls+" "+rel+" "+text+" "+href).lower() for k in ["page","next","last","다음","след","pagination"]) or re.fullmatch(r"\d{1,3}",text):
                if href not in [p["url"] for p in links]:
                    links.append({"text":text[:30],"url":href,"class":cls[:100],"rel":rel[:60]})
        probes=[]
        # Only hrefs actually exposed by the current public album.
        for item in links[:8]:
            if item["url"]==r.url:continue
            try:
                q=s.get(item["url"],timeout=(10,18))
                page=BeautifulSoup(q.content,"html.parser")
                im=[im.get("data-src") or im.get("src") for im in page.select("img") if "cdn.v2ph.com/photos/" in str(im)]\n                examples=[{k:v[:150] for k,v in img.attrs.items() if isinstance(v,str)} for img in page.select("img")[:8]]\n                cdnRaw=[re.sub(r"[^a-zA-Z0-9/._:-]"," ",q)[:150] for q in re.findall(r".{0,60}(?:v2ph.com|\.jpg|\.webp).{0,60}",q.text,re.I)[:6]]\n                print("MIMMI_PAGE2_RAW",json.dumps({"album":a["id"],"url":q.url,"all_img_tags":len(page.select("img")),"examples":examples,"cdn_snippets":cdnRaw},ensure_ascii=False),flush=True)
                probes.append({"url":q.url,"code":q.status_code,"images":len(im),"h1":page.find("h1").get_text(" ",strip=True)[:70] if page.find("h1") else ""})
            except Exception as e:probes.append({"url":item["url"],"error":str(e)[:140]})
        print("MIMMI_REAL_PAGINATION",json.dumps({"album":a["id"],"url":r.url,"code":r.status_code,"anchor_links":links[:35],"probe":probes},ensure_ascii=False),flush=True)
    except Exception as e:print("MIMMI_REAL_PAGINATION_ERROR",a["id"],type(e).__name__,str(e)[:160],flush=True)
